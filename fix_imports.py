#!/usr/bin/env python3
"""
Script to fix imports after reorganization
"""
import os
import re

# Define the import mappings
IMPORT_MAPPINGS = {
    # Old import -> New import
    'from db_config import': 'from src.database.config import',
    'import db_config': 'import src.database.config as db_config',
    'from mariadb_access import': 'from src.database.operations import',
    'import mariadb_access': 'import src.database.operations as mariadb_access',
    'from schemas import': 'from src.database.schemas import',
    'import schemas': 'import src.database.schemas as schemas',
    'from llm_wrapper import': 'from src.llm.wrapper import',
    'import llm_wrapper': 'import src.llm.wrapper as llm_wrapper',
    'from gemini_api import': 'from src.nl2sql.generator import',
    'import gemini_api': 'import src.nl2sql.generator as gemini_api',
    'from insights_config import': 'from src.deep_research.config import',
    'from insights_schema import': 'from src.deep_research.schema import',
    'from insights_planner import': 'from src.deep_research.planner import',
    'from insights_sql_compiler import': 'from src.deep_research.compiler import',
    'from player_refresh import': 'from src.deep_research.player_refresh import',
}

# Prompt path updates
PROMPT_PATH_MAPPINGS = {
    'PROMPT_DIR = "prompts"': 'PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")',
    'PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")': 'PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "llm", "prompts")',
    '"prompts"': 'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "llm", "prompts")',
}

def fix_file_imports(filepath):
    """Fix imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply import mappings
        for old_import, new_import in IMPORT_MAPPINGS.items():
            content = content.replace(old_import, new_import)
        
        # Apply prompt path mappings (only for specific files)
        if 'src/' in filepath:
            for old_path, new_path in PROMPT_PATH_MAPPINGS.items():
                if old_path in content:
                    content = content.replace(old_path, new_path)
        
        # Write back if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"✗ Error fixing {filepath}: {e}")
        return False

def main():
    """Main function to fix all imports"""
    directories = ['src', 'scripts', 'website', 'benchmarking', 'update_player_mappings']
    fixed_count = 0
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        for root, dirs, files in os.walk(directory):
            # Skip __pycache__ and .git
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    if fix_file_imports(filepath):
                        fixed_count += 1
    
    print(f"\n✓ Fixed {fixed_count} files")

if __name__ == '__main__':
    main()
