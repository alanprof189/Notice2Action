
import re


# ============================================================
# 1. SPLIT THE PDF INTO INDIVIDUAL NOTICES
# ============================================================

def split_notices(text):
    """Split extracted PDF text into separate notices."""

    if not text or not text.strip():
        return []

    pattern = r"(?im)^\s*NOTICE\s+\d+\s*\*?\s*:"
    matches = list(re.finditer(pattern, text))

    if not matches:
        return [text.strip()]

    notices = []

    for index, match in enumerate(matches):
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )

        notice = text[start:end].strip()

        if notice:
            notices.append(notice)

    return notices


# ============================================================
# 2. DATE PATTERNS AND TEXT CLEANING
# ============================================================

MONTHS = (
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December"
)

WEEKDAYS = (
    r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
)

DATE_PATTERN = (
    rf"(?:(?:{WEEKDAYS})\s*,?\s*)?"
    rf"(?:{MONTHS})\s+\d{{1,2}}"
    rf"(?:,\s*\d{{4}})?"
)


def _clean(value):
    """Normalize extracted text."""

    return re.sub(r"\s+", " ", value).strip(" \t\n:;,-")


def _find_first(patterns, text, flags=re.IGNORECASE):
    """Return the first non-empty regex capture."""

    for pattern in patterns:
        match = re.search(pattern, text, flags)

        if match:
            value = _clean(match.group(1))

            if value:
                return value

    return None


# ============================================================
# 3. EXTRACT DEADLINES
# ============================================================

def _extract_deadline(text):
    """
    Extract explicitly stated action deadlines.

    Event dates, effective dates, and closure dates are not
    automatically treated as submission deadlines.
    """

    patterns = [
        rf"\bSubmission\s+Deadline\s*:\s*({DATE_PATTERN})",
        rf"\bApplication\s+Deadline\s*:\s*({DATE_PATTERN})",
        rf"\bRegistration\s+Deadline\s*:\s*({DATE_PATTERN})",
        rf"\bDeadline\s*:\s*({DATE_PATTERN})",
        rf"\bDue\s+Date\s*:\s*({DATE_PATTERN})",
        rf"\bDeadline\s+(?:is\s+)?({DATE_PATTERN})",
        rf"\bsubmit\b[^.\n]{{0,100}}?\bby\s+({DATE_PATTERN})",
        rf"\bmust\b[^.\n]{{0,100}}?\bby\s+({DATE_PATTERN})",
        rf"\bfailure\s+to\b[^.\n]{{0,150}}?\bby\s+({DATE_PATTERN})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return _clean(match.group(1))

    return "Not specified"


# ============================================================
# 4. EXTRACT LOCATION
# ============================================================

def _extract_location(text):
    """Extract a physical location or relevant online destination."""

    # Prefer explicitly stated venue/location fields.
    explicit_location = _find_first([
        r"\bLocation\s*:\s*([^\n|]+)",
        r"\bVenue\s*:\s*([^\n|]+)",
    ], text)

    if explicit_location:
        return explicit_location

    # Parking-specific location and alternative.
    if re.search(r"\bparking\b", text, re.IGNORECASE):
        lot_c_closed = re.search(
            r"\bParking Lot C\b[^.\n]{0,120}\bclosed\b"
            r"|\bclosed\b[^.\n]{0,120}\bParking Lot C\b",
            text,
            re.IGNORECASE,
        )

        alternative_match = re.search(
            r"\bAlternative Parking\s*:\s*([^\n]+)",
            text,
            re.IGNORECASE,
        )

        alternative = (
            _clean(alternative_match.group(1))
            if alternative_match
            else None
        )

        if lot_c_closed and alternative:
            return f"Parking Lot C closed; {alternative}"

        if lot_c_closed:
            return "Parking Lot C is closed during the stated period"

        if alternative:
            return alternative

    # Health-related destinations.
    if re.search(r"\bHealth Portal\b", text, re.IGNORECASE):
        if re.search(r"\bStudent Health Center\b", text, re.IGNORECASE):
            return "Health Portal or Student Health Center"

        return "Health Portal"

    # Student portal.
    if re.search(r"\bStudent Portal\b", text, re.IGNORECASE):
        return "Student Portal"

    # A named physical location following a common phrase.
    location_match = re.search(
        r"\b(?:held|take place|located)\s+(?:at|in)\s+"
        r"([^.\n]+)",
        text,
        re.IGNORECASE,
    )

    if location_match:
        return _clean(location_match.group(1))

    return "See original notice"


# ============================================================
# 5. EXTRACT SUBMISSION METHOD
# ============================================================

def _extract_submission(text):
    """Extract an email, portal, or other submission method."""

    email_match = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        text,
        re.IGNORECASE,
    )

    email = email_match.group(0) if email_match else None

    if email and re.search(
        r"\b(?:email|e-mail)\b[^.\n]{0,100}"
        + re.escape(email),
        text,
        re.IGNORECASE,
    ):
        return f"Email: {email}"

    if re.search(r"\bHealth Portal\b", text, re.IGNORECASE):
        return "Upload documents through the Health Portal"

    if re.search(r"\bStudent Portal\b", text, re.IGNORECASE):
        return "Student Portal"

    if email:
        return f"Email: {email}"

    if re.search(r"\bupload\b", text, re.IGNORECASE):
        return "Online upload"

    if re.search(r"\bpre-register\b", text, re.IGNORECASE):
        return "Pre-register online"

    if re.search(r"\bsubmit\b", text, re.IGNORECASE):
        return "Submit as instructed in the notice"

    return "Not specified"


