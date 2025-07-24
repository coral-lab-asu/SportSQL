# gemini_api_runtime.py
import sys
import json
import re
import os
from io import BytesIO

import google.generativeai as genai
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# ----------- ENV / CONFIG -----------
GEMINI_API_KEY = os.getenv("API_KEY")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

DB_HOST = os.getenv("DATABASE_HOST")
DB_USER = os.getenv("DATABASE_USER")
DB_PASS = os.getenv("DATABASE_PASSWORD")
DB_NAME = os.getenv("DATABASE_NAME")
DB_PORT = int(os.getenv("DATABASE_PORT", 3306))

PROMPT_DIR = "prompts"
EXTRACT_PROMPT_PATH = os.path.join(PROMPT_DIR, "prompt1_extract.txt")
BASE_PROMPT_PATH    = os.path.join(PROMPT_DIR, "prompt2_sql.txt")

STATIC_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_PATH   = os.path.join(STATIC_DIR, "visualization.png")

# ----------- DB ENGINE -----------
def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=1,
        max_overflow=2,
        connect_args={"connect_timeout": 10}
    )

engine = get_engine()

# ----------- HELPERS -----------
def extract_sql(output: str) -> str:
    """Pull SQL between ```sql ... ``` fences and flatten to one line."""
    m = re.search(r"```sql(.*?)```", output, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    sql_code = m.group(1).strip()
    return " ".join(sql_code.split())

def run_select(sql: str):
    """Return (rows, headers) for a SELECT."""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
        headers = result.keys()
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

# ----------- GEMINI SETUP -----------
def gemini_model():
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(GEMINI_MODEL)

# ----------- CORE FUNCTIONS -----------
def generate_sql(question: str) -> str:
    """
    1) Use EXTRACT_CONTEXT to get a 'name lookup' SQL, run it, feed rows back.
    2) Use BASE_CONTEXT + question + names to get final SQL.
    """
    model = gemini_model()

    # Step 1: get name-extract SQL
    resp1 = model.generate_content(EXTRACT_CONTEXT + question)
    sql_extract = extract_sql(resp1.text)
    if not sql_extract:
        return ""

    name_rows, name_headers = run_select(sql_extract)
    name_context = {"headers": list(name_headers), "rows": name_rows}

    # Step 2: final SQL
    prompt2 = BASE_CONTEXT + question + json.dumps(name_context)
    resp2 = model.generate_content(prompt2)
    final_sql = extract_sql(resp2.text)
    return final_sql

def generate_visualization(question: str, data: dict | list | pd.DataFrame) -> bool:
    """
    Build a matplotlib plot from data using Gemini-generated code.
    Saves to static/visualization.png.
    Returns True/False.
    """
    try:
        model = gemini_model()

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

        resp = model.generate_content(viz_prompt)
        code_block = re.search(r"```python(.*?)```", resp.text or "", re.DOTALL | re.IGNORECASE)
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
