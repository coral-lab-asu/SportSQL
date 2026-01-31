#!/usr/bin/env python3
"""
Planner for Comprehensive Insights mode.

Responsibilities:
- Load planner prompt (prompts/prompt3_planner.txt)
- Build planner input (question, schema summary, entities, constraints, server_type)
- Call LLM to produce a strict JSON plan
- Parse and validate plan; enforce caps (subqueries, limits, charts)

Public API:
- plan_queries(question: str, entities: dict, server_type: str = "remote") -> dict
- validate_plan(plan: dict) -> tuple[bool, list[str], dict]
- get_schema_summary() -> str
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

from insights_config import (
    get_constraints,
    MAX_SUBQUERIES,
    ROW_LIMIT,
    MAX_CHARTS,
    LLM_TIMEOUT_SEC,
)
# get_global_llm imported lazily to simplify testing and avoid dotenv dependency at import time
from insights_schema import SCHEMA_SUMMARY


PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
PLANNER_PROMPT_PATH = os.path.join(PROMPTS_DIR, "prompt3_planner.txt")
PLANNER_NL_PROMPT_PATH = os.path.join(PROMPTS_DIR, "prompt3_planner_nl.txt")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_schema_summary() -> str:
    """
    Return a concise schema string used by the planner prompt.
    This mirrors the reference shown in prompt3_planner.txt.
    """
    return (
        "- players: [player_id, first_name, second_name, team_name, goals_scored, assists, minutes, "
        "expected_goals, expected_assists, total_points, ...]\n"
        "- player_history: [season_name, second_name, goals_scored, assists, minutes, expected_goals, "
        "expected_assists, ict_index, ...]\n"
        "- teams: [team_id, team_name, short_name, points, win, draw, loss, strength, ...]\n"
        "- fixtures: [game_id, gw, finished, team_a_name, team_h_name, kickoff_time, team_a_score, team_h_score, ...]"
    )


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Attempt to parse JSON from raw LLM text.
    1) Direct json.loads
    2) Fallback: find first {...} block using balanced braces heuristic
    """
    text = (text or "").strip()
    # Fast path
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to locate a JSON object substring
    # Find first '{' and try to match a balanced object.
    start = text.find("{")
    if start == -1:
        raise ValueError("Planner LLM output did not contain JSON object.")

    # Simple brace counter
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    break

    raise ValueError("Failed to parse planner JSON from LLM output.")


def _coerce_int(value: Any, default: int) -> int:
    try:
        iv = int(value)
        return iv
    except Exception:
        return default


