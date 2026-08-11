# Day 6 — Make Outbound Calls: ShopMitra Restock Nudge

A complete runbook for Day 6 of the **10 Days of Voice Agents** challenge.

**Track:** Local Commerce — **ShopMitra**  
**Outbound use case:** *Restock nudge* — the agent calls customers when their monthly grocery supply is running low.

---

## What Was Built

| Component | File | Description |
|-----------|------|-------------|
| Outbound dispatcher | `backend/src/outbound_caller.py` | Initiates calls via LiveKit SIP, records outcomes, applies retry rules |
| Trigger script | `backend/make_outbound_call.py` | One-shot CLI script to fire the outbound call |
| Agent integration | `backend/src/agent.py` | Detects `is_outbound`, injects mandatory opening, handles `opt_out_restock_calls` tool |
| Database | `backend/src/database.py` | `outbound_calls` table, `set_user_opt_out`, `is_user_opted_out` |
| SIP trunk config | `backend/trunk.json` | Twilio PSTN endpoint config for `lk sip outbound create` |

---

## Architecture

```
make_outbound_call.py
  └─ initiate_outbound_call(phone, name, item)
       ├─ database: check opt-out → record outbound_calls row
       ├─ LiveKit API: create room "outbound-<call_id>" (with metadata)
       │   └─ [if SIP trunk configured]
       │       LiveKit SIP: create_sip_participant()
       │           └─ Twilio SIP Trunk → PSTN → Customer Phone ☎️
       └─ Agent picks up the room → my_agent()
            ├─ Detects is_outbound = True (room name prefix / metadata)
            ├─ Injects mandatory opening instructions
            └─ Assistant speaks:
                 1. WHO  : "Hello Ramesh! This is ShopMitra calling from ABC Local Store."
                 2. WHY  : "I'm calling to check if you'd like to restock Basmati Rice 5kg."
                 3. OPT-OUT: "Say 'opt out' anytime to stop these reminders."
```

---

## Part A: Quick Test (No Telephony — Browser / Simulation Mode)

This lets you test the full outbound call flow **without** Twilio.

### Step 1 — Start the backend agent
```powershell
cd E:\Murf\murf-livekit-starter\backend
$env:PATH += ";$env:USERPROFILE\.local\bin"
uv run python src/agent.py dev
```

### Step 2 — Trigger the outbound call (creates a LiveKit room)
Open a **second** terminal:
```powershell
cd E:\Murf\murf-livekit-starter\backend
$env:PATH += ";$env:USERPROFILE\.local\bin"
uv run python make_outbound_call.py --phone +919876543210 --name "Ramesh Kumar" --item "Basmati Rice 5kg & Wheat Flour 10kg"
```

This creates a room named `outbound-call_XXXXXXXX` with outbound metadata. The agent joins automatically.

### Step 3 — Join the room as the customer (via frontend)
In the browser at `http://localhost:3000`, the agent will open with the mandatory 3-part greeting.

> **You'll hear:**  
> *"Hello Ramesh! This is ShopMitra calling from ABC Local Store. I'm calling to check if you would like to restock your monthly order of Basmati Rice 5kg & Wheat Flour 10kg. If you prefer not to receive these restock call reminders, just say opt out or let me know anytime."*

---

## Part B: Live Telephony — Twilio SIP Setup

This is required to actually ring a real phone.

### Step 1 — Get your Twilio details

