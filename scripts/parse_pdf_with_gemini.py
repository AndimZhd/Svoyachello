#!/usr/bin/env python3
"""
Script to parse quiz pack PDF files using Gemini API and convert to JSON format
Usage: python parse_pdf_with_gemini.py <pdf_file_path>
"""

import os
import sys
import json
import time
from google import genai
from google.genai import types
from pathlib import Path
from dotenv import load_dotenv

from pack_parser_common import (
    SYSTEM_PROMPT,
    build_structure_prompt,
    build_theme_prompt,
    build_user_message,
    convert_docx_to_pdf,
    extract_json_from_response,
    extract_text,
    format_duration,
    generate_short_name,
    merge_pdfs,
    save_json,
    validate_json_structure,
)

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set")
    print("Please set it in .env file or with: export GEMINI_API_KEY='your-api-key'")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)


def upload_file_to_gemini(file_path: str):
    """Upload file (PDF or DOCX) to Gemini"""
    file_path_obj = Path(file_path)

    if file_path_obj.suffix.lower() == '.pdf':
        mime_type = 'application/pdf'
        display_name = 'quiz_pack.pdf'
        file_type = 'PDF'
    elif file_path_obj.suffix.lower() == '.docx':
        mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        display_name = 'quiz_pack.docx'
        file_type = 'DOCX'
    else:
        raise ValueError(f"Unsupported file type: {file_path_obj.suffix}. Supported: PDF, DOCX")

    print(f"Uploading {file_type}: {file_path_obj.name}")

    with open(file_path, 'rb') as f:
        file = client.files.upload(
            file=f,
            config=types.UploadFileConfig(
                mime_type=mime_type,
                display_name=display_name
            )
        )

    print(f"File uploaded: {file.name}")

    while file.state == types.FileState.PROCESSING:
        print("Processing file...")
        time.sleep(2)
        file = client.files.get(name=file.name)

    if file.state == types.FileState.FAILED:
        raise ValueError("File processing failed")

    print("File ready for analysis")
    return file

