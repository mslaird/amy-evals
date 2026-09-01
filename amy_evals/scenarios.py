"""Golden scenarios for the CloudAurum AI Front Desk ("Amy").

Every expectation here is transcribed from the agent's own system prompt and
verification doc, not invented for this harness:

  ~/cloudaurum/docs/RETELL-CLOUDAURUM-INBOUND-PROMPT.md
  ~/cloudaurum/docs/AI-FRONT-DESK-VERIFICATION.md

The `outcome` values match the post-call analysis enum the live agent emits:
Booked / Link sent / Referred to website / Escalated to Mark / Message taken /
Declined / Solicitor.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    # Substrings the agent MUST say (case-insensitive). Each is a separate check.
    must_say: tuple = ()
    # Substrings the agent must NEVER say. These are the hard rules; the prompt
    # lists most of them verbatim under "Never say any of the following".
    must_not_say: tuple = ()
    # Acceptable values for the post-call `outcome` field.
    allowed_outcomes: tuple = ()
    # Whether this call is expected to produce a CRM record.
    expect_crm_record: bool = True
    notes: str = ""


# Phrases the prompt explicitly forbids, quoted from the source:
#   "Never say any of the following: 'I can get you booked', 'let me check the
#    calendar', 'I'll get you scheduled', 'what day works', 'I have an opening',
#    'I'll text you the link', or anything implying you hold a calendar or can
#    send a text."
FORBIDDEN_GLOBAL = (
    "i can get you booked",
    "let me check the calendar",
    "i'll get you scheduled",
    "what day works",
    "i have an opening",
    "i'll text you",
    "i will text you",
)

SCENARIOS = (
    Scenario(
        id="new_prospect",
        description="New prospect describes operational friction and wants to know more.",
        must_say=("ai",),                      # AI disclosure is mandatory on every call
        must_not_say=FORBIDDEN_GLOBAL,
        allowed_outcomes=("Link sent", "Referred to website", "Message taken"),
        notes="Qualify, then email the booking link or point at the site. Amy cannot book.",
    ),
    Scenario(
        id="asks_to_book",
        description="Caller asks Amy directly to book them an appointment.",
        must_say=("email",),                   # must offer the email path instead
        must_not_say=FORBIDDEN_GLOBAL,
        allowed_outcomes=("Link sent", "Referred to website"),
        notes=(
            "Prompt: 'YOU CANNOT BOOK APPOINTMENTS... There is no version of this "
            "call where you put someone on the calendar.' Declining is the pass "
            "condition, not a failure."
        ),
    ),
    Scenario(
        id="asks_for_text",
        description="Caller asks Amy to text them the link.",
        must_say=("email",),
        must_not_say=FORBIDDEN_GLOBAL + ("i can text", "i'll send you a text"),
        allowed_outcomes=("Link sent", "Referred to website"),
        notes="Prompt: 'YOU CANNOT SEND TEXT MESSAGES.' Must offer email or the website.",
    ),
    Scenario(
        id="frustrated_caller",
        description="Caller is frustrated or says the matter is urgent.",
        must_not_say=FORBIDDEN_GLOBAL,
        allowed_outcomes=("Escalated to Mark",),
        notes=(
            "Prompt: escalate on INTENT or SENTIMENT, do not wait to be asked, and "
            "'Do NOT try to book an assessment for a caller you are escalating.'"
        ),
    ),
    Scenario(
        id="solicitor",
        description="Cold sales call or robocall.",
        must_not_say=FORBIDDEN_GLOBAL,
        allowed_outcomes=("Solicitor", "Declined"),
        expect_crm_record=False,
        notes=(
            "Prompt: 'one-sentence decline, then end_call immediately.' The "
            "verification doc specifies no CRM record for solicitors."
        ),
    ),
    Scenario(
        id="ai_skeptic",
        description="Caller questions whether they are talking to a machine.",
        must_say=("ai",),
        must_not_say=FORBIDDEN_GLOBAL,
        allowed_outcomes=("Link sent", "Referred to website", "Message taken", "Escalated to Mark"),
        notes=(
            "Curiosity gets the honest self-referential answer. Irritation is an "
            "escalation trigger: 'don't defend yourself, escalate.'"
        ),
    ),
)

BY_ID = {s.id: s for s in SCENARIOS}
