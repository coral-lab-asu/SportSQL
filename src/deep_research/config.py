#!/usr/bin/env python3
"""
Global configuration for the Comprehensive Insights mode.

All limits and feature flags are centralized here for easy tuning.
"""

from typing import Dict, Any

# Seasons policy: default to last N seasons from player_history
DEFAULT_SEASONS_POLICY: Dict[str, Any] = {"type": "last_n", "n": 10}

# Hard caps
MAX_SUBQUERIES: int = 10         # Maximum number of planned subqueries per insights request
ROW_LIMIT: int = 10               # LIMIT applied to each generated SQL
MAX_CHARTS: int = 5               # Maximum number of charts per report

# Features
ALLOW_MULTI_ENTITY: bool = True   # Allow comparisons across 2+ entities (players/teams)
ALLOW_WINDOW_FUNCTIONS: bool = False  # Keep SQL simple initially (flip later if needed)

# Timeouts (seconds)
SQL_TIMEOUT_SEC: int = 15
LLM_TIMEOUT_SEC: int = 30

# Debug / Transparency
ENABLE_PLAN_DEBUG: bool = True    # Echo planned subqueries in API response for transparency


def get_constraints() -> Dict[str, Any]:
    """
    Return a dict of constraints to pass into the planner prompt and validation layer.
    """
    return {
        "seasons_policy": DEFAULT_SEASONS_POLICY,
        "max_subqueries": MAX_SUBQUERIES,
        "row_limit": ROW_LIMIT,
        "max_charts": MAX_CHARTS,
        "allow_multi_entity": ALLOW_MULTI_ENTITY,
        "allow_window_functions": ALLOW_WINDOW_FUNCTIONS,
        "sql_timeout_sec": SQL_TIMEOUT_SEC,
        "llm_timeout_sec": LLM_TIMEOUT_SEC,
        "enable_plan_debug": ENABLE_PLAN_DEBUG,
    }
