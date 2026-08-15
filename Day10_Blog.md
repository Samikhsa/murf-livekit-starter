# How I Built ShopMitra — An AI Voice Assistant for Indian Local Commerce

*I spent 10 days building a voice agent that helps small grocery store customers check prices, place orders, and get support — entirely by talking. Here's what I learned, what broke, and how you can build your own.*

---

## The Problem and the Users

India has over **12 million kirana (neighbourhood grocery) stores**. Most of them still take orders over phone calls. The store owner answers, checks stock mentally, quotes a price, and scribbles the order on paper. During peak hours, calls go unanswered. Customers give up.

I wanted to test a simple idea: **what if a voice AI agent could answer those calls — in Hindi, English, or Hinglish — check real prices, remember returning customers, and escalate to a human when it's out of its depth?**

That's ShopMitra — a voice assistant for **ABC Local Store**, a fictional kirana store I used as my test bed during the **10 Days of Voice Agents — VoiceForBharat Edition** challenge.

### Who is it for?

- **Customers** who call to ask "Do you have Basmati Rice? How much?" or "I want to return these biscuits."
- **Store owners** who miss calls during rush hours and want an agent that can handle the basics while they focus on in-person shoppers.
- **Why voice?** Because many Indian shoppers — especially in Tier 2/3 cities — are more comfortable calling than typing into an app. Voice removes the literacy and app-download barrier entirely.

---

## What the Voice Agent Does

ShopMitra can:

1. **Greet callers naturally** — new and returning customers get different greetings.
2. **Search a product catalogue** — "Do you have dal?" triggers a tool that looks up live prices and stock.
3. **Compute order totals** — "2 kg rice, 3 litres milk, and 1 kg sugar" → "Your total is ₹462."
4. **Remember customers across calls** — with consent. Next time Ramesh calls, ShopMitra says: "Welcome back! Last time you ordered rice — shall I check stock?"
5. **Make outbound restock calls** — "Hi Ramesh, time to restock your Basmati Rice 5 kg?"
6. **Escalate to humans** — payment disputes and order issues get a ticket with a reference ID, plus a Discord notification to the support team.
7. **Track call analytics** — success rates, failure taxonomy, and a live dashboard.
8. **Hand off to a specialist** — return/refund requests go to RefundMitra, a specialist agent with a different voice.

---

## How the System Works

![ShopMitra Architecture — Real-Time Audio Flow and Ecosystem](C:\Users\Taqueer Khan\.gemini\antigravity-ide\brain\fdba4dc2-db08-4f60-b60b-5d7c5c0cdac6\shopmitra_architecture_1786769016190.jpg)

The pipeline has four core components:

| Component | Technology | Role |
|-----------|-----------|------|
| **Speech-to-Text** | Deepgram Nova-3 (multilingual) | Converts the caller's voice to text |
| **LLM** | Google Gemini | Understands intent, decides which tool to call, generates a response |
| **Text-to-Speech** | **Murf Falcon** | Converts the response back to natural-sounding Indian English speech (55ms latency!) |
| **Real-Time Transport** | LiveKit | Streams audio bidirectionally between the user and the agent |

### Audio Flow

```
User speaks → Deepgram STT → Google Gemini LLM → Murf Falcon TTS → LiveKit → User hears
```

The LLM doesn't just generate text — it calls **function tools** (catalogue lookup, order total, escalation, handoff) based on what the caller says. The tools fetch real data and return structured results that the LLM speaks naturally.

### Supporting Infrastructure

- **SQLite database** — stores user profiles (with consent), escalation tickets, outbound call records, and call analytics. Zero PII in the analytics table.
- **aiohttp API server** — serves escalation and analytics data to the frontend dashboards.
- **Discord webhook** — pushes real-time notifications when a human-help ticket is created.
- **Twilio/Linphone SIP** — enables actual phone calls (inbound and outbound) via LiveKit's telephony bridge.
- **Next.js frontend** — browser-based voice UI plus admin dashboards for escalations and call analytics.

---

## The Most Important Features

### 🎙️ Indian Voice Powered by Murf Falcon

The agent uses **Murf Falcon** with the voice `Anisha` — an Indian English female voice. The specialist (RefundMitra) uses `Priya` so the customer *hears* the handoff. With 55ms model latency and ₹0.01 per 1,000 characters, Falcon was the obvious choice for a real-time voice agent.

