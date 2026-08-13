"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Script from "next/script";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CallStats {
  total: number;
  successful: number;
  failed: number;
  pending: number;
  success_rate: number;
}

interface CallRecord {
  call_id: string;
  room_name: string;
  channel: "browser" | "sip";
  outcome: "success" | "failed" | "pending";
  failure_type: string | null;
  duration_seconds: number;
  started_at: string;
  ended_at: string | null;
}

// ─── Config ───────────────────────────────────────────────────────────────────

const API_BASE = "http://localhost:8765";
const POLL_INTERVAL = 5000; // 5 seconds

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function formatRelativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatFailureType(ft: string | null): string {
  if (!ft) return "—";
  return ft.replace(/_/g, " ");
}

// ─── Main Dashboard Component ─────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState<CallStats | null>(null);
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [chartReady, setChartReady] = useState(false);
  const chartRef = useRef<HTMLCanvasElement>(null);
  const chartInstanceRef = useRef<unknown>(null);

  // ── Fetch data ──────────────────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, callsRes] = await Promise.all([
        fetch(`${API_BASE}/api/calls/stats`),
        fetch(`${API_BASE}/api/calls?limit=20`),
      ]);
      if (!statsRes.ok || !callsRes.ok) throw new Error("API error");
      const [statsData, callsData] = await Promise.all([
        statsRes.json(),
        callsRes.json(),
      ]);
      setStats(statsData);
      setCalls(callsData.calls ?? []);
      setLastUpdated(new Date());
      setError(null);
    } catch {
      setError("Cannot reach agent backend — make sure it is running on port 8765.");
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Initial load + poll ─────────────────────────────────────────────────────

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ── Chart ───────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!chartReady || !stats || !chartRef.current) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Chart = (window as any).Chart;
    if (!Chart) return;

    if (chartInstanceRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (chartInstanceRef.current as any).destroy();
    }

    const ctx = chartRef.current.getContext("2d");
    chartInstanceRef.current = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Successful", "Failed", "Pending"],
        datasets: [
          {
            data: [stats.successful, stats.failed, stats.pending],
            backgroundColor: ["#10b981", "#ef4444", "#6366f1"],
            borderColor: ["#059669", "#dc2626", "#4f46e5"],
            borderWidth: 2,
            hoverOffset: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: function (context: { label: string; parsed: number }) {
                const total = stats.total;
                const val = context.parsed;
                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : "0.0";
                return ` ${context.label}: ${val} (${pct}%)`;
              },
            },
          },
        },
        animation: {
          animateRotate: true,
          duration: 800,
        },
      },
    });
  }, [stats, chartReady]);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Load Chart.js from CDN */}
      <Script
        src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"
        onLoad={() => setChartReady(true)}
        strategy="afterInteractive"
      />

      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
          background: #070711;
        }

        .dash-root {
          min-height: 100vh;
          background: #070711;
          color: #e2e8f0;
          font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
          padding: 100px 24px 48px;
        }

        /* ── Header ─────────────────────────────────────────────── */
        .dash-header {
          max-width: 1200px;
          margin: 0 auto 40px;
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
        }
        .dash-title-block {}
        .dash-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: rgba(99,102,241,0.15);
          border: 1px solid rgba(99,102,241,0.3);
          border-radius: 99px;
          padding: 4px 12px;
          font-size: 11px;
          font-weight: 600;
          color: #818cf8;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          margin-bottom: 12px;
        }
        .dash-badge-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: #818cf8;
          animation: pulse 2s infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(0.85); }
        }
        .dash-title {
          font-size: 32px;
          font-weight: 800;
          letter-spacing: -0.03em;
          background: linear-gradient(135deg, #e2e8f0 30%, #818cf8);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        .dash-subtitle {
          margin-top: 6px;
          font-size: 14px;
          color: #64748b;
        }
        .dash-refresh {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: #475569;
        }
        .dash-refresh-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          background: #10b981;
          animation: pulse 2s infinite;
        }

        /* ── Main grid ──────────────────────────────────────────── */
        .dash-grid {
          max-width: 1200px;
          margin: 0 auto;
          display: grid;
          gap: 24px;
        }

        /* ── Stat cards row ─────────────────────────────────────── */
        .stat-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
        }
        @media (max-width: 900px) {
          .stat-row { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 520px) {
          .stat-row { grid-template-columns: 1fr; }
        }

        .stat-card {
          background: rgba(15,17,35,0.9);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 16px;
          padding: 24px;
          position: relative;
          overflow: hidden;
          transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .stat-card:hover {
          transform: translateY(-2px);
          border-color: rgba(255,255,255,0.12);
        }
        .stat-card::before {
          content: '';
          position: absolute;
          inset: 0;
          opacity: 0;
          transition: opacity 0.3s;
        }
        .stat-card:hover::before { opacity: 1; }

        .stat-card-total::before   { background: radial-gradient(circle at top left, rgba(99,102,241,0.08), transparent 60%); }
        .stat-card-success::before { background: radial-gradient(circle at top left, rgba(16,185,129,0.08), transparent 60%); }
        .stat-card-failed::before  { background: radial-gradient(circle at top left, rgba(239,68,68,0.08), transparent 60%); }
        .stat-card-rate::before    { background: radial-gradient(circle at top left, rgba(251,191,36,0.08), transparent 60%); }

        .stat-icon {
          font-size: 20px;
          margin-bottom: 16px;
          display: block;
        }
        .stat-label {
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #64748b;
          margin-bottom: 8px;
        }
        .stat-value {
          font-size: 42px;
          font-weight: 800;
          letter-spacing: -0.04em;
          line-height: 1;
        }
        .stat-value-total   { color: #818cf8; }
        .stat-value-success { color: #10b981; }
        .stat-value-failed  { color: #ef4444; }
        .stat-value-rate    { color: #fbbf24; }

        .stat-sub {
          margin-top: 8px;
          font-size: 12px;
          color: #475569;
        }

        /* ── Bottom row: chart + table ──────────────────────────── */
        .bottom-row {
          display: grid;
          grid-template-columns: 320px 1fr;
          gap: 24px;
          align-items: start;
        }
        @media (max-width: 900px) {
          .bottom-row { grid-template-columns: 1fr; }
        }

        /* ── Chart card ─────────────────────────────────────────── */
        .chart-card {
          background: rgba(15,17,35,0.9);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 16px;
          padding: 28px;
        }
        .card-title {
          font-size: 13px;
          font-weight: 700;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          color: #94a3b8;
          margin-bottom: 24px;
        }
        .chart-wrapper {
          position: relative;
          height: 220px;
          margin-bottom: 24px;
        }
        .chart-center-text {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          pointer-events: none;
        }
        .chart-center-num {
          font-size: 36px;
          font-weight: 800;
          letter-spacing: -0.04em;
          color: #e2e8f0;
        }
        .chart-center-label {
          font-size: 11px;
          color: #64748b;
          margin-top: 2px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .legend-list {
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .legend-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 13px;
        }
        .legend-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .legend-dot {
          width: 10px; height: 10px;
          border-radius: 3px;
          flex-shrink: 0;
        }
        .legend-name { color: #94a3b8; }
        .legend-val  { font-weight: 700; color: #e2e8f0; }

        /* ── History table card ─────────────────────────────────── */
        .table-card {
          background: rgba(15,17,35,0.9);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 16px;
          padding: 28px;
          overflow: hidden;
        }
        .table-header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }
        .table-count-pill {
          background: rgba(99,102,241,0.15);
          border: 1px solid rgba(99,102,241,0.25);
          border-radius: 99px;
          padding: 2px 10px;
          font-size: 11px;
          color: #818cf8;
          font-weight: 600;
        }
        .table-scroll {
          overflow-x: auto;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        thead th {
          text-align: left;
          padding: 0 16px 12px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: #475569;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        tbody tr {
          border-bottom: 1px solid rgba(255,255,255,0.04);
          transition: background 0.15s;
        }
        tbody tr:last-child { border-bottom: none; }
        tbody tr:hover { background: rgba(255,255,255,0.025); }
        tbody td {
          padding: 14px 16px;
          color: #94a3b8;
          vertical-align: middle;
        }
        .td-mono {
          font-family: 'CommitMono', monospace;
          font-size: 11px;
          color: #64748b;
          max-width: 140px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        /* Outcome badge */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 10px;
          border-radius: 99px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.03em;
          text-transform: uppercase;
          border: 1px solid transparent;
        }
        .badge-success {
          background: rgba(16,185,129,0.12);
          border-color: rgba(16,185,129,0.25);
          color: #10b981;
        }
        .badge-failed {
          background: rgba(239,68,68,0.12);
          border-color: rgba(239,68,68,0.25);
          color: #ef4444;
        }
        .badge-pending {
          background: rgba(99,102,241,0.12);
          border-color: rgba(99,102,241,0.25);
          color: #818cf8;
        }
        .badge-browser {
          background: rgba(56,189,248,0.1);
          border-color: rgba(56,189,248,0.2);
          color: #38bdf8;
          font-size: 10px;
          padding: 2px 8px;
        }
        .badge-sip {
          background: rgba(251,146,60,0.1);
          border-color: rgba(251,146,60,0.2);
          color: #fb923c;
          font-size: 10px;
          padding: 2px 8px;
        }

        /* ── Skeleton / empty / error states ───────────────────── */
        .empty-state {
          text-align: center;
          padding: 60px 24px;
          color: #475569;
        }
        .empty-state-icon { font-size: 40px; margin-bottom: 12px; }
        .empty-state-text { font-size: 14px; }

        .error-banner {
          max-width: 1200px;
          margin: 0 auto 24px;
          background: rgba(239,68,68,0.1);
          border: 1px solid rgba(239,68,68,0.25);
          border-radius: 12px;
          padding: 14px 20px;
          color: #fca5a5;
          font-size: 13px;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .skeleton {
          background: rgba(255,255,255,0.05);
          border-radius: 8px;
          animation: shimmer 1.5s infinite;
        }
        @keyframes shimmer {
          0%   { opacity: 0.5; }
          50%  { opacity: 1; }
          100% { opacity: 0.5; }
        }

        .privacy-note {
          max-width: 1200px;
          margin: 24px auto 0;
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 11px;
          color: #374151;
        }
      `}</style>

      <div className="dash-root">
        {/* ── Page header ──────────────────────────────────────────── */}
        <div className="dash-header">
          <div className="dash-title-block">
            <div className="dash-badge">
              <span className="dash-badge-dot" />
              Live · Auto-refreshes every 5s
            </div>
            <h1 className="dash-title">📊 ShopMitra Call Analytics</h1>
            <p className="dash-subtitle">
              ABC Local Store · Local Commerce Track · Day 8
            </p>
          </div>
          {lastUpdated && (
            <div className="dash-refresh">
              <span className="dash-refresh-dot" />
              Last updated {formatRelativeTime(lastUpdated.toISOString())}
            </div>
          )}
        </div>

        {/* ── Error banner ─────────────────────────────────────────── */}
        {error && (
          <div className="error-banner">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <div className="dash-grid">
          {/* ── Stat cards ─────────────────────────────────────────── */}
          <div className="stat-row">
            <StatCard
              icon="📞"
              label="Total Calls"
              value={stats?.total ?? 0}
              valueClass="stat-value-total"
              sub="All sessions recorded"
              cardClass="stat-card-total"
              loading={loading}
            />
            <StatCard
              icon="✅"
              label="Successful"
              value={stats?.successful ?? 0}
              valueClass="stat-value-success"
              sub="Caller got what they needed"
              cardClass="stat-card-success"
              loading={loading}
            />
            <StatCard
              icon="❌"
              label="Failed"
              value={stats?.failed ?? 0}
              valueClass="stat-value-failed"
              sub="No useful outcome reached"
              cardClass="stat-card-failed"
              loading={loading}
            />
            <StatCard
              icon="📈"
              label="Success Rate"
              value={stats ? `${stats.success_rate}%` : "—"}
              valueClass="stat-value-rate"
              sub={stats?.pending ? `${stats.pending} call(s) still in progress` : "Of completed calls"}
              cardClass="stat-card-rate"
              loading={loading}
            />
          </div>

          {/* ── Bottom row ─────────────────────────────────────────── */}
          <div className="bottom-row">
            {/* Donut chart */}
            <div className="chart-card">
              <div className="card-title">Outcome Distribution</div>
              <div className="chart-wrapper">
                {stats && stats.total > 0 ? (
                  <>
                    <canvas ref={chartRef} id="outcomeChart" />
                    <div className="chart-center-text">
                      <div className="chart-center-num">{stats.total}</div>
                      <div className="chart-center-label">total</div>
                    </div>
                  </>
                ) : (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      height: "100%",
                      color: "#374151",
                      fontSize: "13px",
                    }}
                  >
                    No data yet
                  </div>
                )}
              </div>
              <ul className="legend-list">
                <li className="legend-item">
                  <span className="legend-left">
                    <span className="legend-dot" style={{ background: "#10b981" }} />
                    <span className="legend-name">Successful</span>
                  </span>
                  <span className="legend-val">{stats?.successful ?? 0}</span>
                </li>
                <li className="legend-item">
                  <span className="legend-left">
                    <span className="legend-dot" style={{ background: "#ef4444" }} />
                    <span className="legend-name">Failed</span>
                  </span>
                  <span className="legend-val">{stats?.failed ?? 0}</span>
                </li>
                <li className="legend-item">
                  <span className="legend-left">
                    <span className="legend-dot" style={{ background: "#6366f1" }} />
                    <span className="legend-name">Pending</span>
                  </span>
                  <span className="legend-val">{stats?.pending ?? 0}</span>
                </li>
              </ul>
            </div>

            {/* Call history table */}
            <div className="table-card">
              <div className="table-header-row">
                <div className="card-title" style={{ marginBottom: 0 }}>
                  Recent Calls
                </div>
                <span className="table-count-pill">{calls.length} shown</span>
              </div>
              {calls.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📭</div>
                  <div className="empty-state-text">
                    {loading
                      ? "Loading call history..."
                      : "No calls recorded yet. Make your first call!"}
                  </div>
                </div>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Duration</th>
                        <th>Channel</th>
                        <th>Outcome</th>
                        <th>Failure Type</th>
                        <th>Room</th>
                      </tr>
                    </thead>
                    <tbody>
                      {calls.map((call) => (
                        <tr key={call.call_id}>
                          <td>{formatRelativeTime(call.started_at)}</td>
                          <td>{formatDuration(call.duration_seconds)}</td>
                          <td>
                            <span
                              className={
                                call.channel === "sip"
                                  ? "badge badge-sip"
                                  : "badge badge-browser"
                              }
                            >
                              {call.channel === "sip" ? "📞 SIP" : "🌐 Browser"}
                            </span>
                          </td>
                          <td>
                            <span
                              className={`badge badge-${call.outcome}`}
                            >
                              {call.outcome === "success" && "✅ "}
                              {call.outcome === "failed" && "❌ "}
                              {call.outcome === "pending" && "⏳ "}
                              {call.outcome}
                            </span>
                          </td>
                          <td
                            style={{
                              color:
                                call.failure_type ? "#ef4444" : "#374151",
                              fontSize: "12px",
                              textTransform: "capitalize",
                            }}
                          >
                            {formatFailureType(call.failure_type)}
                          </td>
                          <td className="td-mono">{call.room_name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Privacy note ─────────────────────────────────────────── */}
        <div className="privacy-note">
          <span>🔒</span>
          <span>
            Privacy protected — no caller names, phone numbers, or conversation
            transcripts are displayed on this dashboard.
          </span>
        </div>
      </div>
    </>
  );
}

// ─── StatCard sub-component ───────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  valueClass,
  sub,
  cardClass,
  loading,
}: {
  icon: string;
  label: string;
  value: number | string;
  valueClass: string;
  sub: string;
  cardClass: string;
  loading: boolean;
}) {
  return (
    <div className={`stat-card ${cardClass}`}>
      <span className="stat-icon">{icon}</span>
      <div className="stat-label">{label}</div>
      {loading ? (
        <div
          className="skeleton"
          style={{ height: "42px", width: "80px", marginBottom: "8px" }}
        />
      ) : (
        <div className={`stat-value ${valueClass}`}>{value}</div>
      )}
      <div className="stat-sub">{sub}</div>
    </div>
  );
}
