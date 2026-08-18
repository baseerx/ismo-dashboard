"""Reading what the question is actually asking for.

Tool-calling by a 7B local model is workable but not dependable: it will
sometimes answer "how many casual leaves do I have left" from memory, invent a
number, or call the right tool with the wrong dates. Since every HR answer here
is a factual claim about someone's record, the classification and the dates are
decided in code, and the model is used for the parts it is good at - phrasing
an answer, and reading policy prose out of the retrieved manual.

The model still gets a tool-calling turn, but only for questions this module
does not recognise, so a miss degrades to "slower and vaguer", never to "wrong
number stated confidently".
"""

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional

from app.chat.dates import DateRange, parse_date_range


class Intent(str, Enum):
    PROFILE = "profile"                    # who am I, what is my ERP id
    LEAVE_BALANCE = "leave_balance"        # how many days do I have left
    LEAVE_HISTORY = "leave_history"        # which leaves did I take
    ATTENDANCE_DAY = "attendance_day"      # was I on time today
    ATTENDANCE_RANGE = "attendance_range"  # attendance over a period
    OFFICIAL_WORK = "official_work"        # tours / official duty
    REPORT = "report"                      # produce a downloadable file
    POLICY = "policy"                      # answer from the HR manual (RAG)
    NAVIGATE = "navigate"                  # take me to a page
    SMALLTALK = "smalltalk"                # greetings, thanks, "what can you do"
    FALLBACK = "fallback"                  # let the model decide


class Subject(str, Enum):
    LEAVE = "leave"
    ATTENDANCE = "attendance"
    OFFICIAL_WORK = "official_work"


# --------------------------------------------------------------- vocabulary

ATTENDANCE_WORDS = (
    "attendance", "check in", "check-in", "checkin", "check out", "check-out",
    "checkout", "punch", "present", "absent", "late", "early out", "timing",
    "arrival", "in time", "on time", "working hours", "punctual", "punctuality",
    "come in", "came in", "arrive", "arrived", "clock in", "clock out",
)

LEAVE_WORDS = (
    "leave", "leaves", "vacation", "holiday request", "time off", "off day",
    "days off", "day off", "off days",
)

BALANCE_WORDS = (
    "balance", "remaining", "left", "quota", "entitle", "entitlement",
    "available", "how many", "how much", "still have",
)

HISTORY_WORDS = (
    "history", "record", "records", "applied", "application", "applications",
    "request", "requests", "taken", "list", "show", "detail", "details",
    "status", "pending", "approved", "rejected", "summary", "when did i",
)

OFFICIAL_WORK_WORDS = ("official work", "official duty", "tour", "official visit", "field visit")

REPORT_WORDS = ("report", "download", "export", "excel", "spreadsheet", "xlsx", "pdf", "sheet", "print")

POLICY_WORDS = (
    "policy", "policies", "rule", "rules", "regulation", "procedure", "sop",
    "manual", "clause", "chapter", "eligible", "eligibility", "allowed",
    "entitled under", "what does the", "according to", "handbook", "guideline",
    "notice period", "probation", "increment", "promotion", "grade", "hierarchy",
    "definition", "explain", "criteria", "process for",
)

# Only phrasings that unambiguously ask to *go somewhere*. "show me my
# attendance" is a question about data and must not land here, so "show me" is
# not a navigation verb — "open", "go to" and "... page" are.
_GO = r"(?:open|go to|take me to|navigate to|launch)"

NAVIGATE_PATTERNS = (
    (r"\bapply\b[^?]*\bleave\b|\bleave\b[^?]*\bapply\b|\bleave (?:form|application form)\b",
     "leave_application"),
    (rf"{_GO}\b.*\bofficial work\b|\bofficial work\b.*\b(?:form|page)\b", "official_work"),
    (rf"{_GO}\b.*\battendance\b|\battendance\b.*\b(?:page|screen|tab)\b", "attendance"),
    (rf"{_GO}\b.*\b(?:profile|my account)\b|\bprofile\b.*\bpage\b", "profile"),
    (rf"{_GO}\b.*\bleave history\b|\bleave history\b.*\bpage\b", "leave_history"),
    (rf"{_GO}\b.*\bholidays?\b|\bholidays?\b.*\bpage\b", "public_holidays"),
    (rf"{_GO}\b.*\bdashboard\b|\bdashboard\b.*\bpage\b", "dashboard"),
)

