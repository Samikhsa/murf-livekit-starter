# Day 9 — Hand Off to a Specialist Agent

A complete runbook and overview for Day 9 of the **10 Days of Voice Agents** challenge.

**Track:** Local Commerce — **ShopMitra**  
**Use Case:** *Returns & Refunds Specialist Agent Handoff*

---

## What Was Built

| Component | File | Description |
|-----------|------|-------------|
| Refund Specialist Prompt | `backend/src/agent.py` | `REFUND_SPECIALIST_PROMPT` — focused system prompt for RefundMitra covering return policy, eligibility rules, and refund timelines |
| `RefundAgent` class | `backend/src/agent.py` | Specialist agent extending `Agent`, uses Murf voice `Priya`, implements `on_enter()` for auto-introduction |
| Handoff Tool | `backend/src/agent.py` | `transfer_to_refund_specialist` — `@function_tool` on `Assistant` that constructs the specialist and passes conversation history |
| Routing Rules | `backend/src/agent.py` | `AGENT HANDOFF — DAY 9 RULES` section added to `SYSTEM_PROMPT` telling the main agent when to hand off vs. escalate vs. answer itself |

---

## Architecture

```
User / Caller (Browser or SIP)
     │
     ▼
Assistant (ShopMitra — main agent)
     │
     ├─ Normal query ──────────────────────────────────────────────────────►  Answers directly
     │   (product search, store hours, delivery info)                         (no handoff)
     │
     ├─ Payment/order dispute ─────────────────────────────────────────────►  create_escalation
     │   (charged incorrectly, order never arrived)                           (human ticket)
     │
     └─ Return / Refund request ──► transfer_to_refund_specialist tool
                                              │
                                              ▼  (chat_ctx carried over)
                                    RefundAgent (RefundMitra)
                                      - on_enter() fires automatically
                                      - Introduces itself by name
                                      - Continues conversation with full context
                                      - Murf voice: Priya (distinct from Anisha)
```

---

## How Agent Handoff Works

### 1. Main agent announces the transfer
The main agent (`Assistant`) calls `transfer_to_refund_specialist`. The tool returns:
```python
return refund_agent, "Let me connect you to our Returns and Refunds Specialist."
```
LiveKit speaks the announcement string, then immediately swaps the active agent.

### 2. Conversation history is carried over
```python
refund_agent = RefundAgent(
    chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
    ...
)
```
The specialist receives the full conversation history (minus the main agent's system instructions), so the customer does **not** have to repeat themselves.

### 3. Specialist introduces itself
`on_enter()` fires automatically when the session transfers:
```python
async def on_enter(self) -> None:
    await self.session.generate_reply(
        instructions="Introduce yourself as RefundMitra..."
    )
```

### 4. Distinct voice
- **ShopMitra (main):** Murf voice `Anisha`  
- **RefundMitra (specialist):** Murf voice `Priya`  

The user hears a voice change — making the handoff audible.

---

## Specialist Scope (RefundMitra)

| Topic | Handled by |
|---|---|
| Product search / pricing | Main Agent (ShopMitra) |
| Store hours / delivery | Main Agent (ShopMitra) |
| **Returning a product** | ✅ **RefundMitra** |
| **Refund request / timeline** | ✅ **RefundMitra** |
| **Return eligibility questions** | ✅ **RefundMitra** |
| Payment / billing dispute | `create_escalation` (human ticket) |
| Order never arrived | `create_escalation` (human ticket) |

---

## Return & Refund Policy (Known by Specialist)

- Items returnable within **2 days** of purchase
- Item must be in original **sealed condition** with receipt
- Refunds processed in **3–5 business days**
- **Perishables** (dairy, fresh produce) NOT eligible unless defective
- **Sale / clearance items** NOT eligible
- **Defective or damaged items** always eligible — no exceptions

---

## Routing Decision Table

| Customer says | Main agent action |
|---|---|
| "Do you have Basmati Rice?" | Calls `check_catalogue` → answers (no handoff) |
| "What are your store timings?" | Answers from knowledge (no handoff) |
| "I want to return these biscuits" | Announces handoff → `transfer_to_refund_specialist` |
| "Can I get a refund for this?" | Announces handoff → `transfer_to_refund_specialist` |
| "I was charged twice" | `create_escalation` (payment dispute) |
| "My order never arrived" | `create_escalation` (order dispute) |

---

## How to Test

### 1. Start Backend
```powershell
cd E:\Murf\murf-livekit-starter\backend
uv run python src/agent.py dev
```

### 2. Start Frontend
```powershell
cd E:\Murf\murf-livekit-starter\frontend
pnpm dev
```

### 3. Test Path 1 — Normal question (stays with main agent)
> "Do you have Basmati Rice in stock?"

Expected: ShopMitra answers. No handoff.

### 4. Test Path 2 — Refund question (triggers handoff)
> "I bought some biscuits yesterday and I want to return them."

Expected:
1. ShopMitra says: *"Let me connect you to our Returns and Refunds Specialist."*
2. Voice switches to **Priya**
3. RefundMitra introduces herself and asks for product + purchase date — without making the customer repeat themselves.

---

## Day 9 Checklist

- [x] Chosen specialist for Local Commerce track: **Returns & Refunds Specialist**
- [x] Created `RefundAgent` class with its own system prompt (`REFUND_SPECIALIST_PROMPT`)
- [x] Specialist has a smaller, focused scope vs. main agent
- [x] Added `transfer_to_refund_specialist` handoff tool to `Assistant`
- [x] Conversation context (`chat_ctx`) passed to specialist — no repeat questions
- [x] Main agent announces handoff before switching (`"Let me connect you to our Returns and Refunds Specialist."`)
- [x] Specialist introduces itself in `on_enter()` and continues conversation
- [x] Distinct Murf voice for specialist (`Priya` vs `Anisha`) — audible switch
- [x] Routing rules in `SYSTEM_PROMPT` — main agent only hands off when appropriate
- [x] Tested both paths: normal question stays, refund question hands off
- [x] Code committed and pushed to both remote repositories

---

*Part of the 10 Days of Voice Agents challenge — powered by LiveKit & Murf Falcon TTS.*
