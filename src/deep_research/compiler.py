#!/usr/bin/env python3
"""
NL sub-questions -> SQL compiler aligned with prompt2_sql.

For each natural-language sub-question (from the NL planner), we build a constrained prompt
based on prompts/prompt2_sql.txt to produce a single PostgreSQL-compliant SELECT statement.
We then validate and optionally correct the SQL.

Public API:
- compile_questions_to_sql(nl_questions: list[dict], entities: dict, server_type: str = "remote") -> list[dict]
  Each nl_question item: {"id": "s1", "question": "...", "table_hint": "players|player_history|teams|fixtures|player_past" (optional)}
  Returns: [{"id","question","sql","notes":[...],"valid": bool}]
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from src.deep_research.config import ROW_LIMIT, LLM_TIMEOUT_SEC, get_constraints

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "llm", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "llm", "prompts"))
PROMPT2_PATH = os.path.join(PROMPTS_DIR, "prompt2_sql.txt")


# -------------- Utilities --------------

def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_sql(text: str) -> str:
    """
    Extract SQL from a ```sql fenced block if present. Otherwise, if it looks like a SELECT query,
    return the raw string (normalized spaces).
    """
    if not text:
        return ""
    m = re.search(r"```sql(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        sql = m.group(1).strip()
        return " ".join(sql.split())
    # fallback: raw SELECT
    if re.search(r"\bselect\b", text, re.IGNORECASE):
        # try to take until the last semicolon or end of string
        # keep the line(s) that look like SQL text
        # naive approach: pick first 'select' through end
        start = re.search(r"\bselect\b", text, re.IGNORECASE).start()
        sql = text[start:].strip()
        # cut at first triple backticks if any
        fence = sql.find("```")
        if fence != -1:
            sql = sql[:fence]
        # only keep first statement (split by ; )
        parts = sql.split(";")
        if parts:
            sql = parts[0]
        return " ".join(sql.split())
    return ""


# We allow CTEs (WITH ...) because prompt2 examples include them.
_MUTATION_KEYWORDS = re.compile(r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE|CREATE)\b", re.IGNORECASE)

def _has_disallowed_keywords(sql: str) -> bool:
    return bool(_MUTATION_KEYWORDS.search(sql or ""))


def _has_player_filter_in_history_tables(sql: str) -> bool:
    """
    Detect potential direct player filtering in player_history/past/future (we want to avoid it).
    """
    if not sql:
        return False
    # check for common player identifiers in WHERE
    # naive: if 'where' present and words first_name|second_name|player_id appear near it.
    if re.search(r"\bwhere\b", sql, re.IGNORECASE):
        if re.search(r"\b(first_name|second_name|player_id)\b", sql, re.IGNORECASE):
            return True
    return False


def _ensure_limit(sql: str, limit: int) -> Tuple[str, Optional[str]]:
    """
    Ensure the query has a LIMIT <= limit. If absent, append 'LIMIT limit'.
    If larger than limit, we leave as-is (LLM may be explicit) to avoid breaking semantics,
    but we add a note.
    """
    if not sql:
        return sql, None
    m = re.search(r"\blimit\s+(\d+)\b", sql, re.IGNORECASE)
    if m:
        try:
            current_lim = int(m.group(1))
            if current_lim > limit:
                return sql, f"LIMIT present ({current_lim}) exceeds cap ({limit}); left as-is."
            return sql, None
        except ValueError:
            # malformed LIMIT; append safe LIMIT
            return _append_limit(sql, limit), "Malformed LIMIT detected; appended safe LIMIT."
    else:
        return _append_limit(sql, limit), f"LIMIT not found; appended LIMIT {limit}."


def _append_limit(sql: str, limit: int) -> str:
    # If the SQL ends with semicolon, insert before it; else append at end.
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return f"{sql} LIMIT {limit}"


def _llm_fix_sql(sql: str) -> Tuple[str, List[str]]:
    """Use the LLM to validate/fix SQL for PostgreSQL constraints.
    On failure or blank, return original SQL.
    """
    notes: List[str] = []
    try:
        # Lazy imports to avoid load-time dependencies
        from src.llm.wrapper import get_global_llm
        from src.deep_research.schema import SCHEMA_SUMMARY
        from src.deep_research.config import LLM_TIMEOUT_SEC

        prompt = (
            "You are a PostgreSQL SQL fixer.\n"
            "Constraints: single statement only; SELECT/WITH only; no mutations; keep LIMIT;\n"
            "Booleans must use TRUE/FALSE; When using aggregation (SUM/COUNT/AVG/MIN/MAX),\n"
            "ALL non-aggregate columns in SELECT must appear in GROUP BY.\n"
            "Do not change the intent or add new columns.\n\n"
            f"Schema summary:\n{SCHEMA_SUMMARY}\n\n"
            "Original SQL (may be imperfect):\n"
            f"{sql}\n\n"
            "Return ONLY the fixed SQL in a ```sql fenced block. No explanations."
        )
        llm = get_global_llm()
        raw = llm.generate_content(prompt, timeout=LLM_TIMEOUT_SEC)
        fixed = extract_sql(raw)
        if fixed and re.match(r"^\s*(SELECT|WITH)\b", fixed, re.IGNORECASE):
            notes.append("llm_fix_applied")
            return fixed, notes
        notes.append("llm_fix_failed")
        return sql, notes
    except Exception as e:
        notes.append(f"llm_fix_error:{e}")
        return sql, notes


def validate_sql(sql: str, table_hint: Optional[str]) -> Tuple[bool, str, List[str], Optional[str]]:
    """
    Validate SQL according to rules:
    - single statement, SELECT/WITH only (no mutations)
    - limit enforcement
    - avoid player-name filters for history tables
    Returns: (ok, fixed_sql, notes, retry_reason)
    """
    notes: List[str] = []
    retry_reason: Optional[str] = None
    if not sql:
        return False, sql, ["Empty SQL from model"], "empty_sql"

    # must start with SELECT or WITH
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        return False, sql, ["Non-SELECT/CTE SQL emitted"], "non_select"

    # single statement: crude check - disallow additional semicolons in middle
    # we ignore a trailing semicolon by trimming
    sql_trim = sql.strip().rstrip(";")
    if ";" in sql_trim:
        notes.append("Multiple statements detected; only first will be considered.")
        sql_trim = sql_trim.split(";")[0]

    # disallowed keywords (mutations)
    if _has_disallowed_keywords(sql_trim):
        return False, sql_trim, ["Mutation keywords detected"], "mutation"

    # limit
    sql_with_limit, limit_note = _ensure_limit(sql_trim, ROW_LIMIT)
    if limit_note:
        notes.append(limit_note)

    # LLM-based post-validation/fix; fallback to the original if it fails/blank
    sql_fixed_llm, llm_notes = _llm_fix_sql(sql_with_limit)
    notes.extend(llm_notes)

    # No need for programmatic JOINs - player names are now in the tables
    return True, sql_fixed_llm, notes, None


def _build_compiler_prompt(base_prompt: str,
                           sub_question: str,
                           entities: Dict[str, Any],
                           table_hint: Optional[str],
                           server_type: str,
                           corrective_note: Optional[str] = None) -> str:
    """
    Compose the text2sql prompt for a single sub-question.
    """
    constraints = get_constraints()
    eff_limit = constraints.get("row_limit", ROW_LIMIT)
    timeframe = entities.get("timeframe") or constraints.get("seasons_policy", {"type": "last_n", "n": 10})
    players = entities.get("players", [])
    teams = entities.get("teams", [])
    player_ids = entities.get("player_ids", [])

    header = f"""
You are an expert in semantic parsing. Translate the given English question into a single MariaDB-compatible SELECT statement.
Rules:
- Output ONLY a fenced code block marked as ```sql with the query inside (no prose outside).
- No comments in the SQL. Single statement only (no multiple statements).
- If the result could be large, include LIMIT {eff_limit}.
- If entities.player_ids is present and the candidate table is player_history, player_past, or player_future, include a WHERE player_id IN (...).
- If the candidate table is player_history, player_past, or player_future and entities.player_ids is NOT present, return an empty ```sql``` fenced block (no query).
- Dialect: If server_type == "local" (PostgreSQL), use booleans TRUE/FALSE; if "remote" (MySQL), use 1/0.
- Prefer concise column selection that directly answers the question.

Context:
- Players: {players}
- Player IDs: {player_ids}
- Teams: {teams}
- Timeframe: {json.dumps(timeframe)}
- Candidate table: {table_hint or "unspecified"}
- Server type: {server_type}
""".strip()

    if corrective_note:
        header += f"\n- Correction: {corrective_note}"

    body = f"""
English Question:
{sub_question}

Now return ONLY the SQL in a fenced block:
```sql
-- your query here
```
""".strip()

    # base_prompt (prompt2_sql) already includes schema + examples. We append our header/body.
    full_prompt = f"{base_prompt}\n\n{header}\n\n{body}"
    return full_prompt


def _call_llm(prompt: str) -> str:
    from src.llm.wrapper import get_global_llm
    llm = get_global_llm()
    return llm.generate_content(prompt, timeout=LLM_TIMEOUT_SEC)


def _compile_single(base_prompt: str,
                    subq: Dict[str, Any],
                    entities: Dict[str, Any],
                    server_type: str) -> Tuple[str, List[str], bool]:
    """
    Compile a single NL sub-question to SQL with up to one corrective retry.
    Returns: (sql, notes, valid)
    """
    qtext = subq.get("question", "")
    table_hint = subq.get("table_hint")
    notes: List[str] = []

    # Short-circuit: require player_ids for on-demand tables
    if table_hint in {"player_history", "player_past", "player_future"}:
        pids = entities.get("player_ids") or []
        if not pids:
            notes.append("skipped: missing player_ids for on-demand table")
            return "", notes, False

    # First attempt
    prompt = _build_compiler_prompt(base_prompt, qtext, entities, table_hint, server_type, None)
    raw = _call_llm(prompt)
    sql = extract_sql(raw)
    ok, fixed, vnotes, retry_reason = validate_sql(sql, table_hint)
    notes.extend(vnotes)
    if ok:
        return fixed, notes, True

    # Retry with corrective instruction if applicable
    corrective = None
    if retry_reason == "history_table_player_filter":
        corrective = "Do not filter by first_name, second_name, or player_id when using player_history/player_past/player_future."
    elif retry_reason == "non_select":
        corrective = "Return a SELECT or WITH query only; no mutations or prose."
    elif retry_reason == "empty_sql":
        corrective = "You must output a single SQL statement. Do not leave empty."
    elif retry_reason == "mutation":
        corrective = "Do not use INSERT/UPDATE/DELETE/ALTER/DROP/TRUNCATE/CREATE. Only SELECT/CTE."
    # else: other failures -> no corrective

    if corrective:
        prompt2 = _build_compiler_prompt(base_prompt, qtext, entities, table_hint, server_type, corrective)
        raw2 = _call_llm(prompt2)
        sql2 = extract_sql(raw2)
        ok2, fixed2, vnotes2, _ = validate_sql(sql2, table_hint)
        notes.extend(vnotes2)
        if ok2:
            return fixed2, notes, True
        return fixed2 or sql2 or sql, notes, False

    return fixed or sql, notes, False


# -------------- Public API --------------

def compile_questions_to_sql(nl_questions: List[Dict[str, Any]],
                             entities: Dict[str, Any],
                             server_type: str = "remote") -> List[Dict[str, Any]]:
    """
    Compile a list of NL sub-questions to SQL statements.

    Returns list of:
      {
        "id": question_id,
        "question": sub_question,
        "sql": sql_text,
        "notes": [warnings],
        "valid": bool
      }
    """
    base_prompt = _read_text(PROMPT2_PATH)
    results: List[Dict[str, Any]] = []
    for item in nl_questions or []:
        qid = item.get("id") or ""
        sql, notes, valid = _compile_single(base_prompt, item, entities or {}, server_type)
        results.append({
            "id": qid,
            "question": item.get("question", ""),
            "sql": sql,
            "notes": notes,
            "valid": bool(valid),
        })
    return results
