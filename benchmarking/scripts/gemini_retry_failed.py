#!/usr/bin/env python3
"""
Minimalistic script to retry failed Gemini evaluations (rate limit errors)

This script:
1. Loads previous Gemini evaluation details JSON
2. Identifies cases that failed with rate limit errors
3. Retries only those failed cases with longer delays
4. Updates the results files
"""

import pandas as pd
import json
import sys
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

class LLMWrapperGemini:
    def __init__(self, model="gemini-2.0-flash"):
        self.model = model
        api_key = os.getenv("API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Set API_KEY or GEMINI_API_KEY environment variable")
        
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model)

    def generate_content(self, prompt, timeout=60):
        response = self.client.generate_content(
            prompt,
            request_options={"timeout": timeout}
        )
        return response.text

def create_evaluation_prompt(question, gt_sql, generated_sql, gt_output, system_output):
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

def evaluate_single_case(idx, row, llm_wrapper):
    try:
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
            llm_judge = 0

        return {"index": idx, "llm_judge": llm_judge, "reason": f"LLM evaluation: {llm_decision[:50]}"}

    except Exception as e:
        return {"index": idx, "llm_judge": 0, "reason": f"Error: {str(e)[:100]}"}

def main():
    if len(sys.argv) != 3:
        print("Usage: python gemini_retry_failed.py <details_json_file> <csv_file>")
        print("Example: python gemini_retry_failed.py gemini_eval_details_20250915_123456.json pipeline_eval_gemini_20250915_123456.csv")
        sys.exit(1)

    details_file = sys.argv[1]
    csv_file = sys.argv[2]

    print("🔄 Retrying Failed Gemini Evaluations")
    print("=" * 50)
    print(f"📄 Details file: {details_file}")
    print(f"📄 CSV file: {csv_file}")
    print()

    # Load previous results
    try:
        with open(details_file, 'r') as f:
            previous_results = json.load(f)
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(previous_results)} previous results")
    except Exception as e:
        print(f"❌ Error loading files: {str(e)}")
        sys.exit(1)

    # Find failed cases (rate limit errors)
    failed_cases = []
    for idx_str, result in previous_results.items():
        if result["llm_judge"] == 0 and ("429" in result.get("reason", "") or "rate" in result.get("reason", "").lower()):
            failed_cases.append(int(idx_str))

    print(f"🎯 Found {len(failed_cases)} failed cases to retry")
    
    if not failed_cases:
        print("No failed cases found. Exiting.")
        return

    # Initialize LLM
    llm_wrapper = LLMWrapperGemini()
    
    # Retry failed cases
    updated_results = {}
    for i, idx in enumerate(failed_cases):
        print(f"🔄 Retrying case {i+1}/{len(failed_cases)} (index {idx})")
        
        # Get the row data
        row = df.iloc[idx]
        
        # Retry evaluation
        result = evaluate_single_case(idx, row, llm_wrapper)
        updated_results[str(idx)] = result
        
        print(f"   Result: {result['llm_judge']} - {result['reason'][:30]}...")
        
        # Long delay to avoid rate limits
        if i < len(failed_cases) - 1:  # Don't sleep after last case
            print("   ⏳ Waiting 10 seconds...")
            time.sleep(10)

    # Update the results
    for idx_str, new_result in updated_results.items():
        previous_results[idx_str] = new_result
        df.loc[int(idx_str), "llm_judge"] = new_result["llm_judge"]

    # Save updated files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_csv = csv_file.replace(".csv", f"_retry_{timestamp}.csv")
    new_details = details_file.replace(".json", f"_retry_{timestamp}.json")

    df.to_csv(new_csv, index=False)
    with open(new_details, "w") as f:
        json.dump(previous_results, f, indent=2)

    print(f"\n✅ Retry complete!")
    print(f"💾 Updated CSV: {new_csv}")
    print(f"🔍 Updated details: {new_details}")
    
    # Summary
    successful_retries = sum(1 for r in updated_results.values() if r["llm_judge"] > 0)
    print(f"📊 Successfully evaluated: {successful_retries}/{len(failed_cases)} cases")

if __name__ == "__main__":
    main()