# "how do I apply for leave?" wants the policy explained; "apply for leave"
# wants the form. Both offer the link; only the first answers from the manual.
ASKING_HOW = (
    r"^\s*(?:how|what|where|why|which|when|can i|do i|is there|are there)\b",
    r"\?\s*$",
)

# Greetings and "what can you do". Handled without retrieval or a model call:
# a vector store always returns its nearest passages, so "hello" would
# otherwise come back as an unprompted summary of the onboarding chapter.
COURTESY_PATTERNS = (
    r"^\s*(?:thanks|thank you|thankyou|shukriya|ok|okay|k|great|cool|nice|good|perfect)\b[\s!.,]*$",
    r"^\s*(?:bye|goodbye|see you|khuda hafiz|allah hafiz)\b[\s!.,]*$",
)

SMALLTALK_PATTERNS = COURTESY_PATTERNS + (
    r"^\s*(?:hi|hey|hello|hallo|yo|salam|salaam|assalam[ou]?\s*alaikum|good\s+(?:morning|afternoon|evening))\b[\s!.,]*$",
    r"\bwhat can you do\b", r"\bwhat do you do\b", r"\bwho are you\b",
    r"\bhow can you help\b", r"\bwhat are you\b", r"\bhelp me\b",
    r"^\s*help\s*[?!.]*$", r"\bwhat questions can i ask\b",
)

PROFILE_PATTERNS = (
    r"\bwho am i\b", r"\bmy name\b", r"\bwhat'?s my name\b", r"\bmy erp\b",
    r"\bmy employee id\b", r"\bmy (section|department|designation|grade)\b",
    r"\bmy (profile|details|info|information)\b", r"\bam i (an )?admin\b",
)

# Third-person references. Used only to notice that a question is about
# somebody else, so a non-administrator can be told no instead of being
# silently handed their own record.
OTHER_PERSON_PATTERNS = (
    r"\berp\s*(?:id|no\.?|number)?\s*[:#]?\s*(\d{2,6})\b",
    r"\bemployee\s*(?:id|no\.?|number)?\s*[:#]?\s*(\d{2,6})\b",
)

THIRD_PERSON_WORDS = (
    r"\bhis\b", r"\bher\b", r"\btheir\b", r"\bhim\b", r"\bthem\b",
    r"\bsomeone else\b", r"\banother employee\b", r"\bother employees?\b",
    r"\beveryone\b", r"\ball employees\b", r"\bstaff\b",
)

FIRST_PERSON = (r"\bmy\b", r"\bmine\b", r"\bi\b", r"\bme\b", r"\bam i\b", r"\bdid i\b", r"\bhave i\b")

# Words that look like names to the "of <name>" pattern but never are.
NOT_A_NAME = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "how", "what", "where", "why", "which", "when", "who", "whom", "was",
    "were", "did", "does", "give", "send", "please", "kindly", "generate",
    "download", "export", "financial", "fiscal", "quarter", "weekend",
    "summary", "status", "pending", "approved", "rejected", "late", "absent",
    "present", "checked", "check", "punch", "time", "office", "hours",
    "leave", "leaves", "attendance", "report", "reports", "balance", "today",
    "yesterday", "week", "month", "year", "policy", "excel", "pdf", "the",
    "my", "me", "mine", "casual", "medical", "annual", "official", "work",
    "days", "day", "detail", "details", "history", "record", "records", "all",
    "this", "last", "current", "previous", "past", "employee", "employees",
    "staff", "everyone", "sick", "earned", "hajj", "umrah", "maternity",
    "paternity", "study", "short", "compensatory", "marriage", "shift",
    # Function words, so "leaves of kashif" yields "kashif" rather than
    # "of kashif" and the employee lookup gets a clean term.
    "of", "for", "about", "from", "to", "and", "have", "has", "had", "many",
    "much", "say", "says", "show", "open", "take", "apply", "give", "his",
    "her", "their", "them", "page", "screen", "tab", "form", "dashboard",
    "please", "want", "need", "get", "see", "view", "tell", "list",
}