1. Go to [https://console.twilio.com](https://console.twilio.com)
2. Note your **Account SID** and **Auth Token** (already in `.env.local`)
3. Go to **Phone Numbers → Manage → Active numbers** and copy your number (e.g. `+12025551234`)

### Step 2 — Download the `lk` CLI

```powershell
# Windows — download from GitHub releases
# https://github.com/livekit/livekit-cli/releases/latest
# Extract lk.exe to a folder on your PATH, or use the one in this repo
```

Or if you have Go installed:
```powershell
go install github.com/livekit/livekit-cli/cmd/lk@latest
```

### Step 3 — Edit `trunk.json`

Open `backend/trunk.json` and replace `+1XXXXXXXXXX` with your real Twilio number:

```json
{
  "name": "ShopMitra Twilio Outbound Trunk",
  "address": "outbound.pstn.twilio.com",
  "numbers": ["+12025551234"],
  "auth_username": "YOUR_TWILIO_API_KEY_SID",
  "auth_password": "YOUR_TWILIO_API_KEY_SECRET",
  "transport": 0
}
```

### Step 4 — Register the SIP trunk with LiveKit

```powershell
cd E:\Murf\murf-livekit-starter\backend
$env:LIVEKIT_URL="YOUR_LIVEKIT_URL"
$env:LIVEKIT_API_KEY="YOUR_LIVEKIT_API_KEY"
$env:LIVEKIT_API_SECRET="YOUR_LIVEKIT_API_SECRET"

lk sip outbound create --trunk-file trunk.json
```

> You'll see output like:
> ```
> SIPOutboundTrunk created: ST_xxxxxxxxxxxxxxxx
> ```

Copy that `ST_xxx...` value.

### Step 5 — Update `.env.local`

```env
TWILIO_PHONE_NUMBER=+12025551234         # your Twilio number
TO_PHONE_NUMBER=+919876543210            # the number to call (yours)
LIVEKIT_SIP_TRUNK_ID=ST_xxxxxxxxxxxxxxxx # from Step 4
```

Your phone should ring within ~5 seconds. Answer it to hear ShopMitra's mandatory opening!

---

## Part B.2: Free Alternative — Outbound Calls over Linphone

If your Twilio free trial is exhausted, you can use **Linphone** (a free SIP softphone) to receive outbound calls on your smartphone or desktop for free!

### Step 1 — Create a Linphone account
1. Go to [https://subscribe.linphone.org/register/email](https://subscribe.linphone.org/register/email) and create a free account.
2. Note your SIP username (e.g. `taqueerkhan`). Your SIP address will be `sip:<username>@sip.linphone.org`.

### Step 2 — Create the Outbound Trunk in LiveKit Cloud
1. Log in to [https://cloud.livekit.io](https://cloud.livekit.io)
2. In your project sidebar, click **Telephony** → **SIP Trunks**.
3. Click **Create Outbound Trunk**.
4. Set the details:
   - **Name:** `linphone-trunk`
   - **Address / Hostname:** `sip.linphone.org`
   - **Transport:** `TLS` (`SIP_TRANSPORT_TLS`)
   - **Numbers:** `sip:<your-linphone-username>`
5. Click Save. Copy the generated **TRUNK ID** (starts with `ST_...`).

### Step 3 — Update `backend/.env.local`
```env
LIVEKIT_SIP_OUTBOUND_TRUNK_ID=ST_xxxxxxxxxxxxxxxx   # Trunk ID from Step 2
TO_PHONE_NUMBER=sip:your-linphone-username@sip.linphone.org
```

### Step 4 — Set up the Linphone App
1. Download **Linphone** on your phone (iOS / Android) or PC from [linphone.org](https://www.linphone.org/en/).
2. Log in with your `linphone.org` credentials.
3. Grant microphone permission.
4. **Crucial setting:** Open Linphone **Settings → Calls → Advanced calls settings** and turn **"Media encryption mandatory" OFF**.

### Step 5 — Make the call!
1. Start the agent:
   ```powershell
   cd E:\Murf\murf-livekit-starter\backend
   uv run python src/agent.py dev
   ```
2. In a second terminal, dial your Linphone user:
   ```powershell
   cd E:\Murf\murf-livekit-starter\backend
   uv run python make_outbound_call.py --to your-linphone-username
   ```
3. Your Linphone app will ring! Answer it to interact with ShopMitra.

---

## Part C: Advanced — Outcome Handling

The `OutcomeTracker` in `outbound_caller.py` handles all four challenging outbound outcomes:

| Outcome | What Happens | Retry Rule |
|---------|-------------|-----------|
| `CONNECTED` | Full conversation proceeds | No retry needed |
| `NO_ANSWER` | Call not picked up | Retry up to 2× every 30 min |
| `BUSY` | Line busy | Retry up to 3× every 15 min |
| `VOICEMAIL` | Voicemail detected | Leave brief message, no retries |
| `IMMEDIATE_HANGUP` | User hung up in <5s | Mark do-not-call for today |
| `OPTED_OUT` | User said "stop calling" | `opted_out=1` set permanently in DB |

### Testing outcome simulation

```powershell
# Simulate no answer (triggers retry scheduling)
uv run python make_outbound_call.py --phone +919876543210 --outcome NO_ANSWER

# Simulate busy line
uv run python make_outbound_call.py --phone +919876543210 --outcome BUSY

# Simulate voicemail
uv run python make_outbound_call.py --phone +919876543210 --outcome VOICEMAIL

# Simulate immediate hangup
uv run python make_outbound_call.py --phone +919876543210 --outcome IMMEDIATE_HANGUP
```

### Checking call records in the database

```bash
# From backend/ folder
sqlite3 data/shopmitra.db

.headers on
.mode column

# View all outbound calls
SELECT call_id, customer_name, phone_number, status, outcome_notes, next_retry_at
FROM outbound_calls ORDER BY updated_at DESC;

# View opt-out status
SELECT user_id, name, opted_out FROM users WHERE opted_out = 1;
```

---

## Mandatory 3-Part Opening (Day 6 Requirement)

The system prompt enforces this structure in every outbound call's **first two sentences**:

```
Hello [Customer Name]! This is ShopMitra calling from ABC Local Store.
I'm calling to check if you would like to restock your monthly order of [Product].
If you prefer not to receive these restock call reminders, just say "opt out" or let me know anytime.
```

1. **WHO** — "This is ShopMitra calling from ABC Local Store"
2. **WHY** — "I'm calling to check if you'd like to restock [product]"  
3. **OPT-OUT** — "Say 'opt out' to stop these reminders"

---

## Opt-Out Flow

When the customer says "opt out", "stop calling", or "don't call again":

1. Agent immediately calls `opt_out_restock_calls(user_id)` tool
2. `database.set_user_opt_out(user_id, True)` sets `opted_out = 1` in SQLite
3. Agent confirms: *"Understood! I have updated your preferences and disabled restock call reminders."*
4. Future calls to `initiate_outbound_call()` will check `is_user_opted_out()` and skip silently

---

## Day 6 Checklist

- [x] Outbound use case defined: restock nudge based on past order rhythm
- [x] `outbound_caller.py` integrates LiveKit SIP / Twilio SIP trunk
- [x] `make_outbound_call.py` trigger script created
- [x] Mandatory 3-part opening: WHO + WHY + OPT-OUT in first 2 sentences
- [x] `opt_out_restock_calls` tool: agent disables future calls on request
- [x] `outbound_calls` table records every attempt with outcome and retry time
- [x] Outcome handling: NO_ANSWER, BUSY, VOICEMAIL, IMMEDIATE_HANGUP all handled
- [ ] Live test: phone rings and agent delivers the opening *(fill in LIVEKIT_SIP_TRUNK_ID)*
- [ ] LinkedIn post with video recorded and submitted

---

*Part of the 10 Days of Voice Agents challenge — powered by Murf Falcon TTS.*
