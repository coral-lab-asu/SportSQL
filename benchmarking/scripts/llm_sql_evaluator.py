#!/usr/bin/env python3
"""
LLM-based SQL Evaluation Script
Re-evaluates zero accuracy cases using semantic understanding instead of exact output matching.
"""

import pandas as pd
import json
from llm_wrapper import LLMWrapper
import sys
from datetime import datetime
import concurrent.futures
import threading
from typing import List, Dict, Any
import argparse

def create_evaluation_prompt(question, gt_sql, generated_sql, gt_output, system_output):
    """Create a prompt for LLM to evaluate SQL semantic correctness."""
    
    prompt = f"""You are an expert SQL evaluator. Your task is to determine if a generated SQL query correctly answers the given question, even if the output format differs from the ground truth.

QUESTION: {question}

GROUND TRUTH SQL: {gt_sql}
GROUND TRUTH OUTPUT: {gt_output}

GENERATED SQL: {generated_sql}
GENERATED OUTPUT: {system_output}

Please evaluate whether the GENERATED SQL correctly answers the original QUESTION. Consider these factors:

1. **Semantic Correctness**: Does the generated SQL logically answer the question?
2. **Result Equivalence**: Do both outputs contain the same core information?
3. **Accept Format Differences**: Extra columns, different column names, or different name formats (web_name vs second_name) are acceptable if the core answer is correct.
4. **Logic Equivalence**: Different WHERE conditions that yield the same result are acceptable.

IMPORTANT: Focus on whether the generated SQL answers the question correctly, not whether it matches the ground truth exactly.

Respond with ONLY:
- "CORRECT" if the generated SQL correctly answers the question
- "INCORRECT" if the generated SQL does not correctly answer the question

Response:"""
    
    return prompt

def check_null_outputs(gt_output, system_output):
    """Check if both outputs are null/empty and should get 100% accuracy."""
    def is_null_or_empty(output):
        if pd.isna(output) or output is None or output == '':
            return True
        if isinstance(output, str):
            # Check for empty JSON structures
            if output.strip() in ['{}', '[]', '{"headers": [], "rows": []}', '{"headers":[], "rows":[]}']:
                return True
            # Try parsing JSON to check if it's effectively empty
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    return not parsed.get('rows') or len(parsed.get('rows', [])) == 0
                return not parsed
            except:
                pass
        return False
    
    return is_null_or_empty(gt_output) and is_null_or_empty(system_output)

def evaluate_single_case(args):
    """Evaluate a single case - designed for multithreading."""
    idx, row, llm_wrapper = args
    
    try:
        # First check if both outputs are null - automatic 100%
        if check_null_outputs(row['gt_output_fresh'], row['system_output']):
            return {
                'index': idx,
                'llm_judge': 100,
                'reason': 'Both outputs null/empty'
            }
        
        # Create evaluation prompt
        prompt = create_evaluation_prompt(
            question=row['english_question'],
            gt_sql=row['gt_sql'],
            generated_sql=row['generated_sql'],
            gt_output=row['gt_output_fresh'],
            system_output=row['system_output']
        )
        
        # Get LLM evaluation
        response = llm_wrapper.generate_content(prompt, timeout=45)
        llm_decision = response.strip().upper()
        
        # Normalize response to 0 or 100
        if "INCORRECT" in llm_decision:
            llm_judge = 0
        elif "CORRECT" in llm_decision:
            llm_judge = 100
        else:
            llm_judge = 0  # Default to incorrect if unclear
            
        return {
            'index': idx,
            'llm_judge': llm_judge,
            'reason': f"LLM evaluation: {llm_decision[:50]}"
        }
        
    except Exception as e:
        return {
            'index': idx,
            'llm_judge': 0,
            'reason': f"Error: {str(e)[:100]}"
        }

def evaluate_with_llm_multithreaded(df_zero_cases, max_workers=4, llm_provider='gemini'):
    """Evaluate zero accuracy cases using LLM with multithreading."""
    
    print(f"🤖 Starting multithreaded LLM evaluation of {len(df_zero_cases)} cases...")
    print(f"🧵 Using {max_workers} threads")
    print("=" * 60)
    
    # Create LLM wrappers for each thread (to avoid sharing issues)
    def create_args():
        for idx, row in df_zero_cases.iterrows():
            # Each thread gets its own LLM wrapper to avoid conflicts
            llm_wrapper = LLMWrapper(provider=llm_provider)
            yield (idx, row, llm_wrapper)
    
    results = {}
    completed = 0
    
    # Use ThreadPoolExecutor for multithreading
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_idx = {
            executor.submit(evaluate_single_case, args): args[0] 
            for args in create_args()
        }
        
        # Process completed tasks
        for future in concurrent.futures.as_completed(future_to_idx):
            try:
                result = future.result()
                results[result['index']] = result
                completed += 1
                
                # Progress update
                if completed % 10 == 0:
                    print(f"📊 Completed {completed}/{len(df_zero_cases)} evaluations...")
                    
            except Exception as e:
                idx = future_to_idx[future]
                results[idx] = {
                    'index': idx,
                    'llm_judge': 0,
                    'reason': f"Thread error: {str(e)}"
                }
                completed += 1
    
    print(f"✅ Completed all {completed} evaluations")
    return results

