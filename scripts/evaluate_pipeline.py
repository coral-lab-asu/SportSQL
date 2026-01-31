#!/usr/bin/env python3
"""
SportSQL Pipeline Evaluation Script

This script evaluates the SportSQL NL2SQL pipeline on error cases from the evaluation dataset.
It runs the complete pipeline (player detection, data updates, SQL generation, execution) 
and compares results against ground truth SQL queries.

Note: This script is configured to use LOCAL PostgreSQL database for evaluation.
"""

import pandas as pd
import json
import time
import traceback
import csv
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue

# Force local database usage BEFORE importing SportSQL components
# Remove any FORCE_REMOTE_DB environment variable
if 'FORCE_REMOTE_DB' in os.environ:
    del os.environ['FORCE_REMOTE_DB']

# Add --server local to command line arguments for db_config detection
if '--server' not in sys.argv:
    sys.argv.extend(['--server', 'local'])

# Import SportSQL components (they will now use local database)
from src.nl2sql.generator import generate_sql
from src.database.operations import return_query, get_player_id_from_question, update_player_data
from src.database.config import get_db_config


class PipelineEvaluator:
    """Evaluates the SportSQL pipeline on error cases."""
    
    def __init__(self, excel_file: str = "All Results.xlsx", log_file: str = None, max_workers: int = 4):
        """
        Initialize the evaluator.
        
        Args:
            excel_file: Path to the Excel file with evaluation data
            log_file: Path to CSV log file (auto-generated if None)
            max_workers: Maximum number of worker threads for parallel processing
        """
        self.excel_file = excel_file
        self.log_file = log_file or f"pipeline_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.max_workers = max_workers
        
        # Thread-safe logging
        self._log_lock = threading.Lock()
        self._progress_lock = threading.Lock()
        
        # Force local database configuration for evaluation
        self.db_config = get_db_config('local')
        print(f"🔧 Using database: {self.db_config.get_database_info()['type']}")
        print(f"🔧 Host: {self.db_config.get_database_info()['host']}")
        print(f"🔧 Database: {self.db_config.get_database_info()['database']}")
        print(f"🧵 Max worker threads: {self.max_workers}")
        
        # Initialize CSV log file
        self._init_log_file()
        
    def _init_log_file(self):
        """Initialize the CSV log file with headers."""
        headers = [
            'timestamp',
            'template_num', 
            'question_num',
            'english_question',
            'category',
            'difficulty',
            'gt_sql',
            'generated_sql',
            'gt_output_fresh',  # Fresh GT output by running GT_SQL
            'system_output',    # Our pipeline output
            'accuracy',
            'execution_time_sec',
            'player_id_detected',
            'player_update_success',
            'sql_generation_success',
            'sql_execution_success',
            'gt_sql_execution_success',
            'error_message'
        ]
        
        with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        
        print(f"📝 Initialized log file: {self.log_file}")
    
    def load_error_cases(self) -> pd.DataFrame:
        """Load error cases from the Excel file."""
        try:
            df = pd.read_excel(self.excel_file, sheet_name='gemini single')
            
            # Filter for error cases (Accuracy != 100 or LLM_Output is NaN)
            errors = df.copy()
            
            print(f"📊 Loaded {len(df)} total questions, {len(errors)} error cases")
            return errors
            
        except Exception as e:
            print(f"❌ Error loading Excel file: {e}")
            raise
    
    def run_pipeline_on_question(self, question: str) -> Dict[str, Any]:
        """
        Run the complete SportSQL pipeline on a single question.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict with pipeline results and metadata
        """
        start_time = time.time()
        result = {
            'execution_time_sec': 0,
            'player_id_detected': 0,
            'player_update_success': False,
            'sql_generation_success': False,
            'sql_execution_success': False,
            'generated_sql': None,
            'system_output': None,
            'error_message': None
        }
        
        try:
            # Step 1: Player Detection
            print(f"🔍 Detecting player in question...")
            player_id = get_player_id_from_question(question)
            result['player_id_detected'] = player_id
            
            # Step 2: Update player data if needed
            if player_id > 0:
                print(f"👤 Player ID {player_id} detected, updating data...")
                update_success = update_player_data(player_id)
                result['player_update_success'] = update_success
                if not update_success:
                    print("⚠️  Player data update failed, continuing anyway...")
            
            # Step 3: Generate SQL
            print(f"🤖 Generating SQL...")
            sql_query = generate_sql(question)
            result['generated_sql'] = sql_query
            
            if not sql_query or sql_query.strip() == "":
                result['error_message'] = "SQL generation returned empty result"
                return result
            
            result['sql_generation_success'] = True
            print(f"✅ Generated SQL: {sql_query[:100]}...")
            
            # Step 4: Execute SQL
            print(f"💾 Executing SQL query...")
            db_result = return_query(sql_query)
            
            if not db_result:
                result['error_message'] = "SQL execution returned empty result"
                return result
            
            # Parse result
            try:
                parsed_result = json.loads(db_result)
                if 'error' in parsed_result:
                    result['error_message'] = f"SQL execution error: {parsed_result['error']}"
                    return result
                
                result['system_output'] = parsed_result
                result['sql_execution_success'] = True
                print(f"✅ SQL executed successfully")
                
            except json.JSONDecodeError as e:
                result['error_message'] = f"Failed to parse SQL result: {e}"
                return result
                
        except Exception as e:
            result['error_message'] = f"Pipeline error: {str(e)}"
            print(f"❌ Pipeline error: {e}")
            print(traceback.format_exc())
        
        finally:
            result['execution_time_sec'] = time.time() - start_time
        
        return result
    
    def execute_gt_sql(self, gt_sql: str) -> Tuple[bool, Any, Optional[str]]:
        """
        Execute ground truth SQL to get fresh results.
        
        Args:
            gt_sql: Ground truth SQL query
            
        Returns:
            Tuple of (success, result, error_message)
        """
        try:
            print(f"🎯 Executing GT SQL: {gt_sql[:50]}...")
            db_result = return_query(gt_sql)
            
            if not db_result:
                return False, None, "GT SQL execution returned empty result"
            
            try:
                parsed_result = json.loads(db_result)
                if 'error' in parsed_result:
                    return False, None, f"GT SQL execution error: {parsed_result['error']}"
                
                return True, parsed_result, None
                
            except json.JSONDecodeError as e:
                return False, None, f"Failed to parse GT SQL result: {e}"
                
        except Exception as e:
            return False, None, f"GT SQL execution error: {str(e)}"
    
    def calculate_accuracy(self, system_output: Any, gt_output: Any) -> float:
        """
        Calculate accuracy between system output and ground truth output.
        
        Args:
            system_output: System pipeline output
            gt_output: Ground truth output
            
        Returns:
            Accuracy score (0-100)
        """
        try:
            if system_output is None or gt_output is None:
                return 0.0
            
            # Extract rows from both outputs
            sys_rows = system_output.get('rows', []) if isinstance(system_output, dict) else []
            gt_rows = gt_output.get('rows', []) if isinstance(gt_output, dict) else []
            
            # Simple comparison - exact match
            if sys_rows == gt_rows:
                return 100.0
            
            # If different lengths, calculate partial match
            if len(sys_rows) == 0 and len(gt_rows) == 0:
                return 100.0
            elif len(sys_rows) == 0 or len(gt_rows) == 0:
                return 0.0
            
            # Calculate intersection-based accuracy
            sys_set = set(tuple(row) if isinstance(row, list) else (row,) for row in sys_rows)
            gt_set = set(tuple(row) if isinstance(row, list) else (row,) for row in gt_rows)
            
            if len(gt_set) == 0:
                return 0.0
            
            intersection = len(sys_set.intersection(gt_set))
            accuracy = (intersection / len(gt_set)) * 100
            
            return min(100.0, accuracy)
            
        except Exception as e:
            print(f"⚠️  Error calculating accuracy: {e}")
            return 0.0
    
    def log_result(self, row_data: Dict[str, Any], pipeline_result: Dict[str, Any], 
                   gt_success: bool, gt_output: Any, gt_error: str, accuracy: float):
        """Thread-safe log evaluation result to CSV file."""
        log_row = [
            datetime.now().isoformat(),
            row_data.get('Template_Num', ''),
            row_data.get('Question_Num', ''),
            row_data.get('English', ''),
            row_data.get('Category', ''),
            row_data.get('Difficulty', ''),
            row_data.get('GT_SQL', ''),
            pipeline_result.get('generated_sql', ''),
            json.dumps(gt_output) if gt_output else '',
            json.dumps(pipeline_result.get('system_output')) if pipeline_result.get('system_output') else '',
            accuracy,
            pipeline_result.get('execution_time_sec', 0),
            pipeline_result.get('player_id_detected', 0),
            pipeline_result.get('player_update_success', False),
            pipeline_result.get('sql_generation_success', False),
            pipeline_result.get('sql_execution_success', False),
            gt_success,
            pipeline_result.get('error_message', '') or (gt_error if not gt_success else '')
        ]
        
        with self._log_lock:
            with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(log_row)
    
    def evaluate_single_case(self, case_data: Tuple[int, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate a single test case.
        
        Args:
            case_data: Tuple of (index, row_data)
            
        Returns:
            Dict with evaluation results
        """
        idx, row = case_data
        thread_id = threading.current_thread().name
        
        try:
            with self._progress_lock:
                print(f"🧵 [{thread_id}] Processing case {idx}: {row['English'][:50]}...")
            
            # Run pipeline
            pipeline_result = self.run_pipeline_on_question(row['English'])
            
            # Execute GT SQL for fresh ground truth
            gt_success, gt_output, gt_error = self.execute_gt_sql(row['GT_SQL'])
            
            # Calculate accuracy
            accuracy = self.calculate_accuracy(
                pipeline_result.get('system_output'), 
                gt_output
            )
            
            # Log result (thread-safe)
            self.log_result(row, pipeline_result, gt_success, gt_output, gt_error, accuracy)
            
            # Return statistics for aggregation
            return {
                'idx': idx,
                'completed': True,
                'pipeline_success': pipeline_result.get('sql_execution_success', False),
                'gt_sql_success': gt_success,
                'accuracy': accuracy,
                'original_accuracy': row.get('Accuracy', 0),
                'execution_time': pipeline_result.get('execution_time_sec', 0),
                'thread_id': thread_id
            }
            
        except Exception as e:
            error_msg = f"Error processing case {idx}: {str(e)}"
            print(f"❌ [{thread_id}] {error_msg}")
            
            # Log error case
            error_pipeline_result = {
                'generated_sql': '',
                'system_output': None,
                'execution_time_sec': 0,
                'player_id_detected': 0,
                'player_update_success': False,
                'sql_generation_success': False,
                'sql_execution_success': False,
                'error_message': error_msg
            }
            self.log_result(row, error_pipeline_result, False, None, error_msg, 0.0)
            
            return {
                'idx': idx,
                'completed': False,
                'pipeline_success': False,
                'gt_sql_success': False,
                'accuracy': 0.0,
                'original_accuracy': row.get('Accuracy', 0),
                'execution_time': 0,
                'thread_id': thread_id,
                'error': error_msg
            }
    
    def evaluate_all_errors(self):
        """Run evaluation on all error cases using multi-threading."""
        print("🚀 Starting SportSQL Pipeline Evaluation (Multi-threaded)")
        print("=" * 60)
        
        # Load error cases
        error_df = self.load_error_cases()
        total_errors = len(error_df)
        
        print(f"📋 Evaluating {total_errors} error cases...")
        print(f"📝 Logging to: {self.log_file}")
        print(f"🧵 Using {self.max_workers} worker threads")
        print("=" * 60)
        
        # Track statistics
        stats = {
            'total': total_errors,
            'completed': 0,
            'pipeline_success': 0,
            'gt_sql_success': 0,
            'improved_accuracy': 0,
            'perfect_accuracy': 0,
            'total_execution_time': 0,
            'thread_stats': {}
        }
        
        # Prepare data for threading
        case_data = [(idx, row) for idx, (_, row) in enumerate(error_df.iterrows(), 1)]
        
        # Use ThreadPoolExecutor for parallel processing
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_case = {executor.submit(self.evaluate_single_case, case): case for case in case_data}
            
            # Process completed tasks
            for future in as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    result = future.result()
                    
                    # Update statistics
                    stats['completed'] += 1
                    if result['pipeline_success']:
                        stats['pipeline_success'] += 1
                    if result['gt_sql_success']:
                        stats['gt_sql_success'] += 1
                    if result['accuracy'] > result['original_accuracy']:
                        stats['improved_accuracy'] += 1
                    if result['accuracy'] == 100:
                        stats['perfect_accuracy'] += 1
                    
                    stats['total_execution_time'] += result['execution_time']
                    
                    # Track per-thread statistics
                    thread_id = result['thread_id']
                    if thread_id not in stats['thread_stats']:
                        stats['thread_stats'][thread_id] = {'count': 0, 'success': 0, 'time': 0}
                    stats['thread_stats'][thread_id]['count'] += 1
                    if result['pipeline_success']:
                        stats['thread_stats'][thread_id]['success'] += 1
                    stats['thread_stats'][thread_id]['time'] += result['execution_time']
                    
                    # Progress update every 25 completions
                    if stats['completed'] % 25 == 0:
                        elapsed_time = time.time() - start_time
                        progress_pct = (stats['completed'] / stats['total']) * 100
                        success_rate = (stats['pipeline_success'] / stats['completed']) * 100
                        improvement_rate = (stats['improved_accuracy'] / stats['completed']) * 100
                        
                        print(f"\n📈 Progress: {stats['completed']}/{stats['total']} ({progress_pct:.1f}%)")
                        print(f"✅ Pipeline success rate: {success_rate:.1f}%")
                        print(f"📈 Improvement rate: {improvement_rate:.1f}%")
                        print(f"⏱️  Elapsed time: {elapsed_time:.1f}s")
                        print(f"🚀 Average speed: {stats['completed']/elapsed_time:.1f} cases/sec")
                
                except Exception as e:
                    print(f"❌ Error processing case {case[0]}: {e}")
                    stats['completed'] += 1
        
        total_time = time.time() - start_time
        
        # Final statistics
        print("\n" + "=" * 60)
        print("🏁 MULTI-THREADED EVALUATION COMPLETE")
        print("=" * 60)
        print(f"📋 Total error cases evaluated: {stats['total']}")
        print(f"✅ Pipeline successful: {stats['pipeline_success']} ({stats['pipeline_success']/stats['total']*100:.1f}%)")
        print(f"🎯 GT SQL successful: {stats['gt_sql_success']} ({stats['gt_sql_success']/stats['total']*100:.1f}%)")
        print(f"📈 Improved accuracy: {stats['improved_accuracy']} ({stats['improved_accuracy']/stats['total']*100:.1f}%)")
        print(f"🎯 Perfect accuracy: {stats['perfect_accuracy']} ({stats['perfect_accuracy']/stats['total']*100:.1f}%)")
        print(f"⏱️  Total wall time: {total_time:.1f}s")
        print(f"⏱️  Total pipeline time: {stats['total_execution_time']:.1f}s")
        print(f"🚀 Average speed: {stats['total']/total_time:.1f} cases/sec")
        print(f"⚡ Speedup factor: {stats['total_execution_time']/total_time:.1f}x")
        
        # Thread statistics
        print(f"\n🧵 Thread Performance:")
        for thread_id, thread_stats in stats['thread_stats'].items():
            success_rate = (thread_stats['success'] / thread_stats['count']) * 100 if thread_stats['count'] > 0 else 0
            avg_time = thread_stats['time'] / thread_stats['count'] if thread_stats['count'] > 0 else 0
            print(f"  {thread_id}: {thread_stats['count']} cases, {success_rate:.1f}% success, {avg_time:.1f}s avg")
        
        print(f"\n📝 Results logged to: {self.log_file}")


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SportSQL Pipeline Evaluator')
    parser.add_argument('--threads', '-t', type=int, default=1,
                       help='Number of worker threads (default: 4)')
    parser.add_argument('--input', default='All Results.xlsx',
                       help='Input Excel file')
    parser.add_argument('--llm', choices=['gemini', 'openai'], default='gemini',
                       help='LLM provider to use')
    parser.add_argument('--server', choices=['local', 'remote'], default='local',
                       help='Database server type')
    
    args = parser.parse_args()
    
    print("🏈 SportSQL Pipeline Evaluator (Multi-threaded)")
    print("Evaluating error cases from the evaluation dataset...")
    print(f"🧵 Using {args.threads} worker threads")
    print(f"🤖 Using {args.llm.upper()} LLM provider")
    
    evaluator = PipelineEvaluator(excel_file=args.input, max_workers=args.threads)
    evaluator.evaluate_all_errors()


if __name__ == "__main__":
    main()