```python
tts=murf.TTS(
    voice="Anisha",
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)
```

### 🧠 Memory for Returning Users

ShopMitra remembers callers across sessions — but only with consent. The system prompt enforces:

> *"BEFORE saving ANYTHING, explicitly ask the caller for permission."*

If Ramesh calls back a week later, the agent greets him by name and offers to reorder what he bought last time. If he says "forget me," the `forget_caller` tool wipes his record immediately.

### 🛒 Catalogue and Pricing Tools

Two function-call tools prevent the agent from ever hallucinating a price:

- **`check_catalogue`** — fuzzy-searches a 30-item product catalogue. Supports Hindi keywords like "दूध" (milk) and transliterations like "doodh."
- **`compute_order_total`** — calculates a line-item breakdown: "2 kg Basmati Rice at ₹240 + 3 litres Milk at ₹180 = ₹420."

If the catalogue file is missing or corrupt, the agent says *"I'm having trouble checking our system right now"* — it never goes silent and never invents a number.

### 📞 Outbound Restock Calls

The agent can proactively call customers to nudge them to restock. Every outbound call opens with a mandatory 3-part structure:

1. **WHO** — "This is ShopMitra calling from ABC Local Store."
2. **WHY** — "I'm calling to check if you'd like to restock Basmati Rice 5 kg."
3. **OPT-OUT** — "Say 'opt out' to stop these reminders."

Outcomes (connected, busy, voicemail, no answer) are tracked with retry rules. Opt-outs are permanent.

### 🚨 Human Escalation with Consent

Payment disputes and order issues trigger a human escalation flow:
1. Agent acknowledges empathetically.
2. Tells the caller *exactly* what will be shared (no payment credentials, no OTPs).
3. Asks for explicit permission.
4. Creates a ticket with a speakable reference ID (e.g., `ESC-20260812-0001`).
5. Fires a Discord notification to the support team.
6. Deduplicates — if the caller already has an open ticket, it reads back the existing ref ID.

### 📊 Call Analytics Dashboard

Every call session is tracked — start time, duration, channel (browser vs SIP), outcome (success/failed), and failure taxonomy (`user_hangup`, `incomplete_task`, `tool_error`, `no_response`). The dashboard at `/dashboard` shows KPI cards, success rate, failure breakdown, and a live call log. **Zero PII is stored** — no names, no phone numbers, no transcripts.

### 🔄 Specialist Agent Handoff

When a customer asks to return a product, the main agent hands off to **RefundMitra** — a specialist with:
- Its own focused system prompt (return policy, eligibility rules, refund timelines)
- A different Murf voice (`Priya` vs `Anisha`) so the user hears the switch
- Full conversation context carried over — the customer doesn't repeat themselves

```python
@function_tool
async def transfer_to_refund_specialist(self, context: RunContext):
    refund_agent = RefundAgent(
        chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
    )
    return refund_agent, "Let me connect you to our Returns and Refunds Specialist."
```

---

## Challenges and How I Overcame Them

### Challenge 1: Getting Outbound Calls to Actually Ring

Setting up SIP trunking was the hardest part of the entire challenge. I initially tried Twilio, but my free trial had exhausted its credits. After hours of debugging trunk configurations, I discovered I could use **Linphone** — a free SIP softphone — as an alternative.

**The fix:** I created a Linphone account, registered an outbound trunk in the LiveKit Cloud dashboard pointing to `sip.linphone.org` with TLS transport, and turned off "Media encryption mandatory" in the Linphone app settings. The call rang on my phone within seconds.

**Lesson:** Always have a fallback for third-party services. Free tiers expire at the worst possible time.

### Challenge 2: The Agent Hallucinating Prices

Early on, when a customer asked "How much is rice?", the LLM would confidently say "₹80 per kg" — a completely invented number. This is dangerous for a commerce agent.

**The fix:** I added hard guardrails in the system prompt:

> *"Never invent product prices — always use `check_catalogue`. If the tool returns an error, say you're having trouble."*

Combined with the `check_catalogue` tool's structured error handling, the agent now either gives a real price with a date stamp or admits it can't check. It never guesses.

