#!/usr/bin/env python3
"""
Ground Truth SQL Update Script

Updates GT_SQL in the evaluation Excel file to use current player/team IDs.
Supports both deterministic rule-based and LLM-based approaches.
"""

import os
import sys
import pandas as pd
import json
import re
from typing import Dict, List, Tuple, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Force local database usage
if 'FORCE_REMOTE_DB' in os.environ:
    del os.environ['FORCE_REMOTE_DB']
if '--server' not in sys.argv:
    sys.argv.extend(['--server', 'local'])

from mariadb_access import run_sql

load_dotenv()

class GTSQLUpdater:
    """Updates ground truth SQL with current player/team IDs."""
    
    def __init__(self, excel_file: str = "All Results .xlsx"):
        self.excel_file = excel_file
        self.player_map = self._load_player_map()
        self.team_map = self._load_team_map()
        self.name_to_id_map = self._create_name_to_id_map()
        
        # Initialize Gemini for LLM approach
        self.gemini_api_key = os.getenv("API_KEY")
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self.model = None
            print("⚠️  No Gemini API key found - LLM approach disabled")
    
    def _load_player_map(self) -> Dict:
        """Load current player ID mappings."""
        if os.path.exists('player_id_map.json'):
            with open('player_id_map.json', 'r') as f:
                return json.load(f)
        else:
            print("🔄 Generating player mappings...")
            headers, rows = run_sql("SELECT player_id, first_name, second_name, web_name, team_name FROM players")
            player_map = {}
            for row in rows:
                player_id, first_name, second_name, web_name, team_name = row
                player_map[str(player_id)] = {
                    'first_name': first_name,
                    'second_name': second_name,
                    'web_name': web_name,
                    'full_name': f"{first_name} {second_name}".strip(),
                    'team_name': team_name
                }
            return player_map
    
    def _load_team_map(self) -> Dict:
        """Load current team ID mappings."""
        if os.path.exists('team_id_map.json'):
            with open('team_id_map.json', 'r') as f:
                return json.load(f)
        else:
            print("🔄 Generating team mappings...")
            headers, rows = run_sql("SELECT team_id, team_name, short_name FROM teams")
            team_map = {}
            for row in rows:
                team_id, team_name, short_name = row
                team_map[str(team_id)] = {
                    'team_name': team_name,
                    'short_name': short_name
                }
            return team_map
    
    def _create_name_to_id_map(self) -> Dict:
        """Create reverse mapping from names to current IDs."""
        name_to_id = {
            'players': {},
            'teams': {}
        }
        
        # Player name mappings
        for player_id, info in self.player_map.items():
            # Multiple ways to reference a player
            names = [
                info['full_name'].lower(),
                info['second_name'].lower(),
                info['web_name'].lower(),
                f"{info['first_name']} {info['second_name']}".lower().strip()
            ]
            for name in names:
                if name and name != 'nan':
                    name_to_id['players'][name] = int(player_id)
        
        # Team name mappings  
        for team_id, info in self.team_map.items():
            names = [
                info['team_name'].lower(),
                info['short_name'].lower()
            ]
            for name in names:
                if name and name != 'nan':
                    name_to_id['teams'][name] = int(team_id)
        
        return name_to_id
    
    def deterministic_update(self, sql: str, english_question: str) -> Tuple[str, bool, str]:
        """
        Deterministic rule-based approach to update GT SQL.
        
        Returns: (updated_sql, success, explanation)
        """
        try:
            updated_sql = sql
            changes = []
            
            # Extract player names from English question
            player_names = self._extract_player_names_from_question(english_question)
            team_names = self._extract_team_names_from_question(english_question)
            
            # Pattern 1: Update player_id = X with current ID
            if 'player_id =' in sql.lower():
                for name in player_names:
                    if name in self.name_to_id_map['players']:
                        current_id = self.name_to_id_map['players'][name]
                        # Replace any player_id = X with current ID
                        pattern = r'player_id\s*=\s*\d+'
                        replacement = f'player_id = {current_id}'
                        if re.search(pattern, updated_sql, re.IGNORECASE):
                            updated_sql = re.sub(pattern, replacement, updated_sql, flags=re.IGNORECASE)
                            changes.append(f"Updated player_id to {current_id} for {name}")
                            break
            
            # Pattern 2: Update team_id = X with current ID  
            if 'team_id =' in sql.lower():
                for name in team_names:
                    if name in self.name_to_id_map['teams']:
                        current_id = self.name_to_id_map['teams'][name]
                        pattern = r'team_id\s*=\s*\d+'
                        replacement = f'team_id = {current_id}'
                        if re.search(pattern, updated_sql, re.IGNORECASE):
                            updated_sql = re.sub(pattern, replacement, updated_sql, flags=re.IGNORECASE)
                            changes.append(f"Updated team_id to {current_id} for {name}")
                            break
            
            success = len(changes) > 0
            explanation = "; ".join(changes) if changes else "No updates needed"
            
            return updated_sql, success, explanation
            
        except Exception as e:
            return sql, False, f"Error: {str(e)}"
    
    def llm_update(self, sql: str, english_question: str) -> Tuple[str, bool, str]:
        """
        LLM-based approach to update GT SQL.
        
        Returns: (updated_sql, success, explanation)
        """
        if not self.model:
            return sql, False, "LLM not available"
        
        try:
            # Create context with current mappings
            context = self._create_llm_context(english_question)
            
            prompt = f"""
You are updating an old SQL query to use current player/team IDs from a Premier League database.

TASK: Update the SQL query to use the correct current player_id or team_id values.

ORIGINAL QUESTION: {english_question}
ORIGINAL SQL: {sql}

CURRENT DATABASE MAPPINGS:
{context}

INSTRUCTIONS:
1. Identify which player/team is mentioned in the question
2. Find their current ID from the mappings above
3. Update the SQL query to use the current ID
4. Return ONLY the updated SQL query, no explanations

UPDATED SQL:"""

            response = self.model.generate_content(
                prompt,
                request_options={"timeout": 30}
            )
            
            updated_sql = response.text.strip()
            
            # Clean up the response (remove markdown, extra text)
            if '```sql' in updated_sql:
                updated_sql = re.search(r'```sql\n(.*?)\n```', updated_sql, re.DOTALL)
                if updated_sql:
                    updated_sql = updated_sql.group(1).strip()
            elif '```' in updated_sql:
                updated_sql = updated_sql.replace('```', '').strip()
            
            # Basic validation
            if updated_sql and updated_sql != sql:
                return updated_sql, True, "LLM updated SQL"
            else:
                return sql, False, "LLM made no changes"
                
        except Exception as e:
            return sql, False, f"LLM error: {str(e)}"
    
    def _extract_player_names_from_question(self, question: str) -> List[str]:
        """Extract potential player names from English question."""
        question_lower = question.lower()
        found_names = []
        
        # Check against known player names
        for name, player_id in self.name_to_id_map['players'].items():
            if name in question_lower:
                found_names.append(name)
        
        # Sort by length (longer names first for better matching)
        return sorted(set(found_names), key=len, reverse=True)
    
    def _extract_team_names_from_question(self, question: str) -> List[str]:
        """Extract potential team names from English question."""
        question_lower = question.lower()
        found_names = []
        
        # Check against known team names
        for name, team_id in self.name_to_id_map['teams'].items():
            if name in question_lower:
                found_names.append(name)
        
        return sorted(set(found_names), key=len, reverse=True)
    
    def _create_llm_context(self, question: str) -> str:
        """Create relevant context for LLM based on the question."""
        player_names = self._extract_player_names_from_question(question)
        team_names = self._extract_team_names_from_question(question)
        
        context_parts = []
        
        # Add relevant players
        if player_names:
            context_parts.append("RELEVANT PLAYERS:")
            for name in player_names[:5]:  # Limit to top 5 matches
                player_id = self.name_to_id_map['players'][name]
                player_info = self.player_map[str(player_id)]
                context_parts.append(f"  {player_info['full_name']}: player_id = {player_id} ({player_info['team_name']})")
        
        # Add relevant teams
        if team_names:
            context_parts.append("RELEVANT TEAMS:")
            for name in team_names[:5]:
                team_id = self.name_to_id_map['teams'][name]
                team_info = self.team_map[str(team_id)]
                context_parts.append(f"  {team_info['team_name']}: team_id = {team_id} ({team_info['short_name']})")
        
        return "\n".join(context_parts) if context_parts else "No relevant mappings found"
    
    def update_excel_file(self, approach: str = "both", output_file: str = None, all_cases: bool = True):
        """
        Update the Excel file with corrected GT SQL.
        
        Args:
            approach: "deterministic", "llm", or "both"
            output_file: Output file path (default: adds _updated suffix)
            all_cases: If True, update all cases; if False, only error cases
        """
        print(f"🔄 Loading Excel file: {self.excel_file}")
        df = pd.read_excel(self.excel_file, sheet_name='gemini single')
        
        if all_cases:
            # Update ALL cases in the dataset
            cases_to_update = df.copy()
            print(f"📊 Found {len(cases_to_update)} total cases to update")
        else:
            # Filter error cases only
            cases_to_update = df[(df['Accuracy'] != 100) | (df['LLM_Output'].isna())].copy()
            print(f"📊 Found {len(cases_to_update)} error cases to update")
        
        # Track results
        stats = {
            'total': len(cases_to_update),
            'deterministic_success': 0,
            'llm_success': 0,
            'both_success': 0,
            'no_change': 0
        }
        
        # Add new columns for updated SQL
        cases_to_update['GT_SQL_Updated_Deterministic'] = cases_to_update['GT_SQL']
        cases_to_update['GT_SQL_Updated_LLM'] = cases_to_update['GT_SQL']
        cases_to_update['GT_SQL_Final'] = cases_to_update['GT_SQL']
        cases_to_update['Update_Method'] = 'none'
        cases_to_update['Update_Explanation'] = ''
        
        print(f"🚀 Starting GT SQL updates using {approach} approach...")
        
        for idx, (_, row) in enumerate(cases_to_update.iterrows(), 1):
            if idx % 50 == 0:
                print(f"  Progress: {idx}/{len(cases_to_update)} ({idx/len(cases_to_update)*100:.1f}%)")
            
            original_sql = row['GT_SQL']
            english_question = row['English']
            
            deterministic_sql = original_sql
            llm_sql = original_sql
            final_sql = original_sql
            method_used = 'none'
            explanation = ''
            
            # Try deterministic approach
            if approach in ['deterministic', 'both']:
                deterministic_sql, det_success, det_explanation = self.deterministic_update(original_sql, english_question)
                cases_to_update.loc[cases_to_update.index[idx-1], 'GT_SQL_Updated_Deterministic'] = deterministic_sql
                if det_success:
                    stats['deterministic_success'] += 1
                    final_sql = deterministic_sql
                    method_used = 'deterministic'
                    explanation = det_explanation
            
            # Try LLM approach
            if approach in ['llm', 'both']:
                llm_sql, llm_success, llm_explanation = self.llm_update(original_sql, english_question)
                cases_to_update.loc[cases_to_update.index[idx-1], 'GT_SQL_Updated_LLM'] = llm_sql
                if llm_success:
                    stats['llm_success'] += 1
                    if approach == 'llm' or method_used == 'none':
                        final_sql = llm_sql
                        method_used = 'llm'
                        explanation = llm_explanation
            
            # Determine final SQL and method
            if approach == 'both':
                if deterministic_sql != original_sql and llm_sql != original_sql:
                    # Both methods made changes - prefer deterministic for consistency
                    final_sql = deterministic_sql
                    method_used = 'both_deterministic_preferred'
                    explanation = f"Both updated: {det_explanation}; LLM: {llm_explanation}"
                    stats['both_success'] += 1
                elif deterministic_sql != original_sql:
                    final_sql = deterministic_sql
                    method_used = 'deterministic_only'
                    explanation = det_explanation
                elif llm_sql != original_sql:
                    final_sql = llm_sql
                    method_used = 'llm_only'
                    explanation = llm_explanation
                else:
                    stats['no_change'] += 1
            elif final_sql == original_sql:
                stats['no_change'] += 1
            
            cases_to_update.loc[cases_to_update.index[idx-1], 'GT_SQL_Final'] = final_sql
            cases_to_update.loc[cases_to_update.index[idx-1], 'Update_Method'] = method_used
            cases_to_update.loc[cases_to_update.index[idx-1], 'Update_Explanation'] = explanation
        
        # Save results
        output_file = output_file or self.excel_file.replace('.xlsx', '_updated.xlsx')
        
        # Create a new Excel file with updated data
        with pd.ExcelWriter(output_file) as writer:
            # Write original sheets
            for sheet_name in pd.ExcelFile(self.excel_file).sheet_names:
                if sheet_name == 'gemini single':
                    # Update the original dataframe with our changes
                    df_updated = df.copy()
                    for idx, updated_row in cases_to_update.iterrows():
                        df_updated.loc[idx, 'GT_SQL'] = updated_row['GT_SQL_Final']
                    df_updated.to_excel(writer, sheet_name='gemini single', index=False)
                else:
                    original_sheet = pd.read_excel(self.excel_file, sheet_name=sheet_name)
                    original_sheet.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Add analysis sheet
            cases_to_update.to_excel(writer, sheet_name='GT_SQL_Update_Analysis', index=False)
        
        # Print results
        print(f"\n✅ GT SQL update completed!")
        print(f"📊 Results:")
        print(f"  Total cases processed: {stats['total']}")
        print(f"  Deterministic updates: {stats['deterministic_success']}")
        print(f"  LLM updates: {stats['llm_success']}")
        print(f"  Both methods succeeded: {stats['both_success']}")
        print(f"  No changes needed: {stats['no_change']}")
        print(f"  Success rate: {(stats['total'] - stats['no_change'])/stats['total']*100:.1f}%")
        print(f"📝 Updated file saved as: {output_file}")
        print(f"📋 Detailed analysis available in 'GT_SQL_Update_Analysis' sheet")


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update Ground Truth SQL with current player/team IDs')
    parser.add_argument('--approach', choices=['deterministic', 'llm', 'both'], default='both',
                       help='Update approach to use')
    parser.add_argument('--input', default='All Results .xlsx',
                       help='Input Excel file')
    parser.add_argument('--output', 
                       help='Output Excel file (default: adds _updated suffix)')
    parser.add_argument('--server', choices=['local', 'remote'], default='local',
                       help='Database server type (added for compatibility)')
    parser.add_argument('--all-cases', action='store_true', default=True,
                       help='Update all cases in dataset (default: True)')
    parser.add_argument('--errors-only', action='store_true', 
                       help='Update only error cases (overrides --all-cases)')
    
    args = parser.parse_args()
    
    # Determine whether to update all cases or just errors
    update_all = args.all_cases and not args.errors_only
    
    print("🔧 GT SQL Updater")
    print("=" * 50)
    print(f"🎯 Mode: {'All cases' if update_all else 'Error cases only'}")
    
    updater = GTSQLUpdater(args.input)
    updater.update_excel_file(approach=args.approach, output_file=args.output, all_cases=update_all)


if __name__ == "__main__":
    main()
