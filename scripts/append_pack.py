#!/usr/bin/env python3
"""
Append Pack Script

Validates a JSON file and appends its themes to an existing pack in the database.
If pack doesn't exist and --name is provided, creates a new pack.

Usage:
    python scripts/append_pack.py <pack_short_name> <json_file_path>
    python scripts/append_pack.py <pack_short_name> <json_file_path> --name "Pack Name"

Example:
    python scripts/append_pack.py "vuelta" "./packs_json/vuelta_day3.json"
    python scripts/append_pack.py "new_pack" "./packs_json/new.json" --name "New Pack"
"""

import argparse
import asyncio
import json
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from database.packs import get_pack_by_short_name, create_pack

REQUIRED_QUESTION_FIELDS = ['form', 'cost', 'question', 'answer']
QUESTIONS_PER_THEME = 5

NUMBER_PREFIX_PATTERN = re.compile(r'^\d+\.\s*')


def strip_number_prefix(name: str) -> str:
    """Remove leading number with dot from theme name (e.g. '1. Theme' -> 'Theme')."""
    return NUMBER_PREFIX_PATTERN.sub('', name)


def process_themes(themes: list[dict]) -> list[dict]:
    """Process themes: strip number prefixes from names."""
    for theme in themes:
        if 'name' in theme:
            theme['name'] = strip_number_prefix(theme['name'])
    return themes


def validate_json(data: dict) -> list[str]:
    """
    Validate the JSON structure.
    Returns a list of error messages (empty if valid).
    """
    errors = []
    
    if 'themes' not in data:
        errors.append("Missing 'themes' field in JSON")
        return errors
    
    themes = data['themes']
    
    if not isinstance(themes, list):
        errors.append("'themes' must be a list")
        return errors
    
    if len(themes) == 0:
        errors.append("'themes' list is empty")
        return errors
    
    for theme_idx, theme in enumerate(themes, 1):
        theme_prefix = f"Theme {theme_idx}"
        
        if 'name' not in theme:
            errors.append(f"{theme_prefix}: missing 'name' field")
        
        if 'questions' not in theme:
            errors.append(f"{theme_prefix}: missing 'questions' field")
            continue
        
        questions = theme['questions']
        
        if not isinstance(questions, list):
            errors.append(f"{theme_prefix}: 'questions' must be a list")
            continue
        
        if len(questions) != QUESTIONS_PER_THEME:
            errors.append(
                f"{theme_prefix}: expected {QUESTIONS_PER_THEME} questions, "
                f"got {len(questions)}"
            )
        
        for q_idx, question in enumerate(questions, 1):
            q_prefix = f"{theme_prefix}, Question {q_idx}"
            
            for field in REQUIRED_QUESTION_FIELDS:
                if field not in question:
                    errors.append(f"{q_prefix}: missing '{field}' field")
                elif not question[field] and field != 'form':
                    errors.append(f"{q_prefix}: '{field}' is empty")
    
    return errors


async def update_pack(short_name: str, pack_file: dict, number_of_themes: int) -> bool:
    """Update pack in database."""
    pool = Database.get_pool()
    sql = Database.load_sql("packs/update_pack.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, short_name, json.dumps(pack_file), number_of_themes)
        return row is not None


async def main():
    parser = argparse.ArgumentParser(
        description='Append themes from JSON file to existing pack in database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python scripts/append_pack.py "vuelta" "./packs_json/vuelta_day3.json"
    python scripts/append_pack.py --dry-run "vuelta" "./packs_json/vuelta_day3.json"
    python scripts/append_pack.py "new_pack" "./new.json" --name "New Pack"
        """
    )
    parser.add_argument('pack_short_name', help='Short name of the pack')
    parser.add_argument('json_path', help='Path to the JSON file with themes')
    parser.add_argument('--name', '-n', help='Full name of the pack (required if creating new)')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Validate and show result without updating DB')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_path):
        print(f"❌ Error: File not found: {args.json_path}")
        sys.exit(1)
    
    # Load JSON file
    try:
        with open(args.json_path, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file: {e}")
        sys.exit(1)
    
    # Validate JSON
    print(f"📋 Validating {args.json_path}...")
    errors = validate_json(new_data)
    
    if errors:
        print(f"\n❌ Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"   • {error}")
        sys.exit(1)
    
    new_themes = process_themes(new_data['themes'])
    print(f"✅ Validation passed: {len(new_themes)} theme(s) found")
    
    for i, theme in enumerate(new_themes, 1):
        print(f"   {i}. {theme['name']} ({len(theme['questions'])} questions)")
    
    # Connect to database
    print(f"\n🔗 Connecting to database...")
    await Database.connect()
    
    try:
        # Get existing pack
        print(f"📦 Loading pack '{args.pack_short_name}'...")
        existing_pack = await get_pack_by_short_name(args.pack_short_name)
        
        if not existing_pack:
            # Pack doesn't exist - check if we can create it
            if not args.name:
                print(f"❌ Error: Pack '{args.pack_short_name}' not found in database")
                print(f"   To create a new pack, provide --name argument")
                sys.exit(1)
            
            # Create new pack
            print(f"📝 Pack not found, creating new pack...")
            
            pack_file = {
                'info': new_data.get('info', ''),
                'themes': new_themes
            }
            total_themes = len(new_themes)
            
            print(f"\n📊 New pack: {total_themes} theme(s)")
            
            if args.dry_run:
                print("\n🔍 Dry run - no changes made to database")
                print("\n--- New pack structure ---")
                for i, theme in enumerate(new_themes, 1):
                    print(f"   📘 {i}. {theme['name']}")
                return
            
            print(f"\n💾 Creating pack in database...")
            pack_id = await create_pack(
                short_name=args.pack_short_name,
                name=args.name,
                pack_file=pack_file,
                number_of_themes=total_themes
            )
            
            print(f"\n✅ Pack created successfully!")
            print(f"   ID: {pack_id}")
            print(f"   Name: {args.name}")
            print(f"   Short name: {args.pack_short_name}")
            print(f"   Themes: {total_themes}")
        else:
            # Pack exists - append themes
            existing_pack_file = existing_pack['pack_file']
            existing_themes = existing_pack_file.get('themes', [])
            existing_count = len(existing_themes)
            
            print(f"✅ Found pack with {existing_count} existing theme(s)")
            
            # Concatenate themes
            merged_themes = existing_themes + new_themes
            total_themes = len(merged_themes)
            
            # Create updated pack file
            updated_pack_file = existing_pack_file.copy()
            updated_pack_file['themes'] = merged_themes
            
            print(f"\n📊 Result: {existing_count} + {len(new_themes)} = {total_themes} theme(s)")
            
            if args.dry_run:
                print("\n🔍 Dry run - no changes made to database")
                print("\n--- Merged pack structure ---")
                for i, theme in enumerate(merged_themes, 1):
                    marker = "📗" if i <= existing_count else "📘"
                    print(f"   {marker} {i}. {theme['name']}")
                return
            
            # Update in database
            print(f"\n💾 Updating pack in database...")
            success = await update_pack(args.pack_short_name, updated_pack_file, total_themes)
            
            if success:
                print(f"\n✅ Pack updated successfully!")
                print(f"   Short name: {args.pack_short_name}")
                print(f"   Total themes: {total_themes}")
            else:
                print(f"\n❌ Error: Failed to update pack")
                sys.exit(1)
            
    finally:
        await Database.disconnect()


if __name__ == '__main__':
    asyncio.run(main())