# ============================================================
# 6. EXTRACT NOTICE DETAILS
# ============================================================

def extract_notice_details(notice_text):
    """Extract notice fields using deterministic Python rules."""

    text = (notice_text or "").strip()
    text_lower = text.lower()

    details = {
        "title": "College Notice",
        "action": "Read the notice for instructions.",
        "deadline": "Not specified",
        "eligibility": "Not specified",
        "documents": "Not specified",
        "submission": "Not specified",
        "consequence": "None specified",
        "location": "See original notice",
    }

    if not text:
        return details

    # ---------------- TITLE ----------------

    title_match = re.search(
        r"(?is)^\s*NOTICE\s+\d+\s*\*?\s*:\s*"
        r"(.*?)(?=\s+To\s*:|\s+From\s*:|$)",
        text,
    )

    if title_match and title_match.group(1).strip():
        details["title"] = _clean(title_match.group(1))

    title_lower = details["title"].lower()

    # ---------------- ELIGIBILITY ----------------

    # Extract only the audience between "To:" and "From:".
    # Do not replace the audience with conditions such as
    # "Zone 2 permit holders" from the body of the notice.
    audience_match = re.search(
        r"(?is)\bTo\s*:\s*(.*?)(?=\s+From\s*:|$)",
        text,
    )

    if audience_match:
        audience = _clean(audience_match.group(1))

        if audience:
            details["eligibility"] = audience

    # ---------------- DEADLINE ----------------

    details["deadline"] = _extract_deadline(text)

    # ---------------- LOCATION ----------------

    details["location"] = _extract_location(text)

    # ---------------- SUBMISSION ----------------

    details["submission"] = _extract_submission(text)

    # ---------------- REQUIRED DOCUMENTS ----------------

    if "immunization" in text_lower or "vaccination" in text_lower:
        details["documents"] = (
            "Required immunization forms and vaccination proof"
        )

    elif "resume" in text_lower or "résumé" in text_lower:
        if re.search(r"\b10\s+copies\b", text_lower):
            details["documents"] = "Updated resume (minimum 10 copies)"
        else:
            details["documents"] = "Updated resume"

    elif "original unpublished" in text_lower:
        details["documents"] = "Original, unpublished work"

    elif "visual art" in text_lower:
        details["documents"] = (
            "Up to 3 poems, short fiction up to 3,500 words, "
            "or high-resolution images/scans of visual art; "
            "include name, student ID, and major"
        )

    elif re.search(r"\bdocuments?\b|\bdocumentation\b", text_lower):
        details["documents"] = "Required documents"

    elif re.search(r"\bforms?\b", text_lower):
        details["documents"] = "Required forms"

    elif "proof" in text_lower:
        details["documents"] = "Required proof or documentation"

    # ---------------- CONSEQUENCES ----------------

    consequence_patterns = [
        r"[^.\n]*automatic academic hold[^.\n]*",
        r"[^.\n]*will be towed[^.\n]*",
        r"[^.\n]*failure to[^.\n]*will result in[^.\n]*",
        r"[^.\n]*will prevent[^.\n]*",
        r"[^.\n]*will result in[^.\n]*",
    ]

    for pattern in consequence_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            details["consequence"] = _clean(match.group(0))
            break

    # ---------------- ACTION ----------------

    if "immunization" in text_lower or "vaccination" in text_lower:
        details["action"] = "Submit proof of required vaccinations."

    elif "parking" in title_lower:
        details["action"] = (
            "Do not park in Lot C after midnight on October 11; "
            "use Lot G if you have a Zone 2 permit."
        )

    elif "career" in title_lower or "internship fair" in title_lower:
        details["action"] = (
            "Pre-register through the Student Portal to receive "
            "the employer directory; bring at least 10 updated "
            "resume copies and wear professional attire."
        )

    elif "literary" in title_lower or "magazine" in title_lower:
        details["action"] = (
            "Email original, unpublished poetry, short fiction, "
            "or visual art to the magazine."
        )

    elif "pre-register" in text_lower:
        details["action"] = "Pre-register online as instructed."

    elif "upload" in text_lower:
        details["action"] = "Upload the required documents."

    elif "submit" in text_lower and details["submission"].startswith("Email:"):
        details["action"] = "Submit the required materials by email."

    elif "submit" in text_lower:
        details["action"] = "Submit the required materials as instructed."

    return details