@dataclass
class Understanding:
    intent: Intent
    question: str
    subject: Optional[Subject] = None
    date_range: Optional[DateRange] = None
    leave_type_hint: Optional[str] = None
    report_format: Optional[str] = None       # "excel" | "pdf" | None
    navigate_to: Optional[str] = None
    wants_report: bool = False
    # "thanks" / "bye" deserve a line, not the whole capability menu.
    is_courtesy: bool = False
    # Filled when the question is about somebody other than the asker.
    target_erp_id: Optional[int] = None
    target_name_candidates: List[str] = field(default_factory=list)
    about_someone_else: bool = False

    @property
    def needs_data(self) -> bool:
        return self.intent in {
            Intent.LEAVE_BALANCE,
            Intent.LEAVE_HISTORY,
            Intent.ATTENDANCE_DAY,
            Intent.ATTENDANCE_RANGE,
            Intent.OFFICIAL_WORK,
            Intent.REPORT,
        }


def _mentions(text: str, words) -> bool:
    return any(word in text for word in words)


def _matches_any(text: str, patterns) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _report_format(text: str) -> Optional[str]:
    if re.search(r"\b(excel|xlsx|spreadsheet|sheet|csv)\b", text):
        return "excel"
    if re.search(r"\bpdf\b", text):
        return "pdf"
    return None


def _name_candidates(text: str) -> List[str]:
    """Phrases that might name a colleague.

    Deliberately generous: whatever comes back is checked against the employee
    table before it is believed, so a false positive costs a lookup and
    nothing more.
    """
    candidates: List[str] = []

    for pattern in (
        r"\b(?:of|for|about|belonging to)\s+((?:[A-Za-z.]{2,}\s*){1,4})",
        r"\b([A-Za-z.]{3,}(?:\s+[A-Za-z.]{2,}){0,3})'s\b",
        r"\bemployee\s+([A-Za-z.]{3,}(?:\s+[A-Za-z.]{2,}){0,3})",
        # A bare name: "Kashif Mehmood attendance last week", "MR. NASIR leaves".
        r"\b((?:[A-Z][a-z.]{2,}|[A-Z]{3,})(?:\s+(?:[A-Z][a-z.]{1,}|[A-Z]{2,})){0,3})\b",
    ):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            phrase = " ".join(
                word for word in match.group(1).split()
                if word.lower().strip(".,") not in NOT_A_NAME
            ).strip()
            if len(phrase) >= 3:
                candidates.append(phrase)

    # Longest first: "kashif mehmood" is a better lookup than "kashif".
    return sorted(dict.fromkeys(candidates), key=len, reverse=True)[:3]


