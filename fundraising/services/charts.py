import json
from pathlib import Path


CHART_LIBRARY_PATH = Path(__file__).resolve().parents[1] / "voice" / "chart-library.json"


def load_chart_library():
    try:
        payload = json.loads(CHART_LIBRARY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    return payload.get("charts", [])


def _normalize_category(category):
    if isinstance(category, list):
        category = " ".join(str(value) for value in category if value)
    if not isinstance(category, str):
        return ""
    return category.strip().lower()


def pick_chart(category):
    normalized = _normalize_category(category)
    if not normalized:
        return None

    for chart in load_chart_library():
        if any(str(keyword).lower() in normalized for keyword in chart.get("programmes", [])):
            return chart
    return None
