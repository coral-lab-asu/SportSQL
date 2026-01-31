#!/usr/bin/env python3
"""
Execute compiled SQL queries with Enhanced Batch Pre-populate Strategy.

Key improvements:
- Batch pre-populate all on-demand tables with ALL required players
- Execute all queries against the same consistent dataset
- Store outputs of every query with proper formatting

Usage:
  python -m SportSQL.run_execute_plans --input compiled_sql_output.json --output execution_results.json
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Set
from datetime import datetime, date
from decimal import Decimal

from SportSQL.mariadb_access import return_query, update_player_data
from SportSQL.player_refresh import refresh_players_with_like_and_llm, cleanup_on_demand_tables, _ensure_on_demand_tables_schema



def populate_for_plan(entities: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure fresh schema and populate on-demand tables for a single plan."""
    # Always start with a clean schema for this plan
    try:
        _ensure_on_demand_tables_schema()
    except Exception as e:
        return {"status": "error", "error": f"schema init failed: {e}"}
    
    # Prefer explicit player_ids if provided
    try:
        player_ids = list(dict.fromkeys((entities or {}).get("player_ids") or []))
    except Exception:
        player_ids = []
    
    summary: Dict[str, Any] = {
        "status": "success",
        "player_count": len(player_ids),
        "updated_ok": [],
        "updated_fail": []
    }
    
    if player_ids:
        for pid in player_ids:
            try:
                ok = bool(update_player_data(int(pid)))
                if ok:
                    summary["updated_ok"].append(int(pid))
                else:
                    summary["updated_fail"].append({"pid": int(pid), "error": "update_player_data returned False"})
            except Exception as e:
                summary["updated_fail"].append({"pid": int(pid), "error": str(e)})
        if summary["updated_fail"]:
            summary["status"] = "partial" if summary["updated_ok"] else "error"
        return summary
    
    # Fallback: if no IDs but names exist, resolve and populate via refresh utility
    if (entities or {}).get("players"):
        try:
            refresh_result = refresh_players_with_like_and_llm(entities, include_debug=False)
            summary["refresh_result"] = refresh_result
            return summary
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    return {"status": "skipped", "reason": "no player_ids or player names in entities"}


def execute_sql_query(sql: str) -> Dict[str, Any]:
    """Execute a single SQL query and return formatted results."""
    if not sql or not sql.strip():
        return {
            "success": False,
            "error": "Empty SQL query",
            "data": None,
            "row_count": 0
        }
    
    try:
        # Execute query via mariadb_access
        raw_result = return_query(sql)
        parsed_result = json.loads(raw_result)
        
        # Check for database errors
        if "error" in parsed_result:
            return {
                "success": False,
                "error": parsed_result["error"],
                "data": None,
                "row_count": 0
            }
        
        # Extract data
        headers = parsed_result.get("headers", [])
        rows = parsed_result.get("rows", [])
        
        return {
            "success": True,
            "error": None,
            "data": {
                "headers": headers,
                "rows": rows
            },
            "row_count": len(rows)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "data": None,
            "row_count": 0
        }


def execute_plan_queries(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Execute all subqueries for a single plan."""
    subquestions = plan.get("compiled_subquestions", [])
    executed_queries = []
    
    for subq in subquestions:
        sql = subq.get("sql", "")
        
        # Execute the query
        execution_result = execute_sql_query(sql)
        
        # Build result record
        query_result = {
            "id": subq.get("id"),
            "question": subq.get("question"),
            "table_hint": subq.get("table_hint"),
            "sql": sql,
            "valid": subq.get("valid", False),
            "notes": subq.get("notes", []),
            "execution": execution_result
        }
        
        executed_queries.append(query_result)
        
        # Log execution status
        status = "✅" if execution_result["success"] else "❌"
        row_count = execution_result["row_count"]
        print(f"  {status} {subq.get('id')}: {row_count} rows")
    
    return {
        "index": plan.get("index"),
        "question": plan.get("question"),
        "entities": plan.get("entities"),
        "subqueries": executed_queries,
        "total_queries": len(executed_queries),
        "successful_queries": sum(1 for q in executed_queries if q["execution"]["success"])
    }


def main():
    parser = argparse.ArgumentParser(description="Execute compiled SQL queries with batch pre-populate")
    parser.add_argument("--input", "-i", required=True, help="Path to compiled SQL JSON file")
    parser.add_argument("--output", "-o", required=True, help="Path to write execution results")
    parser.add_argument("--server", choices=["local", "remote"], default="local", help="Database server type")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON")
    args = parser.parse_args()

    # Ensure db_config sees the server type by checking sys.argv
    if "--server" not in " ".join(sys.argv):
        sys.argv.extend(["--server", args.server])

    # Load compiled plans
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            plans = json.load(f)
        print(f"[INFO] Loaded {len(plans)} compiled plans from {args.input}")
    except Exception as e:
        sys.stderr.write(f"[FATAL] Failed to load '{args.input}': {e}\n")
        sys.exit(1)

    # Per-plan population will be performed inside the execution loop

    # Phase 3: Execute all queries
    execution_results = []
    start_time = datetime.now()
    
    for i, plan in enumerate(plans, 1):
        print(f"[INFO] Executing plan {i}/{len(plans)}: {plan.get('question', 'Unknown')[:60]}...")
        populate_result = {}
        try:
            # Per-plan isolation: reset schema and populate required players for this plan
            entities = plan.get("entities") or {}
            populate_result = populate_for_plan(entities)
        except Exception as e:
            populate_result = {"status": "error", "error": str(e)}
        
        try:
            plan_result = execute_plan_queries(plan)
            plan_result["populate"] = populate_result
            execution_results.append(plan_result)
        except Exception as e:
            print(f"[ERROR] Plan {i} failed: {e}")
            execution_results.append({
                "index": plan.get("index"),
                "question": plan.get("question"),
                "entities": plan.get("entities"),
                "populate": populate_result,
                "error": str(e),
                "subqueries": []
            })
        finally:
            # Clean up on-demand tables after this question
            cleanup_on_demand_tables()

    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    # Phase 4: Build final output
    final_output = {
        "metadata": {
            "input_file": args.input,
            "execution_time_seconds": round(execution_time, 2),
            "timestamp": end_time.isoformat(),
            "total_plans": len(plans),
            "successful_plans": len([r for r in execution_results if "error" not in r]),
            "populate_scope": "per-plan"
        },
        "results": execution_results
    }

    # Phase 5: Write results
    def _json_default(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            if args.compact:
                json.dump(final_output, f, ensure_ascii=False, separators=(",", ":"), default=_json_default)
            else:
                json.dump(final_output, f, ensure_ascii=False, indent=2, default=_json_default)
        
        print(f"\n[SUCCESS] Execution complete!")
        print(f"  � {len(execution_results)} plans executed in {execution_time:.2f}s")
        print(f"  �� Results written to {args.output}")
        
    except Exception as e:
        sys.stderr.write(f"[FATAL] Failed to write '{args.output}': {e}\n")
        sys.exit(1)
    
    finally:
        # Phase 6: Cleanup on-demand tables
        print("[INFO] Cleaning up on-demand tables...")
        cleanup_on_demand_tables()


if __name__ == "__main__":
    main()
