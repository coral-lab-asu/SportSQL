#!/usr/bin/env python3
"""
Test script for GT SQL updates.
Tests both deterministic and LLM approaches on a few examples.
"""

import os
import sys

# Force local database usage
if 'FORCE_REMOTE_DB' in os.environ:
    del os.environ['FORCE_REMOTE_DB']
if '--server' not in sys.argv:
    sys.argv.extend(['--server', 'local'])

from update_gt_sql import GTSQLUpdater
import pandas as pd

def test_gt_updates():
    """Test GT SQL updates on sample cases."""
    print("🧪 Testing GT SQL Update Approaches")
    print("=" * 60)
    
    # Load sample error cases
    df = pd.read_excel('All Results .xlsx', sheet_name='gemini single')
    errors = df[(df['Accuracy'] != 100) | (df['LLM_Output'].isna())].head(5)
    
    updater = GTSQLUpdater()
    
    print(f"📋 Testing on {len(errors)} sample cases:\n")
    
    for idx, (_, row) in enumerate(errors.iterrows(), 1):
        english = row['English']
        original_sql = row['GT_SQL']
        
        print(f"🧪 Test Case {idx}:")
        print(f"❓ Question: {english}")
        print(f"🎯 Original GT SQL: {original_sql}")
        
        # Test deterministic approach
        det_sql, det_success, det_explanation = updater.deterministic_update(original_sql, english)
        print(f"🔧 Deterministic: {'✅' if det_success else '❌'} {det_explanation}")
        if det_success:
            print(f"   Updated SQL: {det_sql}")
        
        # Test LLM approach
        llm_sql, llm_success, llm_explanation = updater.llm_update(original_sql, english)
        print(f"🤖 LLM: {'✅' if llm_success else '❌'} {llm_explanation}")
        if llm_success:
            print(f"   Updated SQL: {llm_sql}")
        
        print("-" * 60)
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_gt_updates()
