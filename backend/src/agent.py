import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    inference,
    tokenize,
    room_io,
)
from livekit.plugins import murf, silero, deepgram, noise_cancellation, openai
try:
    from livekit.plugins import google
except Exception as exc:
    google = None
from livekit.plugins.turn_detector.multilingual import MultilingualModel


try:
    from . import database  # when imported as a package (uv run / pytest)
    from . import catalogue  # Day 5 -- product catalogue tools
    from . import escalation_notifier  # Day 7 -- Discord webhook
    from . import escalation_api        # Day 7 -- HTTP dashboard API
except ImportError:
    import database  # when run directly as a script
    import catalogue  # when run directly as a script
    import escalation_notifier  # type: ignore[no-redef]
    import escalation_api        # type: ignore[no-redef]

logger = logging.getLogger("agent")


def _load_backend_env() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=False)


_load_backend_env()


def get_llm_provider() -> dict[str, str]:
    """Return the configured LLM provider settings for the backend."""
    _load_backend_env()
    if os.getenv("OPENROUTER_API_KEY"):
        return {
            "provider": "openrouter",
            "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            "base_url": "https://openrouter.ai/api/v1",
        }
    if os.getenv("GOOGLE_API_KEY"):
        return {
            "provider": "google",
            "model": os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash"),
        }

    return {
        "provider": "google",
        "model": os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash"),
    }




# ---------------------------------------------------------------------------
# System prompt — ShopMitra, Local Commerce track
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
IDENTITY
- Name: ShopMitra
- Role: AI Voice Assistant for ABC Local Store
- Tone: Friendly, professional, conversational.

OBJECTIVES
1. Help customers find products.
2. Provide store information such as timings, location, delivery options, and return policy.
3. Help customers with shopping-related queries and connect them to a human representative when verification is required.
4. Remember returning customers and personalise every interaction using their saved profile.

MEMORY & PERSONALISATION — CRITICAL RULES
- At the very start of every call, call the `lookup_caller` tool with the caller's user_id.
- If the tool returns a known caller, greet them warmly by name and reference something from their last visit.
  Example: "Welcome back, Ramesh! Last time you ordered rice in bulk — shall I check if we have stock today?"
- If the tool returns a new caller, use the default greeting below.
- During the conversation, learn: the caller's name, language preference, past orders,
  usual quantities, and preferred delivery slot.
- BEFORE saving ANYTHING, explicitly ask the caller for permission:
  "Is it okay if I remember your preferences for next time?"
- If they say NO or are hesitant — do NOT call `save_caller_info`. Drop the information completely.
- Only call `save_caller_info` after receiving clear verbal consent.
- You also have a `forget_caller` tool. If a caller ever asks to be forgotten, call it immediately
  and confirm: "Done — I have deleted all your saved information."

KNOWLEDGE
Knows:
- Store timings: Mon–Sat 9 AM to 9 PM, Sun 10 AM to 6 PM
- Product categories: Groceries, Dairy, Pulses, Grains, Snacks, Beverages, Household items
- Delivery areas: Within 5 km of the store
- Return & exchange policy: Within 2 days with receipt for sealed items
- Store contact: +91-98765-43210
- FAQs

Does NOT know:
- Live inventory unless verified via the `check_catalogue` tool
- Real-time order status unless verified
- Payment transaction details

CATALOGUE & PRICING TOOLS — CRITICAL RULES
- Whenever a customer asks about a product, its price, or whether it is in stock —
  ALWAYS call `check_catalogue` FIRST. Never guess or invent a price.
- Always state when the price was last updated:
  "As of today's data, [product] is ₹[price] per [unit]."
- If `check_catalogue` returns error status — say aloud:
  "I'm having trouble checking our system right now. Let me connect you to our
  store staff who can help you directly."
- If a product shows in_stock = false — say: "Unfortunately [product] is out of
  stock right now. Would you like me to suggest something similar?"
- If quantity_available < 5 and the item is in stock — proactively mention:
  "We only have a few left — would you like to reserve some?"
- When a customer wants to know the cost of multiple items, call `compute_order_total`.
  Speak the total naturally: "Your total for [items] comes to ₹[total]."
- If the caller is a returning customer and their past_orders mention items you found
  in the catalogue — you may say: "You've ordered this before — shall I add it again?"