def main():
    """Main function to run LLM-based SQL evaluation."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LLM-based SQL Evaluation')
    parser.add_argument('--csv', default='pipeline_evaluation_20250913_182639.csv',
                       help='Input CSV file with evaluation results')
    parser.add_argument('--threads', type=int, default=6,
                       help='Number of threads for parallel processing')
    parser.add_argument('--llm', choices=['gemini', 'openai', 'gpt'], default='gemini',
                       help='LLM provider to use')
    
    args = parser.parse_args()
    
    print("🔍 LLM-Based SQL Semantic Evaluation")
    print("=" * 50)
    print(f"📄 Input file: {args.csv}")
    print(f"🧵 Threads: {args.threads}")
    print(f"🤖 LLM: {args.llm}")
    print()
    
    # Load evaluation results
    print(f"📊 Loading evaluation results from {args.csv}...")
    
    try:
        df = pd.read_csv(args.csv)
        print(f"✅ Loaded {len(df)} evaluation cases")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        sys.exit(1)
    
    # Filter ALL zero accuracy cases (not just successful ones)
    zero_cases = df[df['accuracy'] == 0.0].copy()
    
    print(f"🎯 Found {len(zero_cases)} zero accuracy cases to re-evaluate")
    
    if len(zero_cases) == 0:
        print("No zero accuracy cases found. Exiting.")
        return
    
    # Run multithreaded LLM evaluation
    llm_results = evaluate_with_llm_multithreaded(zero_cases, max_workers=args.threads, llm_provider=args.llm)
    
    # Create the output dataframe with llm_judge column
    print("\n📊 Creating output CSV with LLM judgments...")
    
    # Start with original dataframe - this includes ALL cases
    df_output = df.copy()
    
    # Add llm_judge column - default to original accuracy for all cases
    df_output['llm_judge'] = df_output['accuracy']
    
    # Update llm_judge for cases that were re-evaluated (only zero accuracy cases)
    for idx, result in llm_results.items():
        df_output.loc[idx, 'llm_judge'] = result['llm_judge']
    
    # Note: Cases with original accuracy = 100 keep llm_judge = 100
    # Cases with original accuracy = 0 get updated with LLM judgment (0 or 100)
    
    # Analyze results
    print("\n📊 Dataset Composition:")
    print("=" * 40)
    
    total_cases = len(df_output)
    original_perfect = len(df[df['accuracy'] == 100.0])
    original_zero = len(df[df['accuracy'] == 0.0])
    
    print(f"📊 Total cases in output CSV: {total_cases}")
    print(f"✅ Originally perfect (kept as 100%): {original_perfect}")
    print(f"🔄 Originally zero (re-evaluated): {original_zero}")
    
    print("\n📊 LLM Re-evaluation Results:")
    print("=" * 40)
    
    # Count LLM judgments for zero accuracy cases
    llm_correct = sum(1 for r in llm_results.values() if r['llm_judge'] == 100)
    llm_incorrect = sum(1 for r in llm_results.values() if r['llm_judge'] == 0)
    null_both = sum(1 for r in llm_results.values() if 'Both outputs null' in r.get('reason', ''))
    
    print(f"📈 Zero accuracy cases re-evaluated: {len(llm_results)}")
    print(f"✅ LLM judged CORRECT: {llm_correct} ({llm_correct/len(llm_results)*100:.1f}%)")
    print(f"❌ LLM judged INCORRECT: {llm_incorrect} ({llm_incorrect/len(llm_results)*100:.1f}%)")
    print(f"🔄 Both outputs null (auto 100%): {null_both}")
    
    # Calculate accuracy improvement
    original_accuracy = (df['accuracy'] == 100.0).sum() / len(df) * 100
    new_accuracy = (df_output['llm_judge'] == 100.0).sum() / len(df_output) * 100
    improvement = new_accuracy - original_accuracy
    
    print(f"\n🎯 Accuracy Impact:")
    print(f"Original accuracy: {original_accuracy:.1f}%")
    print(f"New LLM-judged accuracy: {new_accuracy:.1f}%")
    print(f"Improvement: +{improvement:.1f} percentage points")
    
    # Show some examples of corrections
    print(f"\n📝 Sample LLM Corrections:")
    print("-" * 50)
    corrected_cases = [(idx, row, llm_results[idx]) for idx, row in zero_cases.iterrows() 
                      if idx in llm_results and llm_results[idx]['llm_judge'] == 100][:3]
    
    for idx, row, result in corrected_cases:
        print(f"Q: {row['english_question']}")
        print(f"GT SQL: {row['gt_sql']}")
        print(f"Generated: {row['generated_sql']}")
        print(f"LLM: CORRECT (was 0% → 100%)")
        print(f"Reason: {result['reason']}")
        print()
    
    # Save output CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = f"pipeline_evaluation_llm_judged_{timestamp}.csv"
    
    df_output.to_csv(output_csv, index=False)
    print(f"💾 Results saved to: {output_csv}")
    
    # Save detailed LLM results for debugging
    llm_details_file = f"llm_evaluation_details_{timestamp}.json"
    with open(llm_details_file, 'w') as f:
        # Convert to serializable format
        serializable_results = {str(k): v for k, v in llm_results.items()}
        json.dump(serializable_results, f, indent=2)
    
    print(f"🔍 Detailed LLM results saved to: {llm_details_file}")
    
    print(f"\n🎉 Evaluation complete! Check {output_csv} for the full results.")

if __name__ == "__main__":
    main()