def validate_plan(plan: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate and enforce caps on the plan structure.

    Returns:
        (is_valid, errors, fixed_plan)
    """
    errors: List[str] = []
    fixed = dict(plan) if isinstance(plan, dict) else {}

    # Required top-level keys
    required_top = ["intent", "entities", "subqueries", "charts", "max_items"]
    for k in required_top:
        if k not in fixed:
            errors.append(f"Missing top-level key: {k}")

    # Ensure structure types
    if not isinstance(fixed.get("entities"), dict):
        fixed["entities"] = {}
        errors.append("entities should be an object")

    if not isinstance(fixed.get("subqueries"), list):
        fixed["subqueries"] = []
        errors.append("subqueries should be an array")

    if not isinstance(fixed.get("charts"), list):
        fixed["charts"] = []
        errors.append("charts should be an array")

    # Enforce caps
    subqueries: List[Dict[str, Any]] = fixed.get("subqueries", [])
    if len(subqueries) > MAX_SUBQUERIES:
        subqueries = subqueries[:MAX_SUBQUERIES]
    fixed["subqueries"] = subqueries

    charts: List[Dict[str, Any]] = fixed.get("charts", [])
    if len(charts) > MAX_CHARTS:
        charts = charts[:MAX_CHARTS]
    fixed["charts"] = charts

    # Validate/normalize each subquery
    normalized_subq: List[Dict[str, Any]] = []
    for idx, sq in enumerate(subqueries):
        if not isinstance(sq, dict):
            errors.append(f"subqueries[{idx}] not an object, dropping")
            continue

        sq_fixed = dict(sq)
        # Required fields inside a subquery
        required_sq = ["id", "purpose", "tables", "columns", "filters", "group_by", "order_by", "limit"]
        for k in required_sq:
            if k not in sq_fixed:
                # Provide minimal defaults
                if k == "id":
                    sq_fixed[k] = f"q{idx+1}"
                elif k == "purpose":
                    sq_fixed[k] = "unspecified"
                elif k == "tables":
                    sq_fixed[k] = []
                elif k == "columns":
                    sq_fixed[k] = []
                elif k == "filters":
                    sq_fixed[k] = []
                elif k == "group_by":
                    sq_fixed[k] = None
                elif k == "order_by":
                    sq_fixed[k] = None
                elif k == "limit":
                    sq_fixed[k] = ROW_LIMIT

        # Enforce limit cap and type
        sq_fixed["limit"] = min(max(_coerce_int(sq_fixed.get("limit"), ROW_LIMIT), 1), ROW_LIMIT)

        # Ensure arrays for tables/columns/filters/group_by/order_by
        if not isinstance(sq_fixed.get("tables"), list):
            sq_fixed["tables"] = []
        if not isinstance(sq_fixed.get("columns"), list):
            sq_fixed["columns"] = []
        if not isinstance(sq_fixed.get("filters"), list):
            sq_fixed["filters"] = []
        # group_by/order_by may be None or list
        if sq_fixed.get("group_by") is not None and not isinstance(sq_fixed.get("group_by"), list):
            sq_fixed["group_by"] = [str(sq_fixed["group_by"])]
        if sq_fixed.get("order_by") is not None and not isinstance(sq_fixed.get("order_by"), list):
            sq_fixed["order_by"] = [str(sq_fixed["order_by"])]

        normalized_subq.append(sq_fixed)

    fixed["subqueries"] = normalized_subq

    # Validate charts structure
    normalized_charts: List[Dict[str, Any]] = []
    for idx, ch in enumerate(charts):
        if not isinstance(ch, dict):
            errors.append(f"charts[{idx}] not an object, dropping")
            continue
        ch_fixed = dict(ch)
        # Required minimal fields
        for k in ["id", "type", "from", "x", "y", "title"]:
            if k not in ch_fixed:
                ch_fixed[k] = "" if k != "type" else "bar"
        # Optional series can be absent
        normalized_charts.append(ch_fixed)
    fixed["charts"] = normalized_charts

    # Ensure max_items echoes cap
    fixed["max_items"] = MAX_SUBQUERIES

    return (len(errors) == 0, errors, fixed)


def plan_queries(question: str, entities: Dict[str, Any], server_type: str = "remote") -> Dict[str, Any]:
    """
    Build a planning prompt, call LLM, parse and validate the plan, and enforce caps.

    Args:
        question: natural language question
        entities: dict with possible keys: {"players": [...], "teams": [...], "timeframe": {...}}
        server_type: "local" or "remote"

    Returns:
        Validated plan dict with enforced caps.
    """
    constraints = get_constraints()
    planner_prompt = _read_text(PLANNER_PROMPT_PATH)
    schema_summary = get_schema_summary()

    # Assemble input payload to append to the planner prompt
    input_payload = {
        "user_question": question,
        "schema_summary": schema_summary,
        "entities": entities or {},
        "constraints": constraints,
        "server_type": server_type,
    }

    prompt_text = f"{planner_prompt}\n\nINPUT:\n{json.dumps(input_payload, ensure_ascii=False)}"
    from llm_wrapper import get_global_llm
    llm = get_global_llm()
    raw = llm.generate_content(prompt_text, timeout=LLM_TIMEOUT_SEC)

    plan_obj = _extract_json(raw)
    ok, errs, fixed = validate_plan(plan_obj)

    # We return the fixed plan regardless; surface validation notes if needed.
    if not ok:
        fixed["_validation_warnings"] = errs

    return fixed


def _extract_json_block(text: str) -> Dict[str, Any]:
    """
    Extract JSON from a ```json fenced block. Fallback to _extract_json if not found.
    """
    text = (text or "").strip()
    m = re.search(r"```json(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        return json.loads(candidate)
    # Fallback: try generic JSON extraction
    return _extract_json(text)


def plan_questions_nl(question: str, entities: Dict[str, Any], server_type: str = "remote") -> Dict[str, Any]:
    """
    NL-only planner:
    - Reads prompts/prompt3_planner_nl.txt
    - Passes SCHEMA_SUMMARY as the schema context
    - Returns a dict with keys: intent, entities, questions, max_items
    - Enforces caps on questions length and ensures timeframe is present in entities
    """
    constraints = get_constraints()

    # Ensure timeframe default if not provided by caller
    ent = dict(entities or {})
    if isinstance(ent, dict) and "timeframe" not in ent:
        ent["timeframe"] = constraints.get("seasons_policy", {"type": "last_n", "n": 10})

    planner_prompt = _read_text(PLANNER_NL_PROMPT_PATH)
    input_payload = {
        "user_question": question,
        "schema_summary": SCHEMA_SUMMARY,
        "entities": ent,
        "constraints": {
            "max_subqueries": constraints.get("max_subqueries"),
            "seasons_policy": constraints.get("seasons_policy"),
            "allow_multi_entity": constraints.get("allow_multi_entity"),
        },
        "server_type": server_type,
    }
    prompt_text = f"{planner_prompt}\n\nINPUT:\n{json.dumps(input_payload, ensure_ascii=False)}"

    from llm_wrapper import get_global_llm
    llm = get_global_llm()
    raw = llm.generate_content(prompt_text, timeout=LLM_TIMEOUT_SEC)

    # Parse JSON plan from Reasoning+JSON response
    try:
        plan_obj = _extract_json_block(raw)
    except Exception:
        plan_obj = _extract_json(raw)

    # Normalize minimal structure
    plan_fixed: Dict[str, Any] = {
        "intent": plan_obj.get("intent", "player_insight"),
        "entities": plan_obj.get("entities", ent),
        "questions": plan_obj.get("questions", []),
        "max_items": MAX_SUBQUERIES,
    }

    # Enforce caps on questions
    qs = plan_fixed.get("questions", [])
    if isinstance(qs, list) and len(qs) > MAX_SUBQUERIES:
        plan_fixed["questions"] = qs[:MAX_SUBQUERIES]

    # Ensure timeframe in entities
    ents = plan_fixed.get("entities") or {}
    if "timeframe" not in ents:
        ents["timeframe"] = constraints.get("seasons_policy", {"type": "last_n", "n": 10})
    plan_fixed["entities"] = ents

    return plan_fixed


# CLI for quick manual check (optional)
if __name__ == "__main__":
    demo_entities = {"players": ["Erling Haaland", "Mohamed Salah"]}
    demo_question = "Compare Haaland and Salah over the last 3 seasons for goals and assists."
    result = plan_queries(demo_question, demo_entities, server_type="remote")
    print(json.dumps(result, indent=2))
