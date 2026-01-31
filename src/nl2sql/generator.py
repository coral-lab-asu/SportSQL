# gemini_api_runtime.py - PostgreSQL focused
import sys
import json
import re
import os
from io import BytesIO

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from src.database.config import get_db_config, get_engine
from src.llm.wrapper import get_global_llm

load_dotenv()

# Database configuration now handled by db_config module
db_config = get_db_config()

PROMPT_DIR = os.path.join(os.path.dirname(__file__), os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "llm", "prompts"))
EXTRACT_PROMPT_PATH = os.path.join(PROMPT_DIR, "prompt1_extract.txt")
BASE_PROMPT_PATH    = os.path.join(PROMPT_DIR, "prompt2_sql.txt")

STATIC_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_PATH   = os.path.join(STATIC_DIR, "visualization.png")

# ----------- DB ENGINE -----------
# Use the centralized engine from db_config
engine = get_engine()

# ----------- HELPERS -----------
def extract_sql(output: str) -> str:
    """
    Pull SQL between ```sql ... ``` fences, or return raw if it looks like SQL.
    """
    output = output.strip()
    m = re.search(r"```sql(.*?)```", output, re.DOTALL | re.IGNORECASE)
    if m:
        sql_code = m.group(1).strip()
    elif "select" in output.lower():
        sql_code = output
    else:
        return ""
    return " ".join(sql_code.split())

def run_select(sql: str):
    """Return (rows, headers) for a SELECT."""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = [tuple(row) for row in result.fetchall()]
        headers = list(result.keys())
    return rows, headers

def write_df(df: pd.DataFrame, table: str, mode="replace"):
    df.to_sql(table, engine, if_exists=mode, index=False, method="multi", chunksize=1000)

def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ensure_static_dir():
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR, exist_ok=True)

# ----------- PROMPTS -----------
EXTRACT_CONTEXT = load_text(EXTRACT_PROMPT_PATH)
BASE_CONTEXT    = load_text(BASE_PROMPT_PATH)

# ----------- LLM SETUP -----------
def get_llm_model():
    """Get the configured LLM model (Gemini by default, OpenAI if specified)."""
    return get_global_llm()

# ----------- CORE FUNCTIONS -----------
def generate_sql(question: str) -> str:
    """
    1) Use EXTRACT_CONTEXT to get a 'name lookup' SQL, run it, feed rows back.
    2) Use BASE_CONTEXT + question + names to get final SQL.
    """
    llm = get_llm_model()

    # Step 1: get name-extract SQL
    resp1_text = llm.generate_content(
        EXTRACT_CONTEXT + question,
        timeout=30
    )
    sql_extract = extract_sql(resp1_text)
    if not sql_extract:
        return ""

    name_rows, name_headers = run_select(sql_extract)
    name_context = {"headers": list(name_headers), "rows": name_rows}

    # Step 2: final SQL
    prompt2 = BASE_CONTEXT + question + json.dumps(name_context)
    resp2_text = llm.generate_content(
        prompt2,
        timeout=30
    )
    final_sql = extract_sql(resp2_text)
    return final_sql

def generate_visualization(question: str, data: dict | list | pd.DataFrame) -> bool:
    """
    Build a matplotlib plot from data using LLM-generated code.
    Saves to static/visualization.png.
    Returns True/False.
    """
    try:
        llm = get_llm_model()

        # Normalize data to DataFrame
        if isinstance(data, dict) and "headers" in data and "rows" in data:
            df = pd.DataFrame(data["rows"], columns=data["headers"])
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            df = pd.DataFrame(data)

        data_description = (
            f"Data columns: {', '.join(df.columns.astype(str).tolist())}\n"
            f"Number of rows: {len(df)}\n"
            "Data rows:\n"
            f"{df.to_string()}\n"
        )

        viz_prompt = f"""
I have the following data from a SQL query about Premier League soccer:

{data_description}

The query was asking: "{question}"

Possible chart types: Bar, Line, Scatter, Boxplot, Pie, Stacked Area.

Choose the best one and generate **only Python code** (no imports, no functions) using matplotlib to:
1. Build the visualization with the provided DataFrame `df`
2. Add title, axis labels, and any necessary annotations
3. Save to 'static/visualization.png' with plt.savefig('static/visualization.png')
4. Handle simple type issues
DO NOT use plt.close() in the code.
"""

        resp_text = llm.generate_content(
            viz_prompt,
            timeout=45
        )
        code_block = re.search(r"```python(.*?)```", resp_text or "", re.DOTALL | re.IGNORECASE)
        if not code_block:
            return False

        viz_code = code_block.group(1).strip()

        # Execute code
        ensure_static_dir()
        plt.figure(figsize=(10, 6))
        exec(
            viz_code,
            {"df": df, "plt": plt, "np": np, "pd": pd}
        )

        plt.savefig(PLOT_PATH, bbox_inches="tight", dpi=300, format="png", facecolor="white")
        plt.close()

        return os.path.exists(PLOT_PATH) and os.path.getsize(PLOT_PATH) > 0

    except Exception as e:
        print(f"Error generating visualization: {e}")
        import traceback
        print(traceback.format_exc())
        try:
            plt.close()
        except Exception:
            pass
        return False

# ----------- CLI -----------
def main():
    if len(sys.argv) < 3:
        print("Usage: python gemini_api_runtime.py [sql|viz] \"question\" [data_json]")
        sys.exit(1)

    op    = sys.argv[1].lower()
    query = sys.argv[2]

    if op == "sql":
        sql_query = generate_sql(query)
        print(sql_query)

    elif op == "viz":
        if len(sys.argv) < 4:
            print("Error: Data JSON required for visualization")
            sys.exit(1)
        data = json.loads(sys.argv[3])
        ok = generate_visualization(query, data)
        print(json.dumps({"success": ok, "path": "static/visualization.png" if ok else None}))

    else:
        print(f"Unknown operation '{op}'")
        sys.exit(1)

if __name__ == "__main__":
    main()