- For voice: do NOT read out raw numbers as JSON. Round prices to whole rupees.

LANGUAGE & SCRIPT
Always write every language in its own native script.
- Hindi → Devanagari (नमस्ते), never romanized (never "namaste").
- Same rule for all non-English languages.
Always detect the user's language automatically and reply in the same language.
- If the user speaks English → reply in English only.
- If the user speaks Hindi → reply only in Hindi using Devanagari script.
- If the user mixes Hindi and English (Hinglish) → match their Hinglish style naturally.
- Never translate unless asked.
- Prioritise matching the user's language over defaulting to English.

GUARDRAILS
- Never confirm an order unless officially verified.
- Never promise a delivery date that has not been confirmed.
- Never invent product prices — always use `check_catalogue`.
- Never claim a product is in stock without calling `check_catalogue`.
- Never ask for or process OTP, PIN, CVV, passwords, or payment credentials.
- Never pretend to know information you do not have.
- If information cannot be verified, politely explain the limitation and offer to connect the customer with a human representative.

STYLE
- Friendly and natural.
- Short responses (1–3 sentences).
- Avoid long paragraphs.
- Suitable for spoken conversation.
- If the user is silent for several seconds, politely ask if they are still there.

DEFAULT FIRST GREETING (new inbound callers only)
"Hello! Welcome to ABC Local Store. I'm ShopMitra, your AI shopping assistant. I can help you find products, check our timings, explain delivery options, and answer your shopping queries. How may I help you today?"

OUTBOUND CALL RULES — DAY 6 MANDATORY OPENING (CRITICAL)
- If this is an OUTBOUND CALL (indicated in system note):
  You MUST open the call immediately with the exact 3-part structure in your first two sentences:
  1. WHO: State clearly who is calling ("This is ShopMitra calling from ABC Local Store...")
  2. WHY: State clearly why you are calling ("...I'm calling to check if you would like to restock your regular monthly order of [product].")
  3. OPT-OUT: State clearly how to make calls stop ("...If you prefer not to receive these restock call reminders, just say opt out or let me know anytime.")
- If the caller says "opt out", "stop calling me", "don't call again", or asks to stop reminders —
  IMMEDIATELY call the `opt_out_restock_calls` tool and confirm:
  "Understood! I have updated your preferences and disabled restock call reminders."

HUMAN ESCALATION — DAY 7 CRITICAL RULES
Two situations ALWAYS require escalating to a human team member. Do NOT try to resolve these yourself:

  Situation 1 — PAYMENT or REFUND DISPUTE (urgency: high)
    Triggers: caller says they were charged incorrectly, double-charged, want a refund,
    dispute a transaction, or complain about billing.

  Situation 2 — ORDER or DELIVERY DISPUTE (urgency: medium)
    Triggers: caller says their order never arrived, wrong items were delivered,
    or the delivery is significantly late.

When you detect one of these situations:
  a. Acknowledge empathetically: "I understand this is frustrating. This needs a human team
     member to look into it properly."
  b. Tell the caller EXACTLY what you want to share:
     "I'd like to send your name, the type of issue, what I've already checked, and your
     preferred follow-up method to our support team. I will NOT share any payment details,
     OTPs, or private numbers."
  c. Ask for explicit permission:
     "May I create a support request with these details so our team can follow up with you?"
  d. If caller says YES — call `create_escalation`.
  e. If caller says NO — do NOT create any request. Say:
     "Of course, I understand. You can reach our team directly at +91-98765-43210."
  f. After the ticket is created, read the reference ID CLEARLY and SLOWLY:
     "Your support ticket reference is [ref_id]. Please keep this handy."
  g. Give an honest next step: "Our team will follow up with you via [method] within
     24 hours during store hours (Mon–Sat 9 AM to 9 PM)."
  h. Do NOT promise immediate callback unless it is certain.

