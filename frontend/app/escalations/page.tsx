"use client";

import { useEffect, useState, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Escalation {
  ref_id: string;
  user_id: string;
  caller_name: string;
  reason_type: "payment_dispute" | "order_dispute";
  summary: string;
  urgency: "low" | "medium" | "high" | "emergency";
  language: string;
  follow_up_method: string;
  agent_checked: string;
  status: "open" | "in_progress" | "resolved";
  created_at: string;
  updated_at: string;
}

// ─── Config ──────────────────────────────────────────────────────────────────

const URGENCY_CONFIG = {
  emergency: {
    label: "EMERGENCY",
    emoji: "🚨",
    badgeClass: "badge-emergency",
    rowClass: "row-emergency",
  },
  high: {
    label: "HIGH",
    emoji: "🔴",
    badgeClass: "badge-high",
    rowClass: "row-high",
  },
  medium: {
    label: "MEDIUM",
    emoji: "🟠",
    badgeClass: "badge-medium",
    rowClass: "row-medium",
  },
  low: {
    label: "LOW",
    emoji: "🔵",
    badgeClass: "badge-low",
    rowClass: "row-low",
  },
};

const REASON_LABELS: Record<string, string> = {
  payment_dispute: "💳 Payment / Refund",
  order_dispute: "📦 Order / Delivery",
};

const STATUS_CONFIG = {
  open: { label: "Open", class: "status-open", dot: "dot-open" },
  in_progress: {
    label: "In Progress",
    class: "status-inprogress",
    dot: "dot-inprogress",
  },
  resolved: {
    label: "Resolved",
    class: "status-resolved",
    dot: "dot-resolved",
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDateTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─── Components ──────────────────────────────────────────────────────────────

function UrgencyBadge({ urgency }: { urgency: Escalation["urgency"] }) {
  const cfg = URGENCY_CONFIG[urgency] ?? URGENCY_CONFIG.low;
  return (
    <span className={`badge ${cfg.badgeClass}`}>
      {cfg.emoji} {cfg.label}
    </span>
  );
}

function StatusPill({ status }: { status: Escalation["status"] }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.open;
  return (
    <span className={`status-pill ${cfg.class}`}>
      <span className={`status-dot ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function EscalationCard({
  ticket,
  onUpdateStatus,
}: {
  ticket: Escalation;
  onUpdateStatus: (ref_id: string, status: string) => void;
}) {
  const urgCfg = URGENCY_CONFIG[ticket.urgency] ?? URGENCY_CONFIG.low;

  return (
    <div className={`ticket-card ${urgCfg.rowClass}`}>
      {/* Header Row */}
      <div className="card-header">
        <div className="card-header-left">
          <span className="ref-id">{ticket.ref_id}</span>
          <span className="time-ago" suppressHydrationWarning>{timeAgo(ticket.created_at)}</span>
        </div>
        <div className="card-header-right">
          <UrgencyBadge urgency={ticket.urgency} />
          <StatusPill status={ticket.status} />
        </div>
      </div>

      {/* Caller Info */}
      <div className="card-caller">
        <span className="caller-icon">👤</span>
        <div>
          <span className="caller-name">{ticket.caller_name}</span>
          <span className="caller-meta">
            {REASON_LABELS[ticket.reason_type] ?? ticket.reason_type} &middot;{" "}
            {ticket.language.toUpperCase()} &middot;{" "}
            📞 {ticket.follow_up_method}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div className="card-summary">
        <p className="summary-text">{ticket.summary}</p>
      </div>

      {/* Agent Checked */}
      {ticket.agent_checked && (
        <div className="card-agent-checked">
          <span className="agent-checked-label">🔍 Agent verified:</span>
          <span className="agent-checked-text">{ticket.agent_checked}</span>
        </div>
      )}

      {/* Footer */}
      <div className="card-footer">
        <span className="updated-at" suppressHydrationWarning>
          Updated {formatDateTime(ticket.updated_at)}
        </span>
        {ticket.status !== "resolved" && (
          <div className="card-actions">
            {ticket.status === "open" && (
              <button
                className="btn btn-inprogress"
                onClick={() => onUpdateStatus(ticket.ref_id, "inprogress")}
              >
                Mark In Progress
              </button>
            )}
            <button
              className="btn btn-resolve"
              onClick={() => onUpdateStatus(ticket.ref_id, "resolve")}
            >
              Resolve ✓
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Stats Banner ─────────────────────────────────────────────────────────────

function StatsBanner({ tickets }: { tickets: Escalation[] }) {
  const open = tickets.filter((t) => t.status === "open").length;
  const inProgress = tickets.filter((t) => t.status === "in_progress").length;
  const resolved = tickets.filter((t) => t.status === "resolved").length;
  const highUrgency = tickets.filter(
    (t) => (t.urgency === "high" || t.urgency === "emergency") && t.status !== "resolved"
  ).length;

  return (
    <div className="stats-banner">
      <div className="stat-card stat-open">
        <span className="stat-num">{open}</span>
        <span className="stat-label">Open</span>
      </div>
      <div className="stat-card stat-inprogress">
        <span className="stat-num">{inProgress}</span>
        <span className="stat-label">In Progress</span>
      </div>
      <div className="stat-card stat-resolved">
        <span className="stat-num">{resolved}</span>
        <span className="stat-label">Resolved</span>
      </div>
      <div className="stat-card stat-urgent">
        <span className="stat-num">{highUrgency}</span>
        <span className="stat-label">Urgent</span>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function EscalationsPage() {
  const [tickets, setTickets] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchTickets = useCallback(async () => {
    try {
      const url =
        filterStatus === "all"
          ? "/api/escalations"
          : `/api/escalations?status=${filterStatus}`;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTickets(data.escalations ?? []);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      setError("Could not reach the escalation API. Make sure the backend is running.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    fetchTickets();
    const interval = setInterval(fetchTickets, 30000); // auto-refresh every 30s
    return () => clearInterval(interval);
  }, [fetchTickets]);

  const handleUpdateStatus = async (ref_id: string, newStatus: string) => {
    try {
      const res = await fetch(
        `http://localhost:8765/api/escalations/${ref_id}/${newStatus}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchTickets();
    } catch (err) {
      console.error("Status update failed:", err);
    }
  };

  const filtered =
    filterStatus === "all"
      ? tickets
      : tickets.filter((t) => t.status === filterStatus.replace("-", "_"));

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
          font-family: 'Inter', sans-serif;
          background: #0a0b0f;
          color: #e2e8f0;
          min-height: 100vh;
        }

        .page-wrap {
          max-width: 1100px;
          margin: 0 auto;
          padding: 2rem 1.5rem 4rem;
        }

        /* ─── Header ─────────────────────────── */
        .page-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          margin-bottom: 2rem;
          gap: 1rem;
          flex-wrap: wrap;
        }
        .header-brand {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        .brand-logo {
          width: 42px;
          height: 42px;
          background: linear-gradient(135deg, #7c3aed, #db2777);
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.3rem;
          box-shadow: 0 0 20px rgba(124,58,237,0.4);
        }
        .brand-text h1 {
          font-size: 1.4rem;
          font-weight: 700;
          background: linear-gradient(135deg, #c4b5fd, #f9a8d4);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          line-height: 1.2;
        }
        .brand-text p {
          font-size: 0.78rem;
          color: #64748b;
          margin-top: 2px;
        }
        .header-actions {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          flex-wrap: wrap;
        }
        .refresh-info {
          font-size: 0.73rem;
          color: #475569;
        }
        .btn-refresh {
          background: rgba(124,58,237,0.15);
          border: 1px solid rgba(124,58,237,0.3);
          color: #c4b5fd;
          border-radius: 8px;
          padding: 0.45rem 1rem;
          font-size: 0.82rem;
          cursor: pointer;
          transition: all 0.2s;
          font-family: inherit;
        }
        .btn-refresh:hover {
          background: rgba(124,58,237,0.3);
          border-color: rgba(124,58,237,0.6);
        }

        /* ─── Stats Banner ─────────────────────── */
        .stats-banner {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 1rem;
          margin-bottom: 1.75rem;
        }
        @media (max-width: 640px) {
          .stats-banner { grid-template-columns: repeat(2, 1fr); }
        }
        .stat-card {
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 12px;
          padding: 1rem 1.25rem;
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
          backdrop-filter: blur(10px);
          transition: transform 0.2s;
        }
        .stat-card:hover { transform: translateY(-2px); }
        .stat-num {
          font-size: 1.9rem;
          font-weight: 700;
          font-family: 'JetBrains Mono', monospace;
          line-height: 1;
        }
        .stat-label { font-size: 0.78rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-open   { border-color: rgba(251,191,36,0.2); }
        .stat-open .stat-num { color: #fbbf24; }
        .stat-inprogress { border-color: rgba(59,130,246,0.2); }
        .stat-inprogress .stat-num { color: #60a5fa; }
        .stat-resolved { border-color: rgba(52,211,153,0.2); }
        .stat-resolved .stat-num { color: #34d399; }
        .stat-urgent { border-color: rgba(239,68,68,0.2); }
        .stat-urgent .stat-num { color: #f87171; }

        /* ─── Filter Bar ────────────────────────── */
        .filter-bar {
          display: flex;
          gap: 0.5rem;
          margin-bottom: 1.25rem;
          flex-wrap: wrap;
        }
        .filter-btn {
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          color: #94a3b8;
          border-radius: 8px;
          padding: 0.4rem 0.9rem;
          font-size: 0.8rem;
          cursor: pointer;
          transition: all 0.15s;
          font-family: inherit;
        }
        .filter-btn:hover {
          background: rgba(255,255,255,0.08);
          color: #e2e8f0;
        }
        .filter-btn.active {
          background: rgba(124,58,237,0.2);
          border-color: rgba(124,58,237,0.5);
          color: #c4b5fd;
          font-weight: 600;
        }

        /* ─── Ticket Cards ──────────────────────── */
        .tickets-list { display: flex; flex-direction: column; gap: 1rem; }

        .ticket-card {
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.07);
          border-radius: 16px;
          padding: 1.25rem 1.5rem;
          backdrop-filter: blur(12px);
          transition: transform 0.2s, box-shadow 0.2s;
          position: relative;
          overflow: hidden;
        }
        .ticket-card::before {
          content: '';
          position: absolute;
          left: 0; top: 0; bottom: 0;
          width: 4px;
          border-radius: 16px 0 0 16px;
        }
        .ticket-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .row-emergency::before { background: #6b7280; }
        .row-emergency { border-color: rgba(107,114,128,0.3); }
        .row-high::before { background: #ef4444; }
        .row-high { border-color: rgba(239,68,68,0.2); }
        .row-medium::before { background: #f59e0b; }
        .row-medium { border-color: rgba(245,158,11,0.2); }
        .row-low::before { background: #3b82f6; }
        .row-low { border-color: rgba(59,130,246,0.2); }

        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 0.85rem;
          flex-wrap: wrap;
          gap: 0.5rem;
        }
        .card-header-left { display: flex; align-items: center; gap: 0.75rem; }
        .card-header-right { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }

        .ref-id {
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.85rem;
          font-weight: 600;
          color: #c4b5fd;
          background: rgba(124,58,237,0.12);
          padding: 0.2rem 0.6rem;
          border-radius: 6px;
          border: 1px solid rgba(124,58,237,0.25);
        }
        .time-ago {
          font-size: 0.73rem;
          color: #475569;
        }

        /* ─── Badges ────────────────────────────── */
        .badge {
          font-size: 0.7rem;
          font-weight: 700;
          padding: 0.25rem 0.65rem;
          border-radius: 999px;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }
        .badge-emergency { background: rgba(107,114,128,0.2); color: #9ca3af; border: 1px solid rgba(107,114,128,0.4); }
        .badge-high      { background: rgba(239,68,68,0.15);  color: #f87171; border: 1px solid rgba(239,68,68,0.35); }
        .badge-medium    { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.35); }
        .badge-low       { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.35); }

        /* ─── Status Pills ───────────────────────── */
        .status-pill {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 0.2rem 0.7rem;
          border-radius: 999px;
          border: 1px solid;
        }
        .status-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
        }
        .status-open { color: #fbbf24; border-color: rgba(251,191,36,0.35); background: rgba(251,191,36,0.1); }
        .dot-open { background: #fbbf24; box-shadow: 0 0 6px #fbbf24; animation: pulse 2s infinite; }
        .status-inprogress { color: #60a5fa; border-color: rgba(96,165,250,0.35); background: rgba(96,165,250,0.1); }
        .dot-inprogress { background: #60a5fa; box-shadow: 0 0 6px #60a5fa; animation: pulse 2s infinite; }
        .status-resolved { color: #34d399; border-color: rgba(52,211,153,0.35); background: rgba(52,211,153,0.1); }
        .dot-resolved { background: #34d399; }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }

        /* ─── Caller Row ─────────────────────────── */
        .card-caller {
          display: flex;
          align-items: flex-start;
          gap: 0.65rem;
          margin-bottom: 0.85rem;
        }
        .caller-icon { font-size: 1.1rem; margin-top: 1px; }
        .caller-name {
          display: block;
          font-size: 0.95rem;
          font-weight: 600;
          color: #f1f5f9;
          margin-bottom: 0.15rem;
        }
        .caller-meta {
          font-size: 0.75rem;
          color: #64748b;
        }

        /* ─── Summary ────────────────────────────── */
        .card-summary {
          background: rgba(255,255,255,0.03);
          border-radius: 8px;
          padding: 0.7rem 0.9rem;
          margin-bottom: 0.75rem;
          border-left: 2px solid rgba(255,255,255,0.1);
        }
        .summary-text {
          font-size: 0.85rem;
          color: #cbd5e1;
          line-height: 1.55;
        }

        /* ─── Agent Checked ──────────────────────── */
        .card-agent-checked {
          display: flex;
          gap: 0.4rem;
          font-size: 0.78rem;
          color: #64748b;
          margin-bottom: 0.75rem;
          align-items: flex-start;
        }
        .agent-checked-label { color: #94a3b8; white-space: nowrap; }
        .agent-checked-text { color: #64748b; }

        /* ─── Footer & Buttons ───────────────────── */
        .card-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 0.5rem;
          padding-top: 0.75rem;
          border-top: 1px solid rgba(255,255,255,0.05);
        }
        .updated-at { font-size: 0.72rem; color: #475569; }
        .card-actions { display: flex; gap: 0.5rem; }

        .btn {
          border: none;
          border-radius: 8px;
          padding: 0.4rem 0.9rem;
          font-size: 0.78rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s;
          font-family: inherit;
        }
        .btn-inprogress {
          background: rgba(59,130,246,0.15);
          border: 1px solid rgba(59,130,246,0.3);
          color: #60a5fa;
        }
        .btn-inprogress:hover {
          background: rgba(59,130,246,0.25);
        }
        .btn-resolve {
          background: rgba(52,211,153,0.15);
          border: 1px solid rgba(52,211,153,0.3);
          color: #34d399;
        }
        .btn-resolve:hover {
          background: rgba(52,211,153,0.25);
        }

        /* ─── Empty / Loading / Error ─────────────── */
        .empty-state, .loading-state, .error-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          gap: 0.75rem;
        }
        .empty-icon { font-size: 3rem; opacity: 0.5; }
        .empty-title { font-size: 1.1rem; font-weight: 600; color: #94a3b8; }
        .empty-sub { font-size: 0.82rem; color: #475569; max-width: 300px; }
        .error-state .empty-title { color: #f87171; }

        .spinner {
          width: 36px; height: 36px;
          border: 3px solid rgba(124,58,237,0.2);
          border-top-color: #7c3aed;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <div className="page-wrap">
        {/* Header */}
        <div className="page-header">
          <div className="header-brand">
            <div className="brand-logo">🛡️</div>
            <div className="brand-text">
              <h1>ShopMitra · Support Tickets</h1>
              <p>ABC Local Store — Human Escalation Dashboard · Day 7</p>
            </div>
          </div>
          <div className="header-actions">
            <span className="refresh-info" suppressHydrationWarning>
              Auto-refresh every 30s &middot; Last: {mounted ? lastRefresh.toLocaleTimeString() : "--:--:--"}
            </span>
            <button
              className="btn-refresh"
              onClick={() => { setLoading(true); fetchTickets(); }}
            >
              ↺ Refresh
            </button>
          </div>
        </div>

        {/* Stats */}
        <StatsBanner tickets={tickets} />

        {/* Filters */}
        <div className="filter-bar">
          {["all", "open", "in_progress", "resolved"].map((s) => (
            <button
              key={s}
              className={`filter-btn ${filterStatus === s ? "active" : ""}`}
              onClick={() => setFilterStatus(s)}
            >
              {s === "all" ? "All" : s === "in_progress" ? "In Progress" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {/* Ticket List */}
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
            <p className="empty-sub">Loading escalation tickets…</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <div className="empty-icon">⚠️</div>
            <p className="empty-title">API Unavailable</p>
            <p className="empty-sub">{error}</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">✅</div>
            <p className="empty-title">No tickets found</p>
            <p className="empty-sub">
              {filterStatus === "all"
                ? "No escalation tickets yet. They appear here when ShopMitra creates one."
                : `No ${filterStatus.replace("_", " ")} tickets right now.`}
            </p>
          </div>
        ) : (
          <div className="tickets-list">
            {filtered.map((ticket) => (
              <EscalationCard
                key={ticket.ref_id}
                ticket={ticket}
                onUpdateStatus={handleUpdateStatus}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
