#!/usr/bin/env python3
"""
Player refresh utilities for populating on-demand tables (player_history, player_past, player_future).
Extracted from run_execute_plans.py to be reusable in both compile-only and execute workflows.
"""

import json
from typing import Any, Dict, List
from src.database.operations import return_query, update_player_data
from src.database.config import get_engine
from src.database.schemas import PLAYER_HISTORY_SCHEMA, PLAYER_PAST_SCHEMA, PLAYER_FUTURE_SCHEMA, get_create_table_sql
from sqlalchemy import text


def _safe_query_json(sql: str) -> Dict[str, Any]:
    """
    Run a SQL and return a consistent dict:
      { "ok": bool, "headers": [...], "rows": [...], "error": str|None }
    """
    try:
        raw = return_query(sql)
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "error" not in parsed:
            return {"ok": True, "headers": parsed.get("headers"), "rows": parsed.get("rows"), "error": None}
        elif isinstance(parsed, dict):
            return {"ok": False, "headers": [], "rows": [], "error": parsed.get("error")}
        # unexpected shape
        return {"ok": True, "headers": [], "rows": parsed, "error": None}
    except Exception as e:
        return {"ok": False, "headers": [], "rows": [], "error": str(e)}


def _table_count(table: str) -> Any:
    """Get count of rows in a table."""
    q = _safe_query_json(f"SELECT COUNT(*) FROM {table}")
    if not q["ok"]:
        return {"error": q["error"]}
    try:
        rows = q.get("rows") or []
        return int(rows[0][0]) if rows and rows[0] else 0
    except Exception as e:
        return {"error": str(e)}


def _get_counts() -> Dict[str, Any]:
    """
    Snapshot counts for on-demand tables to verify writes:
    {"player_history": int|{"error":...}, "player_past": ..., "player_future": ...}
    """
    return {
        "player_history": _table_count("player_history"),
        "player_past": _table_count("player_past"),
        "player_future": _table_count("player_future"),
    }


def _sanitize_literal(s: str) -> str:
    """Basic SQL literal sanitization for inline usage."""
    return (s or "").replace("'", "''").strip()


def _like_candidates_for_name(name: str) -> List[Dict[str, Any]]:
    """
    Use substring match (LIKE) to get candidate players for a given name.
    Works across both first_name and second_name, case-insensitive via LOWER(...).
    Returns a list of dicts: [{"player_id": int, "first_name": str, "second_name": str, "team_name": str}]
    """
    name = (name or "").strip()
    if not name:
        return []
    parts = [p for p in name.split() if p]
    # Build WHERE clause: for multi-token names require each token to match either first or second name
    # ( (LOWER(first_name) LIKE '%tok%') OR (LOWER(second_name) LIKE '%tok%') ) AND ...
    clauses = []
    for tok in parts:
        tok_lit = _sanitize_literal(tok.lower())
        clauses.append(f"(LOWER(first_name) LIKE '%{tok_lit}%' OR LOWER(second_name) LIKE '%{tok_lit}%')")
    where = " AND ".join(clauses) if clauses else "1=0"
    sql = (
        "SELECT player_id, first_name, second_name, team_name "
        "FROM players "
        f"WHERE {where} "
        "ORDER BY total_points DESC NULLS LAST "
        f"LIMIT 25"
    )
    try:
        raw = return_query(sql)
        parsed = json.loads(raw)
        headers = parsed.get("headers", [])
        rows = parsed.get("rows", [])
        idx = {h: i for i, h in enumerate(headers)}
        out = []
        for r in rows or []:
            out.append({
                "player_id": r[idx.get("player_id")] if "player_id" in idx else None,
                "first_name": r[idx.get("first_name")] if "first_name" in idx else None,
                "second_name": r[idx.get("second_name")] if "second_name" in idx else None,
                "team_name": r[idx.get("team_name")] if "team_name" in idx else None,
            })
        return out
    except Exception:
        return []


