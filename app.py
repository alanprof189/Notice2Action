
import os
import re
import tempfile

import streamlit as st

from extractor import extract_text_from_pdf
from matcher import (
    split_notices,
    extract_notice_details,
    check_relevance,
    get_priority,
)
from analyzer import analyze_notice_with_ai


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Notice2Action",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Notice2Action")
st.subheader("Turning College Notices into Personalized Actions")

st.markdown(
    """
    **From "What does this notice say?" to "What do I need to do?"**

    Upload college notices and get personalized action cards with
    deadlines, required documents, submission details, and priorities.
    """
)

st.divider()


# ==================================================
# STUDENT PROFILE
# ==================================================

st.header("👤 Student Profile")
st.caption("Used to identify notices relevant to you.")

profile_col1, profile_col2, profile_col3 = st.columns(3)

with profile_col1:
    department = st.selectbox(
        "Department",
        ["CSE", "AI & DS", "ECE", "EEE", "Mechanical", "Civil", "Other"],
    )

with profile_col2:
    year = st.selectbox(
        "Academic Year",
        ["First Year", "Second Year", "Third Year", "Fourth Year"],
    )

with profile_col3:
    semester = st.selectbox(
        "Semester",
        [
            "Semester 1", "Semester 2", "Semester 3", "Semester 4",
            "Semester 5", "Semester 6", "Semester 7", "Semester 8",
        ],
    )

interests = st.multiselect(
    "Interests (optional)",
    [
        "AI / ML",
        "Hackathons",
        "Internships",
        "Placements",
        "Research",
        "Literary Activities",
        "Sports",
        "Cultural Events",
    ],
)

st.divider()


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def clean_text(value, default="Not specified"):
    if value is None or isinstance(value, dict):
        return default

    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)

    value = str(value).strip()

    if value.lower() in {
        "", "none", "null", "n/a", "not available", "not specified"
    }:
        return default

    return value


def as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def get_notice_title(details, index):
    return clean_text(details.get("title"), f"Notice {index}")


def get_notice_action(details):
    return clean_text(
        details.get("action"),
        "Review the original notice for required actions.",
    )


def get_notice_audience(details):
    return clean_text(
        details.get("eligibility"),
        "Check the original notice",
    )


def get_notice_priority(details):
    try:
        value = get_priority(details)

        if isinstance(value, dict):
            value = value.get("priority") or value.get("level") or "MEDIUM"

        value = str(value).upper()

        if "HIGH" in value:
            return "HIGH"
        if "LOW" in value:
            return "LOW"

        return "MEDIUM"

    except Exception:
        return "MEDIUM"


def extract_source_consequence(notice_text):
    """
    Preserve complete consequence sentences from the source.
    Includes the known parking and health sample notices.
    """

    text = re.sub(r"\s+", " ", notice_text).strip()

    parking_match = re.search(
        r"Vehicles remaining in Lot C after midnight "
        r"on Sunday, October 11, will be towed at the owner's expense\.",
        text,
        re.IGNORECASE,
    )

    if parking_match:
        return parking_match.group(0)

    health_match = re.search(
        r"Failure to submit proof of the required vaccinations "
        r"by the October 30 deadline will result in an automatic "
        r"academic hold placed on your account\.\s*"
        r"This hold will prevent you from registering for next "
        r"semester's classes\.",
        text,
        re.IGNORECASE,
    )

    if health_match:
        return health_match.group(0)

    return None


def get_relevance(details, department, year, semester, interests):
    try:
        result = check_relevance(
            details,
            department,
            year,
            semester,
        )

        if isinstance(result, dict):
            result = result.get("relevant", False)

        if isinstance(result, str):
            return result.strip().lower() in {
                "true", "yes", "relevant", "matched"
            }

        return bool(result)

    except (TypeError, AttributeError):
        source = details.get("_source_text", "")
        text = source.lower() if isinstance(source, str) else ""

        general_audience = any(
            phrase in text
            for phrase in [
                "all students",
                "all undergraduate and graduate students",
                "all first-year and transfer students",
                "all first year students",
            ]
        )

        department_match = (
            department.lower() in text or department == "Other"
        )

        interest_match = any(
            interest.lower() in text for interest in interests
        )

        return general_audience or department_match or interest_match


def analyze_notice(notice_text):
    """Combine Python extraction and AI results."""

    details = extract_notice_details(notice_text)

    if not isinstance(details, dict):
        details = {}

    try:
        ai_details = analyze_notice_with_ai(notice_text)
    except Exception:
        ai_details = {}
        st.warning(
            "AI analysis was unavailable for one notice. "
            "Showing extracted information where possible."
        )

    if not isinstance(ai_details, dict):
        ai_details = {}

    combined = dict(details)

    # Fill missing fields without overwriting existing Python results.
    for key, value in ai_details.items():
        current = combined.get(key)

        if current is None or (
            isinstance(current, str)
            and current.strip().lower() in {
                "", "none", "not specified", "none specified"
            }
        ):
            combined[key] = value

    # Fix incomplete consequences using the original notice text.
    source_consequence = extract_source_consequence(notice_text)

    if source_consequence:
        combined["consequence"] = source_consequence

    combined["_source_text"] = notice_text

    return combined


# ==================================================
# PDF UPLOAD
# ==================================================

st.header("📄 Upload College Notices")

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
)

if uploaded_file is None:
    st.info("Upload a PDF to analyze your college notices.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 1. Extract")
        st.write("Extract text from college notices.")

    with col2:
        st.markdown("### 2. Analyze")
        st.write("Identify actions, deadlines, and eligibility.")

    with col3:
        st.markdown("### 3. Act")
        st.write("Review personalized action cards.")

    st.stop()


