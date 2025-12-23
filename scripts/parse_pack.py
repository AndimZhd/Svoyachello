#!/usr/bin/env python3
"""
PDF Pack Parser Script

Parses a PDF file containing question pack and inserts it into the database.
Themes are identified by bold numbered text (1. Theme Name)
Questions are identified by non-bold numbered text (1. Question text)

Usage:
    python scripts/parse_pack.py <pack_name> <pack_short_name> <pdf_file_path>

Example:
    python scripts/parse_pack.py "Мой пак вопросов" "my_pack" "./packs/questions.pdf"
"""

import argparse
import asyncio
import json
import re
import sys
import os

from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit(1)

from database import Database
from database.packs import create_pack


def is_bold_font(font_name: str) -> bool:
    """Check if font name indicates bold text."""
    font_lower = font_name.lower()
    return 'bold' in font_lower or 'heavy' in font_lower or 'black' in font_lower


def extract_structured_text(pdf_path: str) -> list[dict]:  # type: ignore[type-arg]
    """
    Extract text with formatting info from PDF.
    Returns list of text segments with is_bold flag.
    """
    doc = fitz.open(pdf_path)
    segments: list[dict] = []  # type: ignore[type-arg]
    
    for page in doc:
        blocks = page.get_text("dict")["blocks"]  # type: ignore
        
        for block in blocks:
            if block["type"] != 0:  # Skip non-text blocks  # type: ignore
                continue
            
            for line in block["lines"]:  # type: ignore
                line_text = ""
                line_is_bold = False
                
                for span in line["spans"]:  # type: ignore
                    text = span["text"]  # type: ignore
                    font = span["font"]  # type: ignore
                    
                    if text.strip():
                        line_text += text
                        # Check if any part of the line is bold
                        if is_bold_font(font):
                            line_is_bold = True
                
                if line_text.strip():
                    segments.append({
                        'text': line_text.strip(),
                        'is_bold': line_is_bold
                    })
    
    doc.close()
    return segments


