#!/usr/bin/env python3
"""
Compile-only pipeline:
- Reads planner output JSON (array) produced by the NL planner
- Refreshes player data and populates on-demand tables (player_history, player_past, player_future)
- Uses prompt2_sql via insights_sql_compiler to compile each NL sub-question into a single SQL statement
- Writes a JSON file with compiled SQL per sub-question
- NO SQL execution happens here (compile only)

Usage:
  python -m SportSQL.run_compile_only --input SportSQL/planneer_output.json --output compiled_sql_output.json --server local

Options:
  --input / -i            Path to planner output JSON (array). Default: SportSQL/planneer_output.json
  --output / -o           Path to write compiled SQL JSON. Default: compiled_sql_output.json
  --server                'local' (PostgreSQL) or 'remote' (MySQL). Default: local
  --augment-player-ids    If set, try to augment entities with player_ids from update_player_mappings/player_id_map.json
  --no-refresh            Skip player refresh and on-demand table population (legacy behavior)
  --debug                 Include refresh diagnostics in output
  --compact               Write compact JSON (no indentation)
"""

from __future__ import annotations

import argparse
import json
import time
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal

from SportSQL.insights_sql_compiler import compile_questions_to_sql
from SportSQL.player_refresh import refresh_players_with_like_and_llm, extract_player_ids_from_refresh_map, cleanup_on_demand_tables, get_refresh_debug_info


DEFAULT_INPUT = "SportSQL/planneer_output.json"
DEFAULT_OUTPUT = "compiled_sql_output.json"
PLAYER_ID_MAP_PATH = os.path.join(os.path.dirname(__file__), "update_player_mappings", "player_id_map.json")


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def _save_json(path: str, data: Any, compact: bool = False) -> None:
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"), default=_json_default)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)


def _load_player_id_map(path: str) -> Dict[str, int]:
    """
    Load a simple mapping of player name(s) -> player_id.
    Supports exact keys as present in the JSON. For robustness we also build a lowercase key map.
    """
    try:
        raw = _load_json(path)
        if not isinstance(raw, dict):
            return {}
        # Build a case-insensitive overlay
        lower_map: Dict[str, int] = {}
        for k, v in raw.items():
            if isinstance(k, str):
                lower_map[k.strip().lower()] = int(v) if isinstance(v, (int, str)) and str(v).isdigit() else v
        return lower_map
    except Exception:
        return {}


def _augment_player_ids(entities: Dict[str, Any], pid_map: Dict[str, int]) -> Dict[str, Any]:
    """
    If entities.players is present, try to look up IDs from pid_map and add entities.player_ids.
    Names are matched case-insensitively on the full string provided.
    """
    ents = dict(entities or {})
    players = ents.get("players") or []
    if not isinstance(players, list) or not pid_map:
        return ents

    ids: List[int] = []
    for name in players:
        if not isinstance(name, str):
            continue
        key = name.strip().lower()
        pid = pid_map.get(key)
        try:
            pid_int = int(pid) if pid is not None else None
        except Exception:
            pid_int = None
        if pid_int:
            ids.append(pid_int)

    if ids:
        ents["player_ids"] = ids
    return ents