Also available: `check_escalation_status` — if the caller asks about an existing ticket.
"""



# ---------------------------------------------------------------------------
# Assistant — voice agent with memory tools
# ---------------------------------------------------------------------------

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # Memory tools
    # ------------------------------------------------------------------

    @function_tool
    async def lookup_caller(
        self,
        context: RunContext,
        user_id: str,
    ):
        """
        Look up a caller's saved profile from the database.

        Call this at the very start of every session, before saying anything.
        Pass the user_id that was provided in the session context.

        Returns a dict with the caller's name, language preference, and saved
        facts (past_orders, usual_quantities, preferred_delivery_slot), or a
        message indicating this is a new caller.

        Args:
            user_id: The unique identifier for this caller (provided at session start).
        """
        logger.info("lookup_caller called for user_id=%s", user_id)
        record = database.get_user(user_id)
        if record:
            return {
                "status": "returning_caller",
                "user_id": record["user_id"],
                "name": record["name"],
                "language_preference": record["language_preference"],
                "facts": record["facts"],
                "last_interaction": record["last_interaction"],
            }
        return {
            "status": "new_caller",
            "user_id": user_id,
            "message": "No record found. This is a new caller — use the default greeting.",
        }

    @function_tool
    async def save_caller_info(
        self,
        context: RunContext,
        user_id: str,
        name: str,
        language_preference: str,
        past_orders: str,
        usual_quantities: str,
        preferred_delivery_slot: str,
    ):
        """
        Save or update the caller's profile in the database.

        IMPORTANT: Only call this tool AFTER the caller has verbally agreed to
        have their information saved. If they decline, do NOT call this tool.

        Args:
            user_id: The unique identifier for this caller.
            name: The caller's name as they introduced themselves.
            language_preference: Language the caller prefers — one of: 'en', 'hi', 'hinglish'.
            past_orders: Comma-separated list of products/categories they ordered or asked about.
            usual_quantities: How much they typically buy (e.g. '5 kg rice, 2 L milk').
            preferred_delivery_slot: Their preferred delivery time — one of: 'morning', 'afternoon', 'evening'.
        """
        logger.info("save_caller_info called for user_id=%s name=%s", user_id, name)
        facts = {
            "past_orders": past_orders,
            "usual_quantities": usual_quantities,
            "preferred_delivery_slot": preferred_delivery_slot,
        }
        database.upsert_user(
            user_id,
            name,
            language_preference=language_preference,
            facts=facts,
        )
        return {
            "status": "saved",
            "message": f"Profile for {name} saved successfully.",
        }

    @function_tool
    async def forget_caller(
        self,
        context: RunContext,
        user_id: str,
    ):
        """
        Delete a caller's profile from the database when they ask to be forgotten.

        Call this immediately when the caller explicitly requests their data be deleted.
        After calling this tool, confirm to the caller that their data has been erased.

        Args:
            user_id: The unique identifier for the caller to be deleted.
        """
        logger.info("forget_caller called for user_id=%s", user_id)
        deleted = database.delete_user(user_id)
        if deleted:
            return {
                "status": "deleted",
                "message": "Record deleted. The caller's data has been fully erased.",
            }
        return {
            "status": "not_found",
            "message": "No record found for this caller — nothing to delete.",
        }

    @function_tool
    async def opt_out_restock_calls(
        self,
        context: RunContext,
        user_id: str,
    ):
        """
        Opt out the caller from receiving future outbound restock call reminders.

        Call this immediately when the caller requests to opt out or stop calls.
        After calling this tool, confirm to the caller that restock calls are disabled.

        Args:
            user_id: The unique identifier for the caller.
        """
        logger.info("opt_out_restock_calls called for user_id=%s", user_id)
        database.set_user_opt_out(user_id, True)
        return {
            "status": "opted_out",
            "message": "User successfully opted out of restock call reminders.",
        }

    # ------------------------------------------------------------------
    # Day 5 — Catalogue & pricing tools
    # ------------------------------------------------------------------


    @function_tool
    async def check_catalogue(
        self,
        context: RunContext,
        query: str,
        category: str | None = None,
    ):
        """
        Search the ABC Store product catalogue for a product by name, category,
        or keyword.

        Call this tool EVERY TIME a customer asks about:
        - Whether a product is available or in stock
        - The price of any product
        - What products are in a given category

        Do NOT invent prices or stock information — always call this tool first.

        Args:
            query:    The product name or keyword to search for
                      (e.g. "rice", "basmati", "दूध", "dal").
            category: Optional category filter. One of: Groceries, Dairy,
                      Pulses, Grains, Snacks, Beverages, Household.
                      Leave empty to search all categories.

        Returns up to 5 matching products with name, price in ₹, unit,
        stock status, and the date the price was last updated.
        Speak the price as: "As of [date], [product] is ₹[price] per [unit]."
        If the tool returns an error, say you're having trouble and offer to
        connect the customer to store staff.
        """
        logger.info("check_catalogue called: query=%r category=%r", query, category)
        try:
            result = catalogue.search_products(query, category=category)
            logger.info(
                "check_catalogue: %d results for %r", result["total_found"], query
            )
            return result
        except catalogue.CatalogueUnavailableError as exc:
            logger.error("check_catalogue: catalogue unavailable — %s", exc)
            return {
                "error": "catalogue_unavailable",
                "message": (
                    "The product catalogue is temporarily unavailable. "
                    "Tell the customer you're having trouble checking the system "
                    "and offer to connect them to a human store representative."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("check_catalogue: unexpected error — %s", exc)
            return {
                "error": "catalogue_unavailable",
                "message": (
                    "Unexpected error loading catalogue. "
                    "Tell the customer you're having trouble and offer to help them another way."
                ),
            }

    @function_tool
    async def compute_order_total(
        self,
        context: RunContext,
        items_json: str,
    ):
        """
        Calculate the total cost of a customer's order.

        Call this when the customer has selected one or more products and wants
        to know how much they owe before confirming.

        Args:
            items_json: A JSON-encoded list of objects, each with:
                        - "product_id": the product id from check_catalogue
                          (e.g. "rice_basmati_1kg")
                        - "quantity": number of units the customer wants
                          (e.g. 2 for 2 kg if the unit is "1 kg")

                        Example:
                        '[{"product_id": "rice_basmati_1kg", "quantity": 2},
                          {"product_id": "milk_full_cream_1l", "quantity": 3}]'

        Returns a line-item breakdown and grand total in Rs.
        Speak it naturally, e.g.:
        "Your total is Rs 350 -- that's 2 kg Basmati Rice at Rs 240 and 3 litres
         of Milk at Rs 180, as of today's prices."
        If an item is unknown, tell the customer that item wasn't found and
        give a total for the rest.
        """
        logger.info("compute_order_total called with items_json=%r", items_json)
        try:
            items = json.loads(items_json)
            if not isinstance(items, list):
                raise ValueError("items_json must be a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("compute_order_total: bad items_json -- %s", exc)
            return {
                "error": "invalid_input",
                "message": "Could not parse the item list. Please try again.",
            }

        try:
            result = catalogue.compute_order_total(items)
            logger.info(
                "compute_order_total: grand_total=Rs%d, %d line items, %d unknown",
                result["grand_total_inr"],
                len(result["line_items"]),
                len(result["unknown_ids"]),
            )
            return result
        except catalogue.CatalogueUnavailableError as exc:
            logger.error("compute_order_total: catalogue unavailable -- %s", exc)
            return {
                "error": "catalogue_unavailable",
                "message": (
                    "The catalogue is temporarily unavailable. "
                    "Tell the customer you're unable to compute the total right now "
                    "and offer to connect them to store staff."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("compute_order_total: unexpected error -- %s", exc)
            return {
                "error": "catalogue_unavailable",
                "message": "Unexpected error. Tell the customer you're having trouble.",
            }

    # ------------------------------------------------------------------
    # Day 7 -- Human Escalation tools
    # ------------------------------------------------------------------

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        user_id: str,
        caller_name: str,
        reason_type: str,
        summary: str,
        urgency: str,
        language: str,
        follow_up_method: str,
        agent_checked: str,
    ):
        """
        Create a human-help escalation ticket when a caller has a payment dispute
        or an order/delivery dispute that the agent cannot resolve.

        IMPORTANT: Only call this tool AFTER the caller has given verbal consent
        to share their information with the support team. If they decline, do NOT call.

        This tool will:
        - Check for an existing open ticket (to avoid duplicates)
        - Save the ticket to the database
        - Send a notification to the human support team via Discord
        - Return a reference ID to read aloud to the caller

        Args:
            user_id:          The caller's user_id from the session.
            caller_name:      The caller's name as they introduced themselves.
            reason_type:      One of: 'payment_dispute' | 'order_dispute'.
            summary:          A SHORT, factual description of the problem
                              (2-3 sentences max). Do NOT include OTPs, PINs,
                              account numbers, phone numbers, or passwords.
            urgency:          One of: 'low' | 'medium' | 'high' | 'emergency'.
                              Use 'high' for payment disputes, 'medium' for order disputes.
            language:         Language code the caller spoke in: 'en', 'hi', 'hinglish', etc.
            follow_up_method: How the caller wants to be contacted: 'call' | 'whatsapp' | 'sms'.
            agent_checked:    Brief note on what the agent already verified
                              (e.g. 'Checked order status -- not found in system').
        """
        logger.info(
            "create_escalation called: user_id=%s reason=%s urgency=%s",
            user_id, reason_type, urgency,
        )

        # Validate reason_type
        valid_reasons = ("payment_dispute", "order_dispute")
        if reason_type not in valid_reasons:
            return {
                "error": "invalid_reason_type",
                "message": f"reason_type must be one of: {valid_reasons}",
            }

        # Deduplication -- check for an existing open ticket
        existing = database.find_open_escalation(user_id, reason_type)
        if existing:
            logger.info(
                "Duplicate escalation detected: existing ref_id=%s", existing["ref_id"]
            )
            return {
                "status": "duplicate",
                "ref_id": existing["ref_id"],
                "message": (
                    f"An open support request already exists for this issue. "
                    f"Reference ID: {existing['ref_id']}. "
                    f"Our team is already working on it."
                ),
                "next_steps": (
                    f"Tell the caller: 'You already have an open ticket — {existing['ref_id']}. "
                    f"Our team will follow up via {existing.get('follow_up_method', 'call')} "
                    f"within 24 hours.'"
                ),
            }

        # Create the ticket
        try:
            ticket = database.create_escalation(
                user_id=user_id,
                caller_name=caller_name,
                reason_type=reason_type,
                summary=summary,
                urgency=urgency,
                language=language,
                follow_up_method=follow_up_method,
                agent_checked=agent_checked,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("create_escalation: DB error -- %s", exc)
            return {
                "error": "database_error",
                "message": "Could not save the escalation. Please try again or direct the caller to +91-98765-43210.",
            }

        # Fire-and-forget Discord notification
        try:
            escalation_notifier.post_escalation_sync(ticket)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Discord notification failed (non-fatal): %s", exc)

        ref_id = ticket["ref_id"]
        logger.info("Escalation created successfully: ref_id=%s", ref_id)
        return {
            "status": "created",
            "ref_id": ref_id,
            "message": f"Support ticket created successfully. Reference ID: {ref_id}.",
            "next_steps": (
                f"Tell the caller their reference ID is '{ref_id}' (spell it out clearly). "
                f"Explain: 'Our team will follow up with you via {follow_up_method} within "
                f"24 hours during store hours — Monday to Saturday, 9 AM to 9 PM.'"
            ),
        }

    @function_tool
    async def check_escalation_status(
        self,
        context: RunContext,
        ref_id: str,
    ):
        """
        Check the current status of an existing escalation/support ticket.

        Call this when the caller asks about the status of their support request
        or mentions a reference ID they received earlier.

        Args:
            ref_id: The ticket reference ID (e.g. 'ESC-20260812-0001').
        """
        logger.info("check_escalation_status called: ref_id=%s", ref_id)
        ticket = database.get_escalation(ref_id.strip().upper())
        if not ticket:
            return {
                "status": "not_found",
                "message": (
                    f"No ticket found with reference ID {ref_id}. "
                    "Please double-check the ID or contact us at +91-98765-43210."
                ),
            }

        status = ticket["status"]
        status_messages = {
            "open":        "Your ticket is open and waiting to be assigned to a team member.",
            "in_progress": "Your ticket is currently being reviewed by our support team.",
            "resolved":    "Your ticket has been resolved. If you still have concerns, please call us at +91-98765-43210.",
        }
        return {
            "ref_id":   ticket["ref_id"],
            "status":   status,
            "reason":   ticket["reason_type"],
            "urgency":  ticket["urgency"],
            "created":  ticket["created_at"],
            "updated":  ticket["updated_at"],
            "message":  status_messages.get(status, f"Status: {status}."),
        }


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


# ---------------------------------------------------------------------------
# Day 7 -- Start the escalation HTTP API as a background task
# ---------------------------------------------------------------------------

_escalation_api_task: "asyncio.Task | None" = None


async def _maybe_start_escalation_api() -> None:
    """Start the escalation API server once, on first worker process."""
    global _escalation_api_task
    if _escalation_api_task is None or _escalation_api_task.done():
        import asyncio as _asyncio
        _escalation_api_task = _asyncio.ensure_future(escalation_api.start_api_server())
        logger.info("Escalation API server task started.")


def _derive_user_id(ctx: JobContext) -> str:
    """
    Derive a stable caller ID for this session.

    Priority:
      1. First non-empty participant identity in the room (set by your auth layer)
      2. The room name as a stable fallback (works for the Day 4 demo)
    """
    for p in ctx.room.remote_participants.values():
        if p.identity:
            return p.identity
    return ctx.room.name or "unknown_caller"


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Day 7 -- ensure the escalation HTTP API is running
    await _maybe_start_escalation_api()

    _load_backend_env()
    provider = get_llm_provider()

    # Parse room metadata or name to determine if this is an outbound call
    room_metadata = {}
    if ctx.room.metadata:
        try:
            room_metadata = json.loads(ctx.room.metadata)
        except Exception:  # noqa: BLE001
            pass

    is_outbound = (
        room_metadata.get("call_type") == "outbound"
        or ctx.room.name.startswith("outbound")
    )
    user_id = room_metadata.get("user_id") or ctx.room.name or "demo_user"
    customer_name = room_metadata.get("customer_name", "Ramesh")
    restock_item = room_metadata.get("restock_item", "Basmati Rice 5kg & Wheat Flour 10kg")

    logger.info("Session user_id derived as: %s (outbound=%s)", user_id, is_outbound)

    if provider["provider"] == "openrouter":
        logger.info("Using OpenRouter LLM provider with model %s", provider["model"])
        llm_instance = openai.LLM.with_openrouter(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=provider["model"],
        )
    else:
        google_model = provider.get("model", os.getenv("GOOGLE_LLM_MODEL", "gemini-2.0-flash"))
        logger.info("Using Google Gemini LLM provider with model %s", google_model)
        llm_instance = google.LLM(model=google_model)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=llm_instance,
        tts=murf.TTS(
            voice="Anisha",  # no locale prefix — Murf auto-selects accent per language
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # --- DEBUG LOGGING ---
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        logger.info(f"USER SAID: {msg}")

    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        logger.info(f"AGENT REPLIED: {msg}")

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        logger.info(f"AGENT STATE CHANGED: {ev}")

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        logger.info(f"USER STATE CHANGED: {ev}")
    # --- END DEBUG LOGGING ---

    await ctx.connect()

    if is_outbound:
        initial_message = (
            f"[SYSTEM NOTE — not spoken aloud]\n"
            f"This is an OUTBOUND RESTOCK CALL to {customer_name!r}.\n"
            f"The caller's user_id for this session is: {user_id!r}.\n"
            f"Target Restock Product: {restock_item!r}.\n\n"
            f"DAY 6 MANDATORY OPENING REQUIREMENT:\n"
            f"In your very first turn, you MUST open the call with these 3 exact points in your first 2 sentences:\n"
            f"1. WHO: Say 'Hello {customer_name}! This is ShopMitra calling from ABC Local Store...'\n"
            f"2. WHY: Say '...I'm calling to check if you would like to restock your monthly supply of {restock_item}.'\n"
            f"3. OPT-OUT: Say 'If you prefer not to receive these restock call reminders, just say opt out or let me know anytime.'\n\n"
            f"Begin speaking immediately now."
        )
    else:
        # Inbound call flow
        initial_message = (
            f"[SYSTEM NOTE — not spoken aloud]\n"
            f"The caller's user_id for this session is: {user_id!r}.\n"
            f"Your very first action must be to call the `lookup_caller` tool with this user_id.\n"
            f"Do not greet the caller until you have the result."
        )

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Trigger the first agent turn with the session injection
    await session.generate_reply(instructions=initial_message)



if __name__ == "__main__":
    cli.run_app(server)