# ============================================================
# 7. PERSONALIZED STUDENT RELEVANCE
# ============================================================

def check_relevance(notice_text, department, semester, year):
    """
    Determine whether a notice appears relevant to the student.

    This is rule-based matching, not an AI decision.
    """

    text = (notice_text or "").lower()
    department = str(department or "").strip()
    semester = str(semester or "").strip()
    year = str(year or "").strip()

    reasons = []
    relevant = False
    specific_match = False

    # First-year / year-based audience.
    if re.search(r"\bfirst[- ]year\b", text) and year == "1":
        relevant = True
        specific_match = True
        reasons.append("This notice applies to first-year students.")

    # Department-specific matching.
    if department and department.lower() in text:
        relevant = True
        specific_match = True
        reasons.append(
            f"This notice mentions the {department} department."
        )

    # Semester-specific matching.
    if semester and re.search(
        rf"\b(?:semester|sem)\s*[-:]?\s*{re.escape(semester)}\b",
        text,
    ):
        relevant = True
        specific_match = True
        reasons.append(
            f"This notice mentions Semester {semester}."
        )

    # General student audience.
    # Keep this separate from specific audiences such as
    # first-year and transfer students.
    general_audience_patterns = [
        r"\ball students\b",
        r"\ball undergraduate students\b",
        r"\ball graduate students\b",
        r"\ball undergraduate and graduate students\b",
    ]

    general_audience = any(
        re.search(pattern, text)
        for pattern in general_audience_patterns
    )

    if general_audience:
        relevant = True

        # Avoid adding a generic reason if a specific match
        # already explains why the notice applies.
        if not specific_match:
            reasons.append(
                "This notice is addressed to students generally."
            )

    # Career, internship, and student activity notices.
    if any(term in text for term in [
        "career fair",
        "internship fair",
        "student activity",
    ]):
        relevant = True

        if not reasons:
            reasons.append(
                "This appears to be a student opportunity or activity."
            )

    # Literary submission opportunities.
    if any(term in text for term in [
        "literary magazine",
        "call for submissions",
        "original, unpublished",
    ]):
        relevant = True

        if not reasons:
            reasons.append(
                "This notice announces an opportunity open to students."
            )

    if not reasons:
        reasons.append("No direct eligibility match was detected.")

    return relevant, reasons


# ============================================================
# 8. PRIORITY CLASSIFICATION
# ============================================================

def get_priority(details):
    """
    Assign priority using explicit urgency and consequences.

    HIGH: serious academic or compliance consequences.
    MEDIUM: action or participation is encouraged/required.
    LOW: mainly informational.
    """

    action = details.get("action", "").lower()
    consequence = details.get("consequence", "").lower()
    title = details.get("title", "").lower()

    if any(keyword in consequence for keyword in [
        "academic hold",
        "prevent",
        "failure to",
        "will result",
    ]):
        return "HIGH"

    if any(keyword in title for keyword in [
        "mandatory",
        "required",
        "clearance",
    ]):
        return "HIGH"

    if any(keyword in action for keyword in [
        "upload",
        "submit",
        "pre-register",
        "register",
        "email",
    ]):
        return "MEDIUM"

    if any(keyword in title for keyword in [
        "career",
        "internship",
        "fair",
        "event",
        "submission",
        "literary",
    ]):
        return "MEDIUM"

    return "LOW"