def refresh_players_with_like_and_llm(entities: Dict[str, Any], include_debug: bool = False) -> Dict[str, Any]:
    """
    For each entity name in entities['players'], perform a LIKE-based candidate search,
    then pick player_id deterministically when possible, otherwise use LLM, and call update_player_data(player_id).
    Returns mapping per player with rich debug info if include_debug=True.
    """
    result: Dict[str, Any] = {}
    if not isinstance(entities, dict):
        return result
    players = entities.get("players") or []
    if not isinstance(players, list):
        return result
    
    # Ensure tables have the correct schema before any population
    _ensure_on_demand_tables_schema()
    
    seen = set()
    
    for name in players:
        if not isinstance(name, str):
            continue
        key = name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)

        # Find candidates
        cands = _like_candidates_for_name(name)
        cands_trim = cands[:5] if isinstance(cands, list) else []
        pid = 0
        llm_choice_raw = None

        # 1) Deterministic: exactly one candidate
        if isinstance(cands, list) and len(cands) == 1:
            pid = int(cands[0].get("player_id") or 0)

        # 2) Deterministic: exact match on full name or last name
        if pid == 0 and isinstance(cands, list) and len(cands) > 0:
            target = key
            # full exact match first_name + " " + second_name
            for cand in cands:
                fn = (str(cand.get("first_name") or "")).strip().lower()
                ln = (str(cand.get("second_name") or "")).strip().lower()
                if f"{fn} {ln}" == target:
                    pid = int(cand.get("player_id") or 0)
                    break
            # exact match on last name only
            if pid == 0:
                for cand in cands:
                    ln = (str(cand.get("second_name") or "")).strip().lower()
                    if ln == target:
                        pid = int(cand.get("player_id") or 0)
                        break

        # 3) LLM disambiguation if still unresolved
        if pid == 0:
            llm_choice_raw = ""
            try:
                from src.llm.wrapper import get_global_llm
                llm = get_global_llm()
                prompt = (
                    "You are matching a Premier League player name to a candidate list from a database.\n"
                    "Return ONLY the player_id (integer) of the best match. If no good match, return 0.\n\n"
                    f"Target name: {name}\n\n"
                    f"Candidates (JSON): {json.dumps(cands_trim, ensure_ascii=False)}\n"
                )
                resp = llm.generate_content(prompt, timeout=30)
                llm_choice_raw = resp
                nums = re.findall(r"\\d+", resp or "")
                pid = int(nums[0]) if nums else 0
            except Exception as _e:
                llm_choice_raw = f"LLM error: {_e}"
                pid = 0

        # 4) Final fallback: first candidate if any
        if pid == 0 and isinstance(cands, list) and len(cands) > 0:
            pid = int(cands[0].get("player_id") or 0)
            if llm_choice_raw is None:
                llm_choice_raw = "fallback:first_candidate"

        # Snapshot counts before update (if debug requested)
        before_counts = _get_counts() if include_debug else None

        updated = False
        update_error = None
        if pid > 0:
            try:
                updated = bool(update_player_data(pid))
            except Exception as e:
                updated = False
                update_error = str(e)

        # Snapshot counts after update (if debug requested)
        after_counts = _get_counts() if include_debug else None

        # Compute deltas where possible (if debug requested)
        delta = None
        if include_debug and before_counts and after_counts:
            def delta_for(tbl: str):
                b = before_counts.get(tbl)
                a = after_counts.get(tbl)
                if isinstance(b, dict) or isinstance(a, dict):
                    return "n/a"
                try:
                    return int(a) - int(b)
                except Exception:
                    return "n/a"

            delta = {
                "player_history": delta_for("player_history"),
                "player_past": delta_for("player_past"),
                "player_future": delta_for("player_future"),
            }

        # Build result entry
        entry = {
            "player_id": pid,
            "updated": updated,
        }
        
        if include_debug:
            entry.update({
                "cand_count": len(cands) if isinstance(cands, list) else 0,
                "candidates": cands_trim,
                "llm_choice_raw": llm_choice_raw,
                "before_counts": before_counts,
                "update_error": update_error,
                "after_counts": after_counts,
                "delta": delta,
            })
        elif update_error:
            entry["update_error"] = update_error

        result[name] = entry
        
    return result


def extract_player_ids_from_refresh_map(refresh_map: Dict[str, Any]) -> List[int]:
    """Extract valid player IDs from a refresh map."""
    try:
        return [int(v.get("player_id")) for v in (refresh_map or {}).values() 
                if isinstance(v, dict) and int(v.get("player_id") or 0) > 0]
    except Exception:
        return []


def _ensure_on_demand_tables_schema() -> None:
    """Ensure on-demand tables have the correct schema using master schema definitions."""
    try:
        eng = get_engine()
        with eng.connect() as conn:
            # Drop existing tables if they exist
            conn.execute(text("DROP TABLE IF EXISTS player_history"))
            conn.execute(text("DROP TABLE IF EXISTS player_past"))
            conn.execute(text("DROP TABLE IF EXISTS player_future"))
            conn.commit()
            
            # Create tables using master schemas
            conn.execute(text(get_create_table_sql("player_history", PLAYER_HISTORY_SCHEMA, False)))
            conn.execute(text(get_create_table_sql("player_past", PLAYER_PAST_SCHEMA, False)))
            conn.execute(text(get_create_table_sql("player_future", PLAYER_FUTURE_SCHEMA, False)))
            conn.commit()
            
            print("[INFO] On-demand tables created with standardized schemas")
                    
    except Exception as e:
        print(f"[ERROR] Failed to ensure on-demand tables schema: {e}")


def cleanup_on_demand_tables() -> None:
    """Drop on-demand tables created during refresh."""
    try:
        eng = get_engine()
        with eng.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS player_history"))
            conn.execute(text("DROP TABLE IF EXISTS player_past"))
            conn.execute(text("DROP TABLE IF EXISTS player_future"))
    except Exception as e:
        print(f"[WARN] Failed to drop on-demand tables: {e}")


def get_refresh_debug_info() -> Dict[str, Any]:
    """Get debug information about on-demand tables."""
    counts = {
        "player_history": _table_count("player_history"),
        "player_past": _table_count("player_past"),
        "player_future": _table_count("player_future"),
    }
    samples = {
        "player_history": _sample_table("player_history"),
        "player_past": _sample_table("player_past"),
        "player_future": _sample_table("player_future"),
    }
    return {
        "table_counts": counts,
        "samples": samples,
    }
