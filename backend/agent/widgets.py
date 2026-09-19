import html
import json
import re
from typing import Literal

from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel, Field

MAX_CHART_POINTS = 12
MAX_TABLE_ROWS = 20
MAX_TABLE_COLUMNS = 6

CHART_TYPES = ("bar", "line", "pie")

_ISO_DATE = re.compile(r"^(?P<date>(?P<year_month>\d{4}-\d{2})-(?P<day>\d{2}))([T ]|$)")


class WidgetChoice(BaseModel):
    """Visualization chosen by the model. Values are read from the query result, so a
    chart can never show numbers the database did not return."""

    type: Literal["bar", "line", "pie", "table", "none"]
    title: str = Field(default="", max_length=80)
    label_column: str | None = None
    value_column: str | None = None


def last_sql_result(messages: list) -> dict | None:
    """Most recent successful run_sql artifact since the last user message."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return None
        if isinstance(msg, ToolMessage) and msg.name == "run_sql" and msg.artifact and "error" not in msg.artifact:
            return msg.artifact
    return None


def is_chartable(artifact: dict | None) -> bool:
    return bool(artifact) and artifact.get("row_count", 0) >= 2 and len(artifact.get("columns", [])) >= 2


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def resolve_columns(choice: WidgetChoice, artifact: dict) -> tuple[str, str] | None:
    """Validate the model's column choice, falling back to the first label/number pair."""
    columns = artifact["columns"]
    rows = artifact["rows"]
    label, value = choice.label_column, choice.value_column

    if label in columns and value in columns and label != value:
        if all(_is_number(row.get(value)) for row in rows):
            return label, value

    numeric = [c for c in columns if all(_is_number(row.get(c)) for row in rows)]
    labels = [c for c in columns if c not in numeric]
    if labels and numeric:
        return labels[0], numeric[0]
    return None


def _title_html(title: str) -> str:
    return f'<div class="widget-title">{html.escape(title)}</div>' if title else ""


def _table_html(choice: WidgetChoice, artifact: dict) -> str:
    columns = artifact["columns"][:MAX_TABLE_COLUMNS]
    header = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
    body = ""
    for row in artifact["rows"][:MAX_TABLE_ROWS]:
        cells = "".join(f"<td>{html.escape(str(row.get(c, '')))}</td>" for c in columns)
        body += f"<tr>{cells}</tr>"
    return _title_html(choice.title) + f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


_CHART_TEMPLATE = """
<canvas id="chart"></canvas>
<script>
  const D = __DATA__;
  new Chart(document.getElementById('chart'), {
    type: '__TYPE__',
    data: {
      labels: D.labels,
      datasets: [{
        label: __VALUE_LABEL__,
        data: D.values,
        backgroundColor: [
          'rgba(99,102,241,0.6)','rgba(16,185,129,0.6)','rgba(244,114,182,0.6)',
          'rgba(251,191,36,0.6)','rgba(56,189,248,0.6)','rgba(168,85,247,0.6)',
          'rgba(248,113,113,0.6)','rgba(52,211,153,0.6)','rgba(129,140,248,0.6)',
          'rgba(45,212,191,0.6)','rgba(251,146,60,0.6)','rgba(163,163,163,0.6)'
        ],
        borderColor: 'rgba(129,140,248,1)',
        borderWidth: 1
      }]
    },
    options: { responsive: true, plugins: { legend: { display: __LEGEND__ } } }
  });
</script>"""


def _format_labels(values: list) -> list[str]:
    """Shorten ISO timestamps so axis labels stay readable: 2017-01-01T00:00:00+00:00
    becomes 2017-01 for monthly buckets, or 2017-01-15 for daily ones."""
    labels = [str(v) for v in values]
    dates = [_ISO_DATE.match(label) for label in labels]
    if not all(dates):
        return labels
    if all(match["day"] == "01" for match in dates):
        return [match["year_month"] for match in dates]
    return [match["date"] for match in dates]


def _chart_html(choice: WidgetChoice, artifact: dict, label_column: str, value_column: str) -> str:
    rows = artifact["rows"][:MAX_CHART_POINTS]
    data = {
        "labels": _format_labels([row.get(label_column, "") for row in rows]),
        "values": [row.get(value_column) for row in rows],
    }
    # Escaping "</" stops a data value from closing the script tag.
    body = (
        _CHART_TEMPLATE.replace("__DATA__", json.dumps(data, default=str).replace("</", "<\\/"))
        .replace("__TYPE__", choice.type)
        .replace("__VALUE_LABEL__", json.dumps(value_column))
        .replace("__LEGEND__", "true" if choice.type == "pie" else "false")
    )
    return _title_html(choice.title) + body


def build_widget_html(choice: WidgetChoice, artifact: dict) -> str | None:
    if choice.type == "none" or not artifact.get("rows"):
        return None
    if choice.type == "table":
        return _table_html(choice, artifact)
    if choice.type in CHART_TYPES:
        columns = resolve_columns(choice, artifact)
        if columns is None:
            return _table_html(choice, artifact)
        return _chart_html(choice, artifact, *columns)
    return None
