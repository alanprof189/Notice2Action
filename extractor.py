
import fitz
import re


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF using PyMuPDF.

    Uses layout-aware sorting to improve reading order and
    normalizes whitespace without merging separate words.
    Accepts a PDF file path.
    """

    text_parts = []

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            # Sort text blocks in reading order.
            page_text = page.get_text(
                "text",
                sort=True,
            )

            if page_text and page_text.strip():
                text_parts.append(page_text)

    text = "\n".join(text_parts)

    # Normalize line endings and non-breaking spaces.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\u00a0", " ")

    # Remove trailing whitespace from each line.
    lines = [
        line.strip()
        for line in text.splitlines()
    ]

    # Preserve paragraph breaks while removing excessive blanks.
    cleaned_lines = []
    previous_blank = False

    for line in lines:
        if not line:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
        else:
            cleaned_lines.append(line)
            previous_blank = False

    return "\n".join(cleaned_lines).strip()