def _leave_type_hint(text: str) -> Optional[str]:
    """The words in front of "leave", which `resolve_leave_type` maps to a real type."""
    match = re.search(
        r"\b((?:rest\s*&?\s*recreational|casual|medical|sick|annual|earned|hajj|umrah|"
        r"maternity(?:\s+leave)?(?:\s+(?:first|second|third))?|paternity|study|short|"
        r"compensatory|marriage|shift|iddat|bereavement|beareavement|official)\w*)"
        r"(?:\s+leaves?)?\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    hint = match.group(1).strip().lower()
    # The table spells it "Sick" nowhere - medical is the configured type.
    return "medical" if hint.startswith("sick") else hint


def is_about_the_asker(question: str) -> bool:
    """True when the question is phrased about the person asking it.

    Used by the fallback path to decide between the employee's own records and
    the policy manual. "Am I running low on days off?" is a question about a
    record; answering it out of the manual's maximums produces a number that
    looks like an answer and is not one.
    """
    lowered = (question or "").lower()
    return _matches_any(lowered, FIRST_PERSON) and not _mentions(lowered, POLICY_WORDS)


def understand(question: str, today: Optional[date] = None) -> Understanding:
    text = (question or "").strip()
    lowered = text.lower()

    date_range = parse_date_range(text, today)
    report_format = _report_format(lowered)
    wants_report = _mentions(lowered, REPORT_WORDS)

    understanding = Understanding(
        intent=Intent.FALLBACK,
        question=text,
        date_range=date_range,
        report_format=report_format,
        wants_report=wants_report,
    )

    # ---- who is this about -------------------------------------------------
    for pattern in OTHER_PERSON_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            understanding.target_erp_id = int(match.group(1))
            understanding.about_someone_else = True
            break

    if not understanding.target_erp_id:
        candidates = _name_candidates(text)
        third_person = _matches_any(lowered, THIRD_PERSON_WORDS)
        first_person = _matches_any(lowered, FIRST_PERSON)

        understanding.target_name_candidates = candidates

        # A candidate phrase is only a colleague once the employee table says
        # so, which the caller checks - guessing here would either leak the
        # asker's own record under someone else's name or refuse valid
        # questions because a word looked like a name.
        if third_person and not first_person:
            understanding.about_someone_else = True

    # ---- what is being asked ---------------------------------------------
    is_attendance = _mentions(lowered, ATTENDANCE_WORDS)
    is_leave = _mentions(lowered, LEAVE_WORDS)
    is_official = _mentions(lowered, OFFICIAL_WORK_WORDS)
    is_policy = _mentions(lowered, POLICY_WORDS)

    if is_official:
        understanding.subject = Subject.OFFICIAL_WORK
    elif is_attendance:
        understanding.subject = Subject.ATTENDANCE
    elif is_leave:
        understanding.subject = Subject.LEAVE

    understanding.leave_type_hint = _leave_type_hint(lowered) if is_leave else None

    # A policy question about leave ("what is the casual leave policy") is a
    # document question, not a balance lookup - check that before the data
    # intents claim it.
    policy_beats_data = is_policy and not re.search(
        r"\bmy\b|\bi\b|\bme\b|\bdid i\b|\bhave i\b", lowered
    )

    if _matches_any(lowered, SMALLTALK_PATTERNS) and not (is_attendance or is_leave):
        understanding.intent = Intent.SMALLTALK
        understanding.is_courtesy = _matches_any(lowered, COURTESY_PATTERNS)
    elif wants_report and (is_attendance or is_leave or is_official):
        understanding.intent = Intent.REPORT
    elif policy_beats_data:
        understanding.intent = Intent.POLICY
    elif is_official:
        understanding.intent = Intent.OFFICIAL_WORK
    elif is_attendance:
        single_day = date_range is not None and date_range.days == 1
        understanding.intent = Intent.ATTENDANCE_DAY if single_day else Intent.ATTENDANCE_RANGE
        if date_range is None:
            # "how is my attendance" with no period named: today's card is the
            # useful answer, and it says which day it is reporting.
            understanding.intent = Intent.ATTENDANCE_DAY
    elif is_leave and _mentions(lowered, BALANCE_WORDS) and not date_range:
        understanding.intent = Intent.LEAVE_BALANCE
    elif is_leave and (_mentions(lowered, HISTORY_WORDS) or date_range):
        understanding.intent = Intent.LEAVE_HISTORY
    elif is_leave and _mentions(lowered, BALANCE_WORDS):
        understanding.intent = Intent.LEAVE_BALANCE
    elif _matches_any(lowered, PROFILE_PATTERNS):
        understanding.intent = Intent.PROFILE
    elif is_policy:
        understanding.intent = Intent.POLICY

    # ---- navigation -------------------------------------------------------
    for pattern, destination in NAVIGATE_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            understanding.navigate_to = destination
            break

    # "open the attendance page" is an instruction even though it mentions
    # attendance, so an explicit go-there phrasing outranks the data intent.
    if understanding.navigate_to and re.search(
        rf"{_GO}\b|\b(?:page|screen|tab|form)\b", lowered
    ):
        understanding.intent = Intent.NAVIGATE
    elif understanding.navigate_to and understanding.intent in {
        Intent.FALLBACK, Intent.LEAVE_BALANCE
    }:
        # A question ("how do I apply for leave?") is answered from the manual
        # with the page offered alongside; an instruction ("apply for leave")
        # just opens the page.
        understanding.intent = (
            Intent.POLICY if _matches_any(lowered, ASKING_HOW) else Intent.NAVIGATE
        )

    if understanding.intent is Intent.FALLBACK and is_leave:
        understanding.intent = Intent.LEAVE_BALANCE

    return understanding
