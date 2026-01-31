"""
Test script for the SportSQL pipeline evaluation.
Runs evaluation on just a few error cases to test the system.
"""

import os
import sys

# Force local database usage BEFORE importing anything
if 'FORCE_REMOTE_DB' in os.environ:
    del os.environ['FORCE_REMOTE_DB']

if '--server' not in sys.argv:
    sys.argv.extend(['--server', 'local'])

import pandas as pd
from evaluate_pipeline import PipelineEvaluator

def test_evaluation():
    """Test the evaluation on a small subset of error cases."""
    print("🧪 Testing SportSQL Pipeline Evaluation")
    print("=" * 50)
    
    try:
        # Load error cases
        df = pd.read_excel('All Results_updated.xlsx', sheet_name='gemini single')
        errors = df[(df['Accuracy'] != 100) | (df['LLM_Output'].isna())].copy()
        
        print(f"📊 Found {len(errors)} total error cases")
        
        # Take just first 3 error cases for testing
        test_cases = errors.head(3)
        print(f"🧪 Testing with first 3 error cases...")
        
        # Create a temporary DataFrame for testing
        test_df = test_cases.copy()
        
        # Initialize evaluator with fewer threads for testing
        evaluator = PipelineEvaluator(log_file="test_evaluation.csv", max_workers=2)
        
        print(f"🧵 Testing with {evaluator.max_workers} worker threads")
        
        # Prepare test cases for multi-threading
        case_data = [(idx, row) for idx, (_, row) in enumerate(test_df.iterrows(), 1)]
        
        # Use the multi-threaded evaluation method
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=evaluator.max_workers) as executor:
            # Submit all test cases
            future_to_case = {executor.submit(evaluator.evaluate_single_case, case): case for case in case_data}
            
            # Process results as they complete
            for future in as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    result = future.result()
                    idx = result['idx']
                    
                    print(f"\n🧪 Test Case {idx}/3 [Thread: {result['thread_id']}]:")
                    print(f"✅ Completed: {result['completed']}")
                    print(f"🤖 Pipeline Success: {result['pipeline_success']}")
                    print(f"🎯 GT SQL Success: {result['gt_sql_success']}")
                    print(f"📊 New Accuracy: {result['accuracy']:.1f}% (Original: {result['original_accuracy']}%)")
                    print(f"⏱️  Execution Time: {result['execution_time']:.2f}s")
                    
                    if 'error' in result:
                        print(f"❌ Error: {result['error']}")
                        
                except Exception as e:
                    print(f"❌ Error processing test case: {e}")
        
        print(f"\n✅ Multi-threaded test completed! Check test_evaluation.csv for detailed logs.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    test_evaluation()
