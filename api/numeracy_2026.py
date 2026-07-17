"""Shared contracts and pure quality policy for 2026 numeracy assessments."""

from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone


@dataclass(frozen=True)
class Component:
    airtable_field: str
    display_name: str
    model_field: str
    maximum: float


COMPONENTS = (
    Component("Counting aloud", "Counting Aloud", "counting_aloud", 100),
    Component("Number Recognition", "Number Recognition", "number_recognition", 20),
    Component("Counting & Matching", "Counting & Matching", "counting_matching", 2),
    Component("Write Numbers", "Write Numbers", "write_numbers", 10),
    Component("Identification", "More or Less", "identification", 4),
    Component("Missing Numbers", "Missing Numbers", "missing_numbers", 10),
    Component("Missing number to 10", "Sum 10", "sum_10", 2),
    Component("Story", "Word Problems", "word_problems", 1),
    Component("Jan Addition & Subtraction", "Addition & Subtraction", "addition_subtraction", 12),
)
MAX_SCORES = OrderedDict((component.airtable_field, component.maximum) for component in COMPONENTS)
MODEL_FIELDS = tuple(component.model_field for component in COMPONENTS)
DISPLAY_NAMES = tuple(component.display_name for component in COMPONENTS)


def uid_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    if value is None or value == "":
        return None
    return str(value).strip() or None


def list_value(value):
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def linked_record_ids(value):
    return [str(item) for item in list_value(value) if str(item).startswith("rec")]


def parse_numeric(value):
    if value is None or value == "" or isinstance(value, dict):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value):
    number = parse_numeric(value)
    return int(number) if number is not None else None


def parse_datetime(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt_timezone.utc)
    except (TypeError, ValueError):
        return None


def score_tuple(row):
    return tuple(row.get(field) for field in MODEL_FIELDS)


def range_issues(row):
    issues = []
    for component in COMPONENTS:
        value = row.get(component.model_field)
        if value is not None and (value < 0 or value > component.maximum):
            issues.append(
                {
                    "source_airtable_id": row.get("source_airtable_id"),
                    "child_uid": row.get("child_uid"),
                    "year": row.get("year"),
                    "term": row.get("term"),
                    "issue_code": "OUT_OF_RANGE",
                    "component": component.display_name,
                    "value": value,
                    "maximum": component.maximum,
                }
            )
    return issues


def evaluate_quality(rows):
    """Return accepted winners and a deterministic, name-free issue report.

    Only identical duplicates are resolved automatically. Any invalid component,
    missing child UID, or conflicting duplicate removes that business group from
    the accepted winner set.
    """

    groups = {}
    issues = []
    for row in sorted(rows, key=lambda item: str(item.get("source_airtable_id") or "")):
        if not row.get("child_uid"):
            issues.append(
                {
                    "source_airtable_id": row.get("source_airtable_id"),
                    "child_uid": None,
                    "year": row.get("year"),
                    "term": row.get("term"),
                    "issue_code": "MISSING_CHILD_UID",
                    "component": "",
                    "value": "",
                    "maximum": "",
                }
            )
            issues.extend(range_issues(row))
            continue
        key = (row.get("child_uid"), row.get("year"), row.get("term"))
        groups.setdefault(key, []).append(row)

    winners = {}
    for key in sorted(groups, key=lambda item: tuple(str(part) for part in item)):
        group = groups[key]
        invalid = []
        for row in group:
            invalid.extend(range_issues(row))
        distinct_scores = {score_tuple(row) for row in group}
        if len(distinct_scores) > 1:
            differing_components = [
                component
                for component in COMPONENTS
                if len({row.get(component.model_field) for row in group}) > 1
            ]
            for row in group:
                for component in differing_components:
                    issues.append(
                        {
                            "source_airtable_id": row.get("source_airtable_id"),
                            "child_uid": key[0],
                            "year": key[1],
                            "term": key[2],
                            "issue_code": "CONFLICTING_DUPLICATE",
                            "component": component.display_name,
                            "value": row.get(component.model_field),
                            "maximum": component.maximum,
                        }
                    )
            issues.extend(invalid)
            continue
        if invalid:
            issues.extend(invalid)
            continue
        winner = group[0]
        winners[key] = winner
        for redundant in group[1:]:
            issues.append(
                {
                    "source_airtable_id": redundant.get("source_airtable_id"),
                    "child_uid": key[0],
                    "year": key[1],
                    "term": key[2],
                    "issue_code": "REDUNDANT_IDENTICAL_DUPLICATE",
                    "component": "",
                    "value": "",
                    "maximum": "",
                }
            )
    return winners, issues


def issue_counts(issues):
    return dict(sorted(Counter(issue["issue_code"] for issue in issues).items()))
