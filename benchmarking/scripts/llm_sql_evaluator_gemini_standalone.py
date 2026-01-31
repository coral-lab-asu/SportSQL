#!/usr/bin/env python3
"""
Standalone LLM-based SQL Evaluation Script (Google Gemini)

This script:
1. Loads evaluation results from a CSV.
2. Re-evaluates all cases with original accuracy = 0 using LLM jury (Gemini).
3. Runs sequential API calls to avoid rate limiting.
4. Produces a new CSV with updated "llm_judge" column and JSON debug log.
"""

import pandas as pd
import json
import sys
from datetime import datetime
import argparse
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai


load_dotenv()

# ==============================
# Gemini API Wrapper
# ==============================
class LLMWrapperGemini:
    def __init__(self, model="gemini-2.0-flash"):
        self.model = model
        api_key = os.getenv("API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Set API_KEY or GEMINI_API_KEY environment variable")
        
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model)

    def generate_content(self, prompt, timeout=45):
        response = self.client.generate_content(
            prompt,
            request_options={"timeout": timeout}
        )
        return response.text


# ==============================
# Prompt Builder
# ==============================
def create_evaluation_prompt(question, gt_sql, generated_sql, gt_output, system_output):
    """Create a prompt for LLM to evaluate SQL semantic correctness."""
    return f"""You are an expert SQL evaluator. Your task is to determine if a generated SQL query correctly answers the given question, even if the output format differs from the ground truth.

QUESTION: {question}

GROUND TRUTH SQL: {gt_sql}
GROUND TRUTH OUTPUT: {gt_output}

GENERATED SQL: {generated_sql}
GENERATED OUTPUT: {system_output}

Please evaluate whether the GENERATED SQL correctly answers the original QUESTION. Consider these factors:

1. **Semantic Correctness**: Does the generated SQL logically answer the question?
2. **Result Equivalence**: Do both outputs contain the same core information?
3. **Accept Format Differences**: Extra columns, different column names, or different name formats are acceptable if the core answer is correct.
4. **Logic Equivalence**: Different WHERE conditions that yield the same result are acceptable.

IMPORTANT: Focus on whether the generated SQL answers the question correctly, not whether it matches the ground truth exactly.

Respond with ONLY:
- "CORRECT" if the generated SQL correctly answers the question
- "INCORRECT" if the generated SQL does not correctly answer the question

Response:"""


# ==============================
# Utility: Handle Null Outputs
# ==============================
def check_null_outputs(gt_output, system_output):
    """Check if both outputs are null/empty and should get 100% accuracy."""
    def is_null_or_empty(output):
        if pd.isna(output) or output is None or output == "":
            return True
        if isinstance(output, str):
            output_stripped = output.strip()
            if output_stripped in ["{}", "[]", '{"headers": [], "rows": []}', '{"headers":[],"rows":[]}']:
                return True
            try:
                parsed = json.loads(output_stripped)
                if isinstance(parsed, dict):
                    rows = parsed.get("rows", [])
                    return rows is None or len(rows) == 0
                elif isinstance(parsed, list):
                    return len(parsed) == 0
                return not parsed
            except json.JSONDecodeError:
                # If it's not valid JSON but not empty, consider it non-empty
                return False
        return False

    return is_null_or_empty(gt_output) and is_null_or_empty(system_output)


# ==============================
# Evaluation Logic
# ==============================
def evaluate_single_case(idx, row, llm_wrapper):
    """Evaluate a single case."""
    try:
        if check_null_outputs(row["gt_output_fresh"], row["system_output"]):
            return {"index": idx, "llm_judge": 100, "reason": "Both outputs null/empty"}

        prompt = create_evaluation_prompt(
            question=row["english_question"],
            gt_sql=row["gt_sql"],
            generated_sql=row["generated_sql"],
            gt_output=row["gt_output_fresh"],
            system_output=row["system_output"],
        )

        response = llm_wrapper.generate_content(prompt)
        llm_decision = response.strip().upper()

        if "INCORRECT" in llm_decision:
            llm_judge = 0
        elif "CORRECT" in llm_decision:
            llm_judge = 100
        else:
            llm_judge = 0  # Default fallback

        return {"index": idx, "llm_judge": llm_judge, "reason": f"LLM evaluation: {llm_decision[:50]}"}

    except Exception as e:
        return {"index": idx, "llm_judge": 0, "reason": f"Error: {str(e)[:100]}"}


def evaluate_with_llm_sequential(df_zero_cases):
    """Evaluate zero accuracy cases using LLM sequentially."""
    print(f"🤖 Starting LLM evaluation of {len(df_zero_cases)} zero-accuracy cases...")
    llm_wrapper = LLMWrapperGemini()

    results = {}
    completed = 0
    
    for idx, row in df_zero_cases.iterrows():
        result = evaluate_single_case(idx, row, llm_wrapper)
        results[idx] = result
        completed += 1
        print(result)
        if completed % 10 == 0:
            print(f"📊 Completed {completed}/{len(df_zero_cases)} evaluations...")
        
        # Small delay to avoid rate limiting
        time.sleep(5)

    print(f"✅ Completed all {completed} evaluations")
    return results


# ==============================
# Main
# ==============================
def main():
    parser = argparse.ArgumentParser(description="LLM-based SQL Evaluation (Google Gemini)")
    parser.add_argument("--csv", default='pipeline_evaluation_20250913_182639.csv', help="Input CSV file with evaluation results")
    parser.add_argument("--model", default="gemini-2.0-flash", help="Gemini model to use")
    args = parser.parse_args()

    print("🔍 LLM-Based SQL Semantic Evaluation (Google Gemini)")
    print("=" * 50)
    print(f"📄 Input file: {args.csv}")
    print(f"🤖 Model: {args.model}")
    print()

    try:
        df = pd.read_csv(args.csv)
        print(f"✅ Loaded {len(df)} evaluation cases")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        sys.exit(1)

    zero_cases = df[df["accuracy"] == 0.0].copy()
    print(f"🎯 Found {len(zero_cases)} zero accuracy cases to re-evaluate")

    if zero_cases.empty:
        print("No zero accuracy cases found. Exiting.")
        return

    llm_results = evaluate_with_llm_sequential(zero_cases)

    df_output = df.copy()
    df_output["llm_judge"] = df_output["accuracy"]
    for idx, result in llm_results.items():
        df_output.loc[idx, "llm_judge"] = result["llm_judge"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = f"pipeline_eval_gemini_{timestamp}.csv"
    details_json = f"gemini_eval_details_{timestamp}.json"

    df_output.to_csv(output_csv, index=False)
    with open(details_json, "w") as f:
        json.dump({str(k): v for k, v in llm_results.items()}, f, indent=2)

    print(f"💾 Results saved to: {output_csv}")
    print(f"🔍 Detailed LLM results saved to: {details_json}")
    print("🎉 Evaluation complete!")


if __name__ == "__main__":
    main()