def _compile_entry(entry: Dict[str, Any],
                   server_type: str,
                   augment_player_ids: bool,
                   pid_map: Dict[str, int],
                   refresh_players: bool = True,
                   include_debug: bool = False) -> Dict[str, Any]:
    """
    Compile NL sub-questions for a single planner entry.
    """
    index = entry.get("index")
    top_question = entry.get("question")

    plan_obj = entry.get("plan") or {}
    # Prefer explicit 'entities' field on entry, fallback to plan.entities
    base_entities: Dict[str, Any] = entry.get("entities") or plan_obj.get("entities") or {}
    nl_questions: List[Dict[str, Any]] = plan_obj.get("questions") or []

    entities = base_entities
    refresh_debug = None
    
    # Step 1: Player refresh (populate on-demand tables and get player_ids)
    if refresh_players and entities.get("players"):
        refresh_map = refresh_players_with_like_and_llm(entities, include_debug=include_debug)
        resolved_player_ids = extract_player_ids_from_refresh_map(refresh_map)
        
        # Add resolved player_ids to entities
        entities = dict(entities)
        if resolved_player_ids:
            entities["player_ids"] = resolved_player_ids
            
        if include_debug:
            refresh_debug = {
                "players": refresh_map,
                **get_refresh_debug_info()
            }
    
    # Step 2: Legacy player ID augmentation (if requested)
    if augment_player_ids:
        entities = _augment_player_ids(entities, pid_map)

    # Compile via existing compiler (prompt2_sql)
    compiled = compile_questions_to_sql(nl_questions, entities or {}, server_type=server_type)

    # Cross-reference table_hint from original nl_questions by id
    # Build a small index of id -> table_hint
    hint_index: Dict[str, Optional[str]] = {}
    for q in nl_questions:
        qid = q.get("id")
        hint_index[str(qid) if qid is not None else ""] = q.get("table_hint")

    compiled_out: List[Dict[str, Any]] = []
    for qc in compiled or []:
        qid = qc.get("id") or ""
        compiled_out.append({
            "id": qid,
            "question": qc.get("question", ""),
            "table_hint": hint_index.get(str(qid), None),
            "sql": qc.get("sql", ""),
            "notes": qc.get("notes", []),
            "valid": bool(qc.get("valid", False)),
        })

    result = {
        "index": index,
        "question": top_question,
        "entities": entities,
        "compiled_subquestions": compiled_out
    }
    
    if refresh_debug:
        result["refresh_debug"] = refresh_debug
        
    return result


def main():
    parser = argparse.ArgumentParser(description="Compile NL sub-questions into SQL using prompt2_sql (no execution).")
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT, help="Path to planner output JSON (array)")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help="Path to write compiled SQL JSON")
    parser.add_argument("--server", choices=["local", "remote"], default="local", help="Database server type context for dialect hints")
    parser.add_argument("--augment-player-ids", action="store_true", help="Augment entities with player_ids from update_player_mappings/player_id_map.json")
    parser.add_argument("--no-refresh", action="store_true", help="Skip player refresh and on-demand table population")
    parser.add_argument("--debug", action="store_true", help="Include refresh diagnostics in output")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON (no indentation)")
    args = parser.parse_args()

    # Load planner output
    try:
        plans = _load_json(args.input)
        if not isinstance(plans, list):
            raise ValueError("Planner output must be a JSON array")
    except Exception as e:
        sys.stderr.write(f"[FATAL] Failed to read '{args.input}': {e}\n")
        sys.exit(1)

    # Optional mapping
    pid_map: Dict[str, int] = {}
    if args.augment_player_ids:
        pid_map = _load_player_id_map(PLAYER_ID_MAP_PATH)
        if not pid_map:
            sys.stderr.write("[WARN] --augment-player-ids provided but player_id_map.json could not be loaded or is empty.\n")

    results: List[Dict[str, Any]] = []
    for entry in plans:
        time.sleep(10)
        try:
            if not isinstance(entry, dict):
                continue
            results.append(_compile_entry(
                entry, 
                server_type=args.server, 
                augment_player_ids=args.augment_player_ids, 
                pid_map=pid_map,
                refresh_players=not args.no_refresh,
                include_debug=args.debug
            ))
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed compiling index={entry.get('index')}: {e}\n")
            results.append({
                "index": entry.get("index"),
                "question": entry.get("question"),
                "entities": entry.get("entities"),
                "error": str(e)
            })

    # Cleanup: drop on-demand tables if they were created
    if not args.no_refresh:
        cleanup_on_demand_tables()

    # Write output
    try:
        _save_json(args.output, results, compact=args.compact)
        print(f"Wrote compiled SQL for {len(results)} top-level plans to {args.output}")
    except Exception as e:
        sys.stderr.write(f"[FATAL] Failed to write output '{args.output}': {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
