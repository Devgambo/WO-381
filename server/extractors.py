"""Markdown report parsers shared by the HTTP layer (`main.py`) and the
background worker (`tasks.py`).

These were originally private helpers in `main.py`. They were moved here so
the RQ worker can import them without importing the whole FastAPI app (which
would boot CORS, routers, and the heavy lazy-service machinery just to parse a
string).
"""
import logging
import re

log = logging.getLogger("compliance.extractors")

# ---------- Missing-field extractor ----------
_FLAG_STATUSES = {'missing information', 'cannot verify', 'non compliant'}
_CATEGORY_HEADINGS = {
    'missing information', 'cannot verify', 'non-compliant', 'non compliant',
    'wrong information', 'document type', 'not applicable',
}
_SKIP_LABELS = {'criteria', 'criterion', 'check', 'none', 'n/a', 'nil', '---', '#'}


def _normalise(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _norm_status(cell: str) -> str:
    """Lowercase, strip bold + emoji + punctuation -> just letters and spaces."""
    return re.sub(r"[^a-z ]", " ", cell.replace("**", "").lower()).strip()


def extract_missing_fields(report: str) -> list[str]:
    """Extract missing/non-compliant fields from compliance table + Phase-4 / Step-5 section."""
    missing_from_table: list[str] = []
    missing_from_step5: list[str] = []

    in_section = False
    location_seen = False

    for line in report.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Table row scan
        if stripped.startswith('|'):
            cells = [c.strip() for c in stripped.split('|') if c.strip()]
            if len(cells) >= 4:
                status_cell = _norm_status(cells[-1])
                status_cell = re.sub(r"\s+", " ", status_cell).strip()
                # Reduce "non-compliant"/"non compliant" to a single token.
                status_cell = status_cell.replace("non-", "non ")
                # Match: contains key term as substring.
                if any(flag in status_cell for flag in _FLAG_STATUSES):
                    criteria_idx = 0
                    if cells[0].replace('**', '').strip().isdigit() and len(cells) >= 5:
                        criteria_idx = 1
                    criteria = re.sub(r'^\d+\.\s*', '', cells[criteria_idx].replace('**', '').strip()).strip()
                    if criteria and not criteria.isdigit() and criteria.lower() not in _SKIP_LABELS:
                        missing_from_table.append(criteria)
                        if 'location' in criteria.lower():
                            location_seen = True
            continue

        # Section header detection
        if stripped.startswith('#'):
            if re.search(
                r'(step\s*5|phase\s*4|4\.1\b|missing.*(?:wrong|information|unverifiable))',
                stripped, re.IGNORECASE,
            ):
                in_section = True
                continue
            if in_section:
                if re.search(r'(4\.2\b|4\.3\b|summary|quality|severity)', stripped, re.IGNORECASE):
                    in_section = False
                    continue
                heading_level = len(stripped) - len(stripped.lstrip('#'))
                if heading_level <= 3:
                    in_section = False
                    continue

        # Site location flag from Step 0
        if not location_seen and re.search(r'0\.2', stripped) and re.search(
            r'(?i)missing|not\s+(mentioned|found|specified|provided|available)', stripped,
        ):
            if re.search(r'(?i)(site\s*)?location', stripped):
                missing_from_step5.append('Site Location')
                location_seen = True
                continue

        if not in_section or stripped.startswith('|') or re.match(r'^---+$|^===+$|^\*\*\*+$', stripped):
            continue

        clean = re.sub(r'^\d+\.\s*|^[-*+]\s*', '', stripped).replace('**', '').strip()
        if not clean or clean.lower() in ('none', 'n/a', 'nil'):
            continue

        if ':' in clean:
            prefix, _, detail = clean.partition(':')
            prefix = prefix.strip()
            detail = detail.strip()
            if prefix.lower() in _CATEGORY_HEADINGS:
                if not detail:
                    continue
                items = [item.strip().rstrip('.') for item in re.split(r',\s*(?![^()]*\))', detail)]
                for item in items:
                    item = re.sub(r'(?i)\s*due to lack of explicit data\s*', '', item).strip()
                    item = re.sub(r'\s*\(.*?\)\s*$', '', item).strip()
                    if item.lower().startswith('and '):
                        item = item[4:].strip()
                    if re.search(r'(?i)notes?\s*section|no\s+dedicated', item):
                        continue
                    if item and item.lower() not in ('none', 'n/a', 'nil'):
                        missing_from_step5.append(item)
            else:
                if not re.search(r'(?i)notes?\s*section|no\s+dedicated', prefix):
                    missing_from_step5.append(prefix)
        else:
            if not re.search(r'(?i)notes?\s*section|no\s+dedicated', clean):
                missing_from_step5.append(clean)

    seen: set[str] = set()
    merged: list[str] = []
    for item in missing_from_step5:
        key = _normalise(item)
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    for item in missing_from_table:
        key = _normalise(item)
        if not key or key in seen:
            continue
        if any(key in existing or existing in key for existing in seen):
            continue
        seen.add(key)
        merged.append(item)

    log.debug("Missing fields merged: %s", merged)
    return merged


def extract_quality_assessment(report: str) -> dict:
    """Parse the '### Drawing Quality Assessment' / Phase-4 block."""
    severity = "UNKNOWN"
    critical_defects = 0
    rejection_narrative = "N/A"

    in_section = False
    in_summary_section = False
    narrative_lines: list[str] = []
    collecting_narrative = False

    for line in report.splitlines():
        stripped = line.strip()

        if stripped.startswith("#") and re.search(
            r"drawing\s+quality\s+assessment|summary.*compliance|phase\s*4",
            stripped, re.IGNORECASE,
        ):
            if re.search(r"drawing\s+quality", stripped, re.IGNORECASE):
                in_section = True
            else:
                in_summary_section = True
            continue

        if (in_section or in_summary_section) and stripped.startswith("#"):
            if re.search(r"drawing\s+quality\s+assessment", stripped, re.IGNORECASE):
                in_section = True
                in_summary_section = False
                continue
            heading_level = len(stripped) - len(stripped.lstrip('#'))
            if heading_level <= 3:
                break

        if not in_section and not in_summary_section:
            continue

        sev_match = re.search(r"\*{0,2}severity\*{0,2}\s*:\s*([A-Z_]+)", stripped, re.IGNORECASE)
        if sev_match:
            raw_sev = sev_match.group(1).upper().strip()
            if raw_sev in {"ACCEPTABLE", "REQUIRES_REVISION", "REJECTED"}:
                severity = raw_sev
            continue

        verdict_match = re.search(r"\*{0,2}overall\s+verdict\*{0,2}\s*:\s*(.+)", stripped, re.IGNORECASE)
        if verdict_match and severity == "UNKNOWN":
            verdict_text = verdict_match.group(1).upper()
            if "FAIL" in verdict_text or "REJECT" in verdict_text:
                severity = "REJECTED"
            elif "CONDITIONAL" in verdict_text or "REVISION" in verdict_text:
                severity = "REQUIRES_REVISION"
            elif "PASS" in verdict_text or "ACCEPT" in verdict_text:
                severity = "ACCEPTABLE"
            continue

        defect_match = re.search(r"critical\s+defects?\s+count\s*:\s*(\d+)", stripped, re.IGNORECASE)
        if defect_match:
            try:
                critical_defects = int(defect_match.group(1))
            except ValueError:
                pass
            continue

        narr_match = re.search(r"\*{0,2}rejection\s+narrative\*{0,2}\s*:", stripped, re.IGNORECASE)
        if narr_match:
            collecting_narrative = True
            after_colon = stripped[narr_match.end():].strip()
            if after_colon and after_colon.lower() not in ("n/a", "na", ""):
                narrative_lines.append(after_colon)
            continue

        if collecting_narrative and stripped:
            narrative_lines.append(stripped)

    if narrative_lines:
        candidate = " ".join(narrative_lines).strip()
        if candidate.lower() not in ("n/a", "na"):
            rejection_narrative = candidate

    log.debug(
        "Quality: severity=%s defects=%d narrative_len=%d",
        severity, critical_defects, len(rejection_narrative),
    )
    return {
        "severity": severity,
        "critical_defects": critical_defects,
        "rejection_narrative": rejection_narrative,
    }