def get_package_structure(uploaded_file=None, text_content: str = None, is_merged: bool = False) -> dict:
    """Get package metadata and theme names (first pass)"""
    print("Step 1/2: Getting package structure...")

    prompt = build_structure_prompt(is_merged=is_merged)
    if not text_content:
        prompt = prompt.replace("Извлеки из текста документа", "Извлеки из файла (PDF или DOCX)")

    if text_content:
        contents = [build_user_message(prompt, text_content)]
    else:
        contents = [
            types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
            prompt
        ]

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192
        )
    )

    if not response.text:
        print("\n⚠️  ERROR: Response text is None!")
        print(f"Response object: {response}")

        if hasattr(response, 'candidates') and response.candidates:
            print(f"Number of candidates: {len(response.candidates)}")
            for i, candidate in enumerate(response.candidates):
                print(f"  Candidate {i}:")
                if hasattr(candidate, 'finish_reason'):
                    print(f"    Finish reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'):
                    print(f"    Safety ratings: {candidate.safety_ratings}")
                if hasattr(candidate, 'content'):
                    print(f"    Has content: {candidate.content is not None}")

        if hasattr(response, 'prompt_feedback'):
            print(f"Prompt feedback: {response.prompt_feedback}")

        raise ValueError(
            "Response text is None. Possible causes:\n"
            "1. Content was blocked by safety filters\n"
            "2. Output exceeded max_output_tokens limit\n"
            "3. API error occurred\n"
            "Check the diagnostics above for details."
        )

    return extract_json_from_response(response.text)

def parse_theme_questions(uploaded_file=None, text_content: str = None, theme_name: str = None, theme_index: int = 0, is_merged: bool = False) -> list:
    """Parse questions for a specific theme (second pass)"""
    print(f"  Parsing theme {theme_index + 1}: {theme_name[:50]}...")

    prompt = build_theme_prompt(theme_name, theme_index, is_merged=is_merged)

    if text_content:
        contents = [build_user_message(prompt, text_content)]
    else:
        contents = [
            types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
            prompt
        ]

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192
        )
    )

    if not response.text:
        print(f"\n⚠️  ERROR: Response text is None for theme: {theme_name}")
        print(f"Response object: {response}")

        if hasattr(response, 'candidates') and response.candidates:
            print(f"Number of candidates: {len(response.candidates)}")
            for i, candidate in enumerate(response.candidates):
                print(f"  Candidate {i}:")
                if hasattr(candidate, 'finish_reason'):
                    print(f"    Finish reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'):
                    print(f"    Safety ratings: {candidate.safety_ratings}")
                if hasattr(candidate, 'content'):
                    print(f"    Has content: {candidate.content is not None}")

        if hasattr(response, 'prompt_feedback'):
            print(f"Prompt feedback: {response.prompt_feedback}")

        raise ValueError(
            f"Response text is None for theme '{theme_name}'. Possible causes:\n"
            "1. Content was blocked by safety filters\n"
            "2. Output exceeded max_output_tokens limit\n"
            "3. API error occurred\n"
            "Check the diagnostics above for details."
        )

    result = extract_json_from_response(response.text)

    # Handle both old format (list) and new format (dict with theme_comment and questions)
    if isinstance(result, list):
        return {"questions": result}
    elif isinstance(result, dict) and "questions" in result:
        return result
    else:
        raise ValueError(f"Expected dict with questions or list, got {type(result)}")

def parse_with_text_chunked(file_path: str, is_merged: bool = False) -> dict:
    """Parse file using plain text extraction and Gemini API (faster, no file upload)"""

    total_start = time.time()

    extract_start = time.time()
    print(f"Extracting text from: {Path(file_path).name}")
    text_content = extract_text(file_path)
    extract_duration = time.time() - extract_start
    print(f"  ⏱ Text extraction took: {format_duration(extract_duration)}")
    print(f"  Text length: {len(text_content)} chars")

    structure_start = time.time()
    structure = get_package_structure(text_content=text_content, is_merged=is_merged)
    structure_duration = time.time() - structure_start
    print(f"  ⏱ Structure extraction took: {format_duration(structure_duration)}")

    if "themes" not in structure or not structure["themes"]:
        raise ValueError("Failed to extract themes from text")

    print(f"Found {len(structure['themes'])} themes")
    print(f"Step 2/2: Parsing questions for each theme...")

    themes_start = time.time()
    theme_times = []
    failed_themes = []

    for i, theme in enumerate(structure["themes"]):
        theme_start = time.time()
        theme_name = theme.get("name", f"Theme {i+1}")
        try:
            result = parse_theme_questions(text_content=text_content, theme_name=theme_name, theme_index=i, is_merged=is_merged)
            theme["questions"] = result.get("questions", [])
            if result.get("theme_comment"):
                theme["theme_comment"] = result["theme_comment"]
            theme_duration = time.time() - theme_start
            theme_times.append(theme_duration)
            print(f"    ✓ {len(theme['questions'])} questions parsed ({format_duration(theme_duration)})")
        except Exception as e:
            theme["questions"] = []
            failed_themes.append((i + 1, theme_name, str(e)))
            print(f"    ⚠️ FAILED: {theme_name[:50]}... - {e}")
            continue

    themes_duration = time.time() - themes_start
    total_duration = time.time() - total_start

    print()
    print("=" * 50)
    print("⏱ TIMING SUMMARY (TEXT MODE):")
    print(f"  Text extraction:     {format_duration(extract_duration)}")
    print(f"  Structure extraction: {format_duration(structure_duration)}")
    print(f"  Themes parsing:      {format_duration(themes_duration)}")
    if theme_times:
        avg_theme = sum(theme_times) / len(theme_times)
        print(f"    Avg per theme:     {format_duration(avg_theme)}")
    print(f"  TOTAL:               {format_duration(total_duration)}")
    if failed_themes:
        print(f"  ⚠️ FAILED THEMES:    {len(failed_themes)}")
        for num, name, err in failed_themes:
            print(f"    - Theme {num}: {name[:40]}...")
    print("=" * 50)
    print()

    return structure


def parse_pdf_with_gemini_chunked(file_path: str, is_merged: bool = False) -> dict:
    """Parse PDF/DOCX file using Gemini API with chunked approach (recommended for large files)"""

    total_start = time.time()

    upload_start = time.time()
    uploaded_file = upload_file_to_gemini(file_path)
    upload_duration = time.time() - upload_start
    print(f"  ⏱ Upload took: {format_duration(upload_duration)}")

    structure_start = time.time()
    structure = get_package_structure(uploaded_file, is_merged=is_merged)
    structure_duration = time.time() - structure_start
    print(f"  ⏱ Structure extraction took: {format_duration(structure_duration)}")

    if "themes" not in structure or not structure["themes"]:
        raise ValueError("Failed to extract themes from PDF")

    print(f"Found {len(structure['themes'])} themes")
    print(f"Step 2/2: Parsing questions for each theme...")

    themes_start = time.time()
    theme_times = []
    failed_themes = []

    for i, theme in enumerate(structure["themes"]):
        theme_start = time.time()
        theme_name = theme.get("name", f"Theme {i+1}")
        try:
            result = parse_theme_questions(uploaded_file, theme_name=theme_name, theme_index=i, is_merged=is_merged)
            theme["questions"] = result.get("questions", [])
            if result.get("theme_comment"):
                theme["theme_comment"] = result["theme_comment"]
            theme_duration = time.time() - theme_start
            theme_times.append(theme_duration)
            print(f"    ✓ {len(theme['questions'])} questions parsed ({format_duration(theme_duration)})")
        except Exception as e:
            theme["questions"] = []
            failed_themes.append((i + 1, theme_name, str(e)))
            print(f"    ⚠️ FAILED: {theme_name[:50]}... - {e}")
            continue

    themes_duration = time.time() - themes_start
    total_duration = time.time() - total_start

    print()
    print("=" * 50)
    print("⏱ TIMING SUMMARY (FILE MODE):")
    print(f"  Upload:              {format_duration(upload_duration)}")
    print(f"  Structure extraction: {format_duration(structure_duration)}")
    print(f"  Themes parsing:      {format_duration(themes_duration)}")
    if theme_times:
        avg_theme = sum(theme_times) / len(theme_times)
        print(f"    Avg per theme:     {format_duration(avg_theme)}")
    print(f"  TOTAL:               {format_duration(total_duration)}")
    if failed_themes:
        print(f"  ⚠️ FAILED THEMES:    {len(failed_themes)}")
        for num, name, err in failed_themes:
            print(f"    - Theme {num}: {name[:40]}...")
    print("=" * 50)
    print()

    return structure

def parse_pdf_with_gemini(file_path: str, chunked: bool = True, text_mode: bool = False, is_merged: bool = False) -> dict:
    """Parse PDF/DOCX file using Gemini API

    Args:
        file_path: Path to PDF or DOCX file
        chunked: If True, use chunked parsing (recommended for large files).
                 If False, use single-shot parsing (faster but may hit token limits).
        text_mode: If True, extract text and send as plain text (faster, no file upload).
                   If False, upload file to Gemini (supports images/formatting).
        is_merged: If True, file contains multiple "боёв" merged together
    """

    if text_mode:
        return parse_with_text_chunked(file_path, is_merged=is_merged)

    if chunked:
        return parse_pdf_with_gemini_chunked(file_path, is_merged=is_merged)

    uploaded_file = upload_file_to_gemini(file_path)

    print("Parsing file with Gemini (single-shot mode)...")

    prompt = """Распарси файл (PDF или DOCX) с вопросами "Своя игра" в JSON.

ФОРМАТ ПОЛЯ "form":
"form" - это маркер ЧТО назвать (ИЗ ВОПРОСА, НЕ ИЗ ОТВЕТА!):
- "ОН был профессором" → form: "он"
- "В ЧЕСТЬ НЕГО назвали" → form: "в честь него"
- "ЭТОТ ФРАНЦУЗ" → form: "француз"
- "В ответе одно слово. ОНА" → form: "одним словом, она"

JSON формат:
{"info":"...", "package_name":"...", "themes":[{"name":"...","questions":[{"cost":10,"question":"...","form":"он/она/его/город","answer":"...","source":"источник"}]}]}

ВАЖНО:
- ВСЕГДА ищи и добавляй поле "source" (источник ответа) если оно указано
- Опускай "comment" и "accept" если их нет
- Если информация о пакете (info) НЕ найдена в документе, оставь пустой строкой: ""
- Если название пакета (package_name) НЕ найдено, попробуй определить из содержимого или оставь пустой строкой: ""
- НЕ выдумывай информацию, которой нет в документе
- В JSON ОБЯЗАТЕЛЬНО экранируй кавычки (\\") и переводы строк (\\n)
- Будь краток. Закрой все скобки!"""

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192
        )
    )

    return extract_json_from_response(response.text)

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse quiz pack PDF/DOCX files using Gemini API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single PDF file
  python parse_pdf_with_gemini.py pack.pdf

  # Folder with multiple files (auto-detected)
  python parse_pdf_with_gemini.py Лагерь_Блик_2024_ЭК/

  # Explicit folder mode
  python parse_pdf_with_gemini.py Лагерь_Блик_2024_ЭК/ --folder

  # Use plain text mode (faster)
  python parse_pdf_with_gemini.py pack.docx --text-mode
        """
    )
    parser.add_argument('input_path', help='PDF file, DOCX file, or folder path')
    parser.add_argument('--folder', action='store_true',
                       help='Treat input_path as folder and merge files')
    parser.add_argument('--single-shot', action='store_true',
                       help='Use single-shot parsing (faster, but may hit limits)')
    parser.add_argument('--text-mode', action='store_true',
                       help='Extract plain text and send to Gemini (faster, no file upload)')

    args = parser.parse_args()

    input_path = Path(args.input_path)
    chunked = not args.single_shot
    text_mode = args.text_mode
    is_merged = False
    merged_pdf_path = None
    file_path = None

    if args.folder or (input_path.exists() and input_path.is_dir()):
        print(f"Folder mode: processing {input_path}")
        print("-" * 60)

        pdf_files = sorted([f for f in input_path.glob('*.pdf')])
        docx_files = sorted([f for f in input_path.glob('*.docx') if not f.name.startswith('~$')])

        if not pdf_files and not docx_files:
            print(f"❌ Error: No PDF or DOCX files found in {input_path}")
            sys.exit(1)

        print(f"Found {len(pdf_files)} PDF file(s) and {len(docx_files)} DOCX file(s)")

        all_pdfs = []
        temp_converted_pdfs = []

        if pdf_files:
            all_pdfs.extend(pdf_files)
            print(f"  ✓ {len(pdf_files)} PDF file(s) ready")

        if docx_files:
            print(f"  Converting {len(docx_files)} DOCX file(s) to PDF...")
            for i, docx_file in enumerate(docx_files, 1):
                print(f"    [{i}/{len(docx_files)}] Converting {docx_file.name}...")
                try:
                    converted_pdf = convert_docx_to_pdf(str(docx_file))
                    converted_pdf_path = Path(converted_pdf)
                    all_pdfs.append(converted_pdf_path)
                    temp_converted_pdfs.append(converted_pdf_path)
                    print(f"      ✓ Created: {converted_pdf_path.name}")
                except Exception as e:
                    print(f"      ⚠️  Failed to convert {docx_file.name}: {e}")
                    print(f"      Skipping this file...")

        if not all_pdfs:
            print(f"❌ Error: No valid PDF files to process")
            sys.exit(1)

        all_pdfs = sorted(all_pdfs, key=lambda p: p.name)

        merged_pdf_name = f"{input_path.name}_merged.pdf"
        merged_pdf_path = input_path / merged_pdf_name

        print(f"\nMerging {len(all_pdfs)} PDF file(s) into one...")
        merge_pdfs(all_pdfs, str(merged_pdf_path))
        print(f"✓ Merged PDF created: {merged_pdf_path}")

        file_path = str(merged_pdf_path)
        is_merged = True
    elif input_path.exists() and input_path.is_file():
        file_path_str = str(input_path)

        if input_path.suffix.lower() == '.docx' and not text_mode:
            print("Converting DOCX to PDF...")
            file_path = convert_docx_to_pdf(file_path_str)
        else:
            file_path = file_path_str
    else:
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)

    if is_merged:
        output_path = input_path / f"{input_path.name}_parsed.json"
    else:
        output_path = Path(file_path).parent / f"{Path(file_path).stem}_parsed.json"
    
    print(f"Input: {input_path}")
    print(f"Output JSON: {output_path}")
    print(f"Parsing mode: {'Chunked (theme-by-theme)' if chunked else 'Single-shot'}")
    print(f"Processing mode: {'Plain text' if text_mode else 'File upload'}")
    print(f"File format: {Path(file_path).suffix.upper()}")
    if is_merged:
        print("Note: Processing merged file (multiple боёв)")
    print("-" * 60)

    try:
        result = parse_pdf_with_gemini(file_path, chunked=chunked, text_mode=text_mode, is_merged=is_merged)

        save_json(result, str(output_path))
        print()

        validation_passed = validate_json_structure(result)
        
        if not validation_passed:
            print("\n⚠️  WARNING: JSON validation failed!")
            print("The JSON structure is incomplete or missing 'form' fields.")
            print(f"⚠️  JSON saved anyway to: {output_path}")
            print("You can fix it manually or re-run the parser.")
            sys.exit(1)

        print("-" * 60)
        print("✓ Success! File parsed and saved to JSON")
        print(f"  Themes: {len(result['themes'])}")
        print(f"  Total questions: {sum(len(t['questions']) for t in result['themes'])}")
        if is_merged:
            print(f"  Merged DOCX saved: {file_path}")

        print()
        print("=" * 60)

        short_name = generate_short_name(input_path.name)

        package_name = result.get('package_name', '')

        command = f"python3 scripts/append_pack.py {short_name} {output_path}"
        if package_name:
            command += f' --name "{package_name}"'

        print("📋 Next step: Copy and run this command to add pack to database:")
        print()
        print(f"  {command}")
        print()
        print("=" * 60)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
