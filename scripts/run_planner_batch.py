#!/usr/bin/env python3
"""
Batch runner for the NL Insights Planner.

Reads JSONL input where each line is a JSON object like:
  {"question": "...", "players": ["...","..."], "teams": ["...","..."]}

Writes a single JSON array file with entries:
  {
    "index": 1,
    "question": "...",
    "entities": {"players": [...], "teams": [...], "timeframe": {...}},
    "plan": { ... }  # the NL planner's JSON result
  }

Usage:
  python SportSQL/run_planner_batch.py --input SportSQL/planner_questions.jsonl --output planneer_output.json --server remote

Notes:
- The NL planner prompt outputs "Reasoning" + a fenced JSON block; our code extracts the JSON plan from that response already.
- If no entities are provided for a question, the planner may return empty "questions" by design.
"""

import argparse
import json
import sys
from typing import Any, Dict, List

# Absolute imports so this script can be run directly
from SportSQL.insights_planner import plan_questions_nl


def _parse_line(line: str) -> Dict[str, Any]:
    line = line.strip()
    if not line:
        return {}
    try:
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError("Line is not a JSON object")
        return obj
    except Exception as e:
        raise ValueError(f"Invalid JSONL line: {e}")


def _build_entities(obj: Dict[str, Any]) -> Dict[str, Any]:
    entities: Dict[str, Any] = {}
    players = obj.get("players")
    teams = obj.get("teams")

    if isinstance(players, str):
        players = [p.strip() for p in players.split(",") if p.strip()]
    if isinstance(teams, str):
        teams = [t.strip() for t in teams.split(",") if t.strip()]

    if isinstance(players, list) and players:
        entities["players"] = players
    if isinstance(teams, list) and teams:
        entities["teams"] = teams

    return entities


def main():
    parser = argparse.ArgumentParser(description="Batch NL planner runner")
    parser.add_argument("--input", "-i", required=True, help="Path to JSONL file with questions")
    parser.add_argument("--output", "-o", default="planneer_output.json", help="Path to write combined output JSON")
    parser.add_argument("--server", choices=["local", "remote"], default="remote", help="Server type context passed to planner")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON (no indentation)")
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output
    server = args.server
    compact = args.compact

    results: List[Dict[str, Any]] = []
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                try:
                    obj = _parse_line(line)
                    if not obj:
                        continue
                    question = obj.get("question", "")
                    if not isinstance(question, str) or not question.strip():
                        sys.stderr.write(f"[WARN] Skipping line {idx}: missing 'question'\n")
                        continue

                    entities = _build_entities(obj)
                    plan = plan_questions_nl(question, entities, server_type=server)

                    results.append({
                        "index": idx,
                        "question": question,
                        "entities": plan.get("entities", entities),
                        "plan": plan
                    })
                except Exception as e:
                    sys.stderr.write(f"[ERROR] Line {idx}: {e}\n")
                    continue

        with open(output_path, "w", encoding="utf-8") as out:
            if compact:
                json.dump(results, out, ensure_ascii=False, separators=(",", ":"))
            else:
                json.dump(results, out, ensure_ascii=False, indent=2)

        print(f"Wrote {len(results)} planned entries to {output_path}")

    except FileNotFoundError:
        sys.stderr.write(f"[FATAL] Input file not found: {input_path}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"[FATAL] {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
