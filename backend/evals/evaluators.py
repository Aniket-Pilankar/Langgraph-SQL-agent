"""Evaluators for the golden dataset.

result_match   query results equal the reference results (compares values, not SQL text)
mentions_values  the answer text states the key values
tool_use       SQL ran when the question needed data, and never when it did not
judge_correct  LLM judge: the answer is correct and grounded
"""

import json
import re
from functools import cache

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from evals.normalize import normalize_row, normalize_value

# A stronger model than the agent's, so the judge is not grading its own mistakes.
JUDGE_MODEL = "gpt-4o"
NUMBER_TOLERANCE = 0.01


def _values_equal(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= NUMBER_TOLERANCE
    return a == b


def _row_covers(agent_row: list, reference_row: list) -> bool:
    """True when every reference value appears in the agent row. Agents often add
    extra columns or order them differently; that should not count as wrong."""
    remaining = list(agent_row)
    for expected in reference_row:
        match = next((i for i, value in enumerate(remaining) if _values_equal(value, expected)), None)
        if match is None:
            return False
        remaining.pop(match)
    return True


def _rows_match(agent_rows: list[list], reference_rows: list[list], ordered: bool) -> bool:
    if len(agent_rows) != len(reference_rows):
        return False
    if ordered:
        return all(_row_covers(a, r) for a, r in zip(agent_rows, reference_rows))
    unmatched = list(agent_rows)
    for reference_row in reference_rows:
        match = next((i for i, row in enumerate(unmatched) if _row_covers(row, reference_row)), None)
        if match is None:
            return False
        unmatched.pop(match)
    return True


def result_match(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    if not reference_outputs["expects_sql"]:
        return {"key": "result_match", "score": None, "comment": "No query expected"}
    results = outputs.get("results") or []
    if not results:
        return {"key": "result_match", "score": 0, "comment": "No successful query"}

    expected = reference_outputs["expected_rows"]
    candidates = [[normalize_row(row.values()) for row in rows] for rows in results]
    # A single-row answer is sometimes split across several one-row queries
    # (e.g. total orders, then canceled orders), so also try them combined.
    single_rows = [rows[0] for rows in candidates if len(rows) == 1]
    if len(expected) == 1 and len(single_rows) > 1:
        candidates.append([[value for row in single_rows for value in row]])

    matched = any(_rows_match(rows, expected, reference_outputs["ordered"]) for rows in candidates)
    return {"key": "result_match", "score": int(matched)}


def _normalize_text(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())


MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _date_variants(iso: str) -> list[str]:
    year, month, day = _ISO_DATE.match(iso).groups()
    name, day_number = MONTHS[int(month) - 1], str(int(day))
    return [iso, f"{name} {day_number}, {year}", f"{name} {day_number} {year}", f"{day_number} {name} {year}"]


def _mentioned(answer: str, expected: str) -> bool:
    if _ISO_DATE.match(expected):
        return any(variant in answer for variant in _date_variants(expected))
    value = normalize_value(expected)
    if isinstance(value, float):
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", answer)]
        return any(abs(n - value) <= NUMBER_TOLERANCE for n in numbers)
    words = [w for w in re.split(r"[^a-z0-9-]+", str(value)) if w]
    return all(re.search(rf"\b{re.escape(w)}\b", answer) for w in words)


def mentions_values(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    expected = reference_outputs["must_mention"]
    if not expected:
        return {"key": "mentions_values", "score": None, "comment": "Nothing to check"}
    answer = _normalize_text(outputs.get("answer", ""))
    missing = [value for value in expected if not _mentioned(answer, value)]
    return {
        "key": "mentions_values",
        "score": int(not missing),
        "comment": f"Missing: {', '.join(missing)}" if missing else "",
    }


def tool_use(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    calls = outputs.get("tool_calls", [])
    ran_sql = outputs.get("rows") is not None
    if reference_outputs["expects_sql"]:
        schema_first = "retrieve_schema" in calls and calls.index("retrieve_schema") < calls.index("run_sql") if "run_sql" in calls else False
        return {
            "key": "tool_use",
            "score": int(ran_sql),
            "comment": "" if schema_first else "run_sql was not preceded by retrieve_schema",
        }
    return {"key": "tool_use", "score": int(not ran_sql), "comment": "Query ran but none was needed" if ran_sql else ""}


class JudgeVerdict(BaseModel):
    reasoning: str = Field(description="Short explanation, written before the verdict.")
    correct: bool


JUDGE_PROMPT = """You grade answers from a data assistant for an e-commerce database.

Question: {question}

Reference result rows (from the database): {expected_rows}
Expected behavior: {expected_behavior}

Assistant's answer:
{answer}

Grade facts, not wording. The answer is correct when:
- it answers the question asked;
- every number, name and date it states agrees with the reference rows (formatting and
  rounding to the stated precision are fine);
- it follows the expected behavior, when one is given;
- it does not invent data values that are not in the reference.
Ignore phrasing, tone, formatting and extra correct detail.
Notes:
- null in the reference rows is a missing value; any description of it as missing,
  unspecified or uncategorized is correct.
- When there are no reference rows, grade only on the expected behavior. Describing the
  assistant's own capabilities is not inventing data.
Explain briefly, then give the verdict."""


@cache
def _judge():
    return ChatOpenAI(model=JUDGE_MODEL, temperature=0).with_structured_output(JudgeVerdict)


async def judge_correct(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    verdict = await _judge().ainvoke(
        JUDGE_PROMPT.format(
            question=inputs["question"],
            expected_rows=json.dumps(reference_outputs["expected_rows"][:20]),
            expected_behavior=reference_outputs.get("expected_behavior") or "Answer the question correctly.",
            answer=outputs.get("answer", ""),
        )
    )
    return {"key": "judge_correct", "score": int(verdict.correct), "comment": verdict.reasoning}


EVALUATORS = [result_match, mentions_values, tool_use, judge_correct]