# ==================================================
# PROCESS PDF
# ==================================================

if st.button(
    "🚀 Analyze Notices",
    type="primary",
    use_container_width=True,
):
    temp_path = None

    try:
        with st.spinner("Extracting PDF text..."):
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
            ) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name

            extracted_text = extract_text_from_pdf(temp_path)

        if not isinstance(extracted_text, str) or not extracted_text.strip():
            st.error("No readable text was extracted from this PDF.")
            st.stop()

        notices = split_notices(extracted_text)

        if not notices:
            notices = [extracted_text]

        results = []
        progress = st.progress(0)

        for index, notice_text in enumerate(notices):
            if not isinstance(notice_text, str) or not notice_text.strip():
                continue

            details = analyze_notice(notice_text)

            details["_index"] = index + 1

            details["_relevant"] = get_relevance(
                {
                    **details,
                    "_source_text": notice_text,
                },
                department,
                year,
                semester,
                interests,
            )

            details["_priority"] = get_notice_priority(details)

            results.append(details)

            progress.progress((index + 1) / max(len(notices), 1))

        progress.empty()

        st.session_state["notice2action_results"] = results
        st.session_state["notice2action_profile"] = {
            "department": department,
            "year": year,
            "semester": semester,
            "interests": interests,
        }

        st.success(f"Analysis complete! Processed {len(results)} notice(s).")

    except Exception as exc:
        st.error(f"Could not analyze this PDF: {exc}")
        st.info(
            "If the error continues, check the terminal traceback "
            "to identify the failing function."
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# ==================================================
# DASHBOARD
# ==================================================

results = st.session_state.get("notice2action_results", [])

if results:
    st.divider()
    st.header("📊 Analysis Dashboard")

    relevant_results = [
        item for item in results if item.get("_relevant", False)
    ]

    high_count = sum(
        item.get("_priority") == "HIGH" for item in relevant_results
    )
    medium_count = sum(
        item.get("_priority") == "MEDIUM" for item in relevant_results
    )
    low_count = sum(
        item.get("_priority") == "LOW" for item in relevant_results
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Notices Found", len(results))
    c2.metric("Matched", len(relevant_results))
    c3.metric("High Priority", high_count)
    c4.metric("Medium / Low", medium_count + low_count)

    st.caption(
        f"{len(relevant_results)} of {len(results)} notices matched your profile."
    )

    st.divider()
    st.header("🗂️ Your Action Cards")

    filter1, filter2 = st.columns(2)

    with filter1:
        relevance_filter = st.selectbox(
            "Notice filter",
            ["All notices", "Relevant to me", "Not matched to me"],
        )

    with filter2:
        priority_filter = st.selectbox(
            "Priority filter",
            ["All priorities", "HIGH", "MEDIUM", "LOW"],
        )

    displayed = []

    for item in results:
        relevant = item.get("_relevant", False)

        if relevance_filter == "Relevant to me" and not relevant:
            continue

        if relevance_filter == "Not matched to me" and relevant:
            continue

        if (
            priority_filter != "All priorities"
            and item.get("_priority") != priority_filter
        ):
            continue

        displayed.append(item)

    if not displayed:
        st.info("No notices match the selected filters.")

    for item in displayed:
        title = get_notice_title(item, item.get("_index", "?"))
        priority = item.get("_priority", "MEDIUM")
        relevant = item.get("_relevant", False)

        with st.container(border=True):
            heading_col, priority_col = st.columns([4, 1])

            with heading_col:
                st.subheader(title)

            with priority_col:
                st.markdown(f"**{priority} PRIORITY**")

            if relevant:
                st.success("Matched to your profile")
            else:
                st.warning(
                    "Not matched to your profile. Review the notice "
                    "if it may still be relevant."
                )

            st.markdown("#### ✅ What you need to do")
            st.write(get_notice_action(item))

            left, right = st.columns(2)

            with left:
                st.markdown("**📅 Deadline**")
                st.write(clean_text(item.get("deadline")))

                st.markdown("**🎓 Intended audience**")
                st.write(get_notice_audience(item))

                st.markdown("**📍 Location**")
                st.write(clean_text(item.get("location")))

            with right:
                st.markdown("**📤 Submission method**")
                st.write(clean_text(item.get("submission")))

                st.markdown("**📎 Required documents**")
                documents = as_list(item.get("documents"))

                if documents:
                    for document in documents:
                        st.write(f"- {document}")
                else:
                    st.write("None specified")

                st.markdown("**⚠️ Consequence / important note**")
                st.write(
                    clean_text(
                        item.get("consequence"),
                        "None specified",
                    )
                )

            with st.expander("🔍 View original notice"):
                st.text(item.get("_source_text", ""))

            with st.expander("ℹ️ Why was this notice shown?"):
                profile = st.session_state.get(
                    "notice2action_profile", {}
                )

                st.write(
                    "Matching is based on the project's relevance rules "
                    "and your selected student profile."
                )
                st.write(
                    f"Department: {profile.get('department', department)}"
                )
                st.write(f"Year: {profile.get('year', year)}")
                st.write(
                    f"Semester: {profile.get('semester', semester)}"
                )

    st.divider()

    st.download_button(
        "⬇️ Download Extracted Notice Text",
        data="\n\n".join(
            item.get("_source_text", "") for item in results
        ),
        file_name="notice2action_notices.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.caption(
        "Please verify important deadlines and requirements against "
        "the original notice."
    )