### Challenge 3: Hinglish Detection and Response

Many Indian users naturally mix Hindi and English: "Bhaiya, rice ka price kya hai?" The agent initially responded in pure English to these mixed queries.

**The fix:** I configured Deepgram STT with `language="multi"` for multilingual detection, and added explicit rules in the system prompt:

> *"If the user mixes Hindi and English (Hinglish) → match their Hinglish style naturally. Hindi → Devanagari (नमस्ते), never romanized."*

The multilingual turn detector from LiveKit helped the agent know when the user had finished speaking, even when switching languages mid-sentence.

---

## How to Build and Run It Yourself

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- Node.js 18+
- pnpm (`npm install -g pnpm`)
- API keys for: [LiveKit](https://cloud.livekit.io/), [Murf AI](https://murf.ai/api/dashboard), [Deepgram](https://deepgram.com/), [Google AI Studio](https://aistudio.google.com/)

### Step 1: Clone the repo

```bash
git clone https://github.com/Samikhsa/murf-livekit-starter.git
cd murf-livekit-starter
```

### Step 2: Set up API keys

Create `.env.local` in both `backend/` and `frontend/` by copying from `.env.example`. You need:

| Variable | Where to get it |
|----------|----------------|
| `LIVEKIT_URL` | LiveKit Cloud dashboard |
| `LIVEKIT_API_KEY` | LiveKit Cloud dashboard |
| `LIVEKIT_API_SECRET` | LiveKit Cloud dashboard |
| `MURF_API_KEY` | [murf.ai/api/dashboard](https://murf.ai/api/dashboard) |
| `DEEPGRAM_API_KEY` | [deepgram.com](https://deepgram.com) |
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/) |

> ⚠️ **Never commit `.env.local` to Git.** It's already in `.gitignore`.

### Step 3: Install and run

```bash
# Terminal 1 — Backend
cd backend
uv sync
uv run python src/agent.py download-files   # first time only
uv run python src/agent.py dev

# Terminal 2 — Frontend
cd frontend
pnpm install
pnpm dev
```

Open **http://localhost:3000**, click **Start talking**, allow microphone access, and speak.

### Step 4: Test a conversation

Try these prompts:
- *"Do you have Basmati Rice?"* → triggers catalogue lookup
- *"I want 2 kg rice and 3 litres milk — how much?"* → triggers order total
- *"I was charged twice for my order"* → triggers human escalation
- *"I want to return these biscuits"* → triggers handoff to RefundMitra

---

## What I Would Improve Next

1. **Live inventory integration** — Replace the static JSON catalogue with a real API (e.g., a government commodity price feed or an actual POS system).
2. **WhatsApp channel** — Many Indian users prefer WhatsApp over phone calls. LiveKit supports WebRTC-based integrations that could bridge this.
3. **Multi-store support** — Let different kirana stores configure their own catalogue, branding, and voice.
4. **Consent audit log** — Currently consent is enforced at the LLM level. I'd add a server-side gate that rejects writes without a `consent_given` flag.
5. **End-to-end latency measurement** — Add p50/p95 latency tracking to the analytics dashboard using the [TTS Latency Benchmarker](https://github.com/sahilsgupta/tts-latency-benchmarker).

---

## Links

- 🔗 **GitHub Repository:** [github.com/Samikhsa/murf-livekit-starter](https://github.com/Samikhsa/murf-livekit-starter)
- 🎙️ **Murf Falcon TTS:** [murf.ai/falcon](https://murf.ai/falcon) — 55ms latency, 150+ voices, 35+ languages
- 📖 **Falcon 2 Documentation:** [murf.ai/api/docs/text-to-speech-models/falcon-2](https://murf.ai/api/docs/text-to-speech-models/falcon-2)
- 🧪 **LiveKit Voice AI Quickstart:** [docs.livekit.io/agents/start/voice-ai](https://docs.livekit.io/agents/start/voice-ai/)
- 🎤 **Murf LiveKit Starter (original template):** [github.com/murf-ai/murf-livekit-starter](https://github.com/murf-ai/murf-livekit-starter)

---

*Built during the **10 Days of Voice Agents — VoiceForBharat Edition**, powered by Murf Falcon TTS and LiveKit.*

*#VoiceForBharat*