def parse_pack_from_segments(segments: list[dict]) -> dict:
    """
    Parse pack content from structured segments.
    
    - Themes: bold text starting with "N. " (number with dot), MUST be followed by "Автор:" line
    - Questions: non-bold text starting with "N. " within a theme
    - Answers: text after "Ответ" or "Ответ:"
    """
    result = {
        'info': '',
        'theme_names': [],
        'themes': []
    }
    
    # Pattern for numbered items: "1. ", "2. ", etc.
    numbered_pattern = re.compile(r'^(\d+)\.\s*(.*)$')
    
    info_parts = []
    current_theme = None
    pending_theme_name = None  # Potential theme waiting for author confirmation
    theme_counter = 0  # Counter for theme positions in file
    current_question_num = None
    current_question_text = []
    current_answer_text = []
    current_zachet_text = []
    current_comment_text = []
    in_answer = False
    in_zachet = False
    in_comment = False
    
    def save_current_question():
        """Save the current question to the current theme."""
        nonlocal current_question_num, current_question_text, current_answer_text, current_zachet_text, current_comment_text, in_answer, in_zachet, in_comment
        
        if current_theme is not None and current_question_num is not None:
            question_text = ' '.join(current_question_text).strip()
            # Remove "Форма:" and everything after it
            question_text = re.split(r'\s*Форма[:\s]', question_text, flags=re.IGNORECASE)[0].strip()
            answer_text = ' '.join(current_answer_text).strip().strip('.')
            zachet_text = ' '.join(current_zachet_text).strip().strip('.')
            comment_text = ' '.join(current_comment_text).strip()
            
            if question_text:
                # Calculate cost based on question number (1=10, 2=20, etc.)
                cost = current_question_num * 10
                
                # Combine answer and zachet with "/"
                if answer_text and zachet_text:
                    full_answer = f"{answer_text}/{zachet_text}"
                elif answer_text:
                    full_answer = f"{answer_text}"
                else:
                    full_answer = ""
                
                question_obj = {
                    'cost': cost,
                    'question': question_text,
                    'answer': full_answer
                }
                if comment_text:
                    question_obj['comment'] = f"{comment_text}"
                
                current_theme['questions'].append(question_obj)
        
        current_question_num = None
        current_question_text = []
        current_answer_text = []
        current_zachet_text = []
        current_comment_text = []
        in_answer = False
        in_zachet = False
        in_comment = False
    
    def save_current_theme():
        """Save the current theme to results."""
        nonlocal current_theme, pending_theme_name
        save_current_question()
        
        if current_theme is not None:
            result['themes'].append(current_theme)
        current_theme = None
        pending_theme_name = None
    
    for segment in segments:
        text = segment['text']
        is_bold = segment['is_bold']
        
        # Check if we're waiting for author line to confirm pending theme
        if pending_theme_name is not None:
            author_match = re.match(r'^Автор[:\s]*(.*)$', text, re.IGNORECASE)
            if author_match:
                # Author found - confirm this as a real theme
                confirmed_theme_name = pending_theme_name
                save_current_theme()  # Save previous theme first
                theme_counter += 1  # Increment counter only when theme is confirmed
                author = author_match.group(1).strip()
                theme_name = f"{theme_counter}. {confirmed_theme_name} Автор: {author}" if author else f"{theme_counter}. {confirmed_theme_name}"
                result['theme_names'].append(theme_name)
                current_theme = {
                    'name': theme_name,
                    'questions': []
                }
                pending_theme_name = None
                continue
            else:
                # No author - this was NOT a valid theme, discard pending
                pending_theme_name = None
                # Fall through to process this segment normally
        
        # Check if this is a numbered item
        match = numbered_pattern.match(text)
        
        if match:
            num = int(match.group(1))
            content = match.group(2).strip()
            
            if is_bold:
                # This might be a theme header - need to wait for author confirmation
                pending_theme_name = content
            else:
                # This is a question
                if current_theme is not None:
                    save_current_question()
                    current_question_num = num
                    current_question_text = [content] if content else []
                    in_answer = False
                    in_zachet = False
                    in_comment = False
        else:
            # Regular text - could be continuation of question/answer or info
            if current_theme is None:
                # Before any theme - this is info
                info_parts.append(text)
            else:
                # Check if this starts a comment (after answer)
                comment_match = re.match(r'^Комментарий[:\s]*(.*)$', text, re.IGNORECASE)
                # Check if this starts a zachet (alternative answer)
                zachet_match = re.match(r'^Зачёт[:\s]*(.*)$', text, re.IGNORECASE)
                # Check if this starts an answer
                answer_match = re.match(r'^Ответ[:\s]*(.*)$', text, re.IGNORECASE)
                
                if comment_match:
                    in_comment = True
                    in_answer = False
                    in_zachet = False
                    comment_content = comment_match.group(1).strip()
                    if comment_content:
                        current_comment_text.append(comment_content)
                elif zachet_match:
                    in_zachet = True
                    in_answer = False
                    in_comment = False
                    zachet_content = zachet_match.group(1).strip()
                    if zachet_content:
                        current_zachet_text.append(zachet_content)
                elif answer_match:
                    in_answer = True
                    in_zachet = False
                    in_comment = False
                    answer_content = answer_match.group(1).strip()
                    if answer_content:
                        current_answer_text.append(answer_content)
                elif in_comment:
                    # Continuation of comment
                    current_comment_text.append(text)
                elif in_zachet:
                    # Continuation of zachet
                    current_zachet_text.append(text)
                elif in_answer:
                    # Continuation of answer
                    current_answer_text.append(text)
                elif current_question_num is not None:
                    # Continuation of question
                    current_question_text.append(text)
    
    # Save last theme and question
    save_current_theme()
    
    result['info'] = ' '.join(info_parts).strip()
    
    return result


async def main():
    parser = argparse.ArgumentParser(
        description='Parse PDF pack and insert into database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python scripts/parse_pack.py "Мой пак" "my_pack" "./packs/questions.pdf"
    python scripts/parse_pack.py --dry-run "Test Pack" "test" "./test.pdf"
        """
    )
    parser.add_argument('pack_name', help='Full name of the pack')
    parser.add_argument('pack_short_name', help='Short name (identifier) for the pack')
    parser.add_argument('pdf_path', help='Path to the PDF file')
    parser.add_argument('--dry-run', action='store_true', help='Parse and print JSON without inserting to DB')
    parser.add_argument('--output', '-o', help='Output JSON to file instead of inserting to DB')
    parser.add_argument('--debug', action='store_true', help='Print debug info about parsed segments')
    
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.pdf_path):
        sys.exit(1)
    
    # Extract structured text from PDF
    segments = extract_structured_text(args.pdf_path)
    
    if not segments:
        sys.exit(1)
    
    # Parse the content
    pack_file = parse_pack_from_segments(segments)
    number_of_themes = len(pack_file['themes'])
    
    # Output or save
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(pack_file, f, ensure_ascii=False, indent=2)
        return
    
    if args.dry_run:
        return
    
    # Insert into database
    await Database.connect()
    
    try:
        await create_pack(
            short_name=args.pack_short_name,
            name=args.pack_name,
            pack_file=pack_file,
            number_of_themes=number_of_themes
        )
    except Exception:
        sys.exit(1)
    finally:
        await Database.disconnect()


if __name__ == '__main__':
    asyncio.run(main())

