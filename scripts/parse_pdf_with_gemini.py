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

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set")
    print("Please set it in .env file or with: export GEMINI_API_KEY='your-api-key'")
    sys.exit(1)

# Create client
client = genai.Client(api_key=GEMINI_API_KEY)

# System prompt for parsing quiz PDFs
SYSTEM_PROMPT = """Ты эксперт по парсингу PDF файлов с вопросами для игры "Своя игра" в формат JSON.

═══════════════════════════════════════════════════════════════
КРИТИЧЕСКИ ВАЖНО! ЛОГИКА ПОЛЯ "FORM":
═══════════════════════════════════════════════════════════════

⚠️ ПОЛЕ "form" ≠ ОТВЕТ! ⚠️

"form" - это маркер/указание ЧТО именно нужно назвать, извлекается ИЗ САМОГО ВОПРОСА.

═══════════════════════════════════════════════════════════════
АЛГОРИТМ ИЗВЛЕЧЕНИЯ "FORM":
═══════════════════════════════════════════════════════════════

1️⃣ ИЩЕМ ЗАГЛАВНЫЕ СЛОВА/МЕСТОИМЕНИЯ В ВОПРОСЕ:
   - "В ЧЕСТЬ НЕГО назвали ящерицу" → form: "в честь него"
   - "ЭТОГО ГОЛЛАНДЦА упоминают" → form: "голландец" / "этого голландца"
   - "ОН шутил, что хотел" → form: "он"
   - "ЕГО хотели создать" → form: "его"
   - "ОНИ подвергались гонениям" → form: "они"
   - "С НЕЙ связано много легенд" → form: "она"
   - "ИМИ оказываются девушки" → form: "ими"
   - "ТАКИЕ ОНИ используются в игре" → form: "такие они"
   - "ЭТОЙ СТОЛИЦЕЙ является" → form: "столица" / "эта столица"
   - "ЭТОТ ГОРОД стал побратимом" → form: "этот город" / "город"
   - "В ЭТОМ ГОДУ погибла Ида" → form: "год"
   - "ЭТОГО ПРОДЮСЕРА работой было" → form: "продюсер"

2️⃣ ДОБАВЛЯЕМ ОГРАНИЧЕНИЯ ИЗ НАЧАЛА ВОПРОСА:
   - "В ответе одно слово. ОНА называется" → form: "одним словом, она"
   - "В ответе два слова. ОН известен" → form: "два слова, он"
   - "В ответе три слова. ЕГО называют" → form: "тремя словами, его"
   - "В ответе трёхсложное слово. ОНО" → form: "трёхсложное слово, оно"
   - "В ответе два слова на одну букву" → form: "два слова на одну букву, им"
   - "В ответе два слова на парные согласные" → form: "два слова на парные согласные"
   - "Зачет абсолютно точный ответ" → добавь это в form

3️⃣ ИСПОЛЬЗУЕМ ТИП ОБЪЕКТА ИЗ ВОПРОСА (если указан явно):
   - "ЭТОТ ФРАНЦУЗ не обладал" → form: "француз"
   - "ЭТА СТОЛИЦА находится" → form: "столица"
   - "ЭТОТ ГОРОД США стал" → form: "этот город"
   - "ЭТИМ АНГЛИЙСКИМ ВЫРАЖЕНИЕМ называют" → form: "английское выражение"
   - "ЭТОМУ ПРОИЗВЕДЕНИЮ посвящено" → form: "произведение"

4️⃣ ЕСЛИ В PDF ЕСТЬ СТРОКА "Зачет:":
   - Извлеки альтернативные варианты в отдельное поле "accept": ["вариант1", "вариант2"]
   - НО form всё равно должна быть местоимением/маркером из вопроса!

═══════════════════════════════════════════════════════════════
РЕАЛЬНЫЕ ПРИМЕРЫ ИЗ ПАКЕТОВ:
═══════════════════════════════════════════════════════════════

✅ ПРАВИЛЬНО:
Вопрос: "В декабре 2012 года В ЧЕСТЬ НЕГО назвали ископаемую ящерицу"
→ form: "в честь него"
→ answer: "Барак Обама"

✅ ПРАВИЛЬНО:
Вопрос: "Эстонец упоминается наравне с фамилией ЭТОГО ГОЛЛАНДЦА"
→ form: "голландец"
→ answer: "Ян Хендрик Оорт"

✅ ПРАВИЛЬНО:
Вопрос: "В ответе одно слово. «Третьей ЕЙ» называют загрязнение"
→ form: "одним словом, она"
→ answer: "рука"

✅ ПРАВИЛЬНО:
Вопрос: "ОН был профессором кафедры биохимии"
→ form: "он"
→ answer: "Александр Опарин"

✅ ПРАВИЛЬНО:
Вопрос: "ЭТА СТОЛИЦА находится в 25 км от экватора"
→ form: "столица"
→ answer: "Кито"

✅ ПРАВИЛЬНО:
Вопрос: "Девушки оказываются ИМИ"
→ form: "ими"
→ answer: "вампиры"

❌ НЕПРАВИЛЬНО:
→ form: "Барак Обама" ❌ (это ответ, не форма!)
→ form: "ответ" ❌ (бессмысленно)

═══════════════════════════════════════════════════════════════
ФОРМАТ ВЫХОДНОГО JSON:
═══════════════════════════════════════════════════════════════

{
  "info": "полная информация о пакете: название, авторы, редакторы, благодарности, мораторий",
  "package_name": "название пакета",
  "themes": [
    {
      "name": "Название темы (Автор: Имя Фамилия)",
      "questions": [
        {
          "cost": 10,
          "question": "текст вопроса с ЗАГЛАВНЫМИ местоимениями",
          "form": "местоимение/маркер из вопроса (ОН/ОНА/ЕГО/ИХ/город/столица и т.д.)",
          "answer": "сам ответ",
          "comment": "комментарий к ответу",
          "accept": ["альтернатива1", "альтернатива2"]  // опционально, если есть "Зачет:"
        }
      ]
    }
  ]
}

═══════════════════════════════════════════════════════════════
ОБЩИЕ ПРАВИЛА ПАРСИНГА:
═══════════════════════════════════════════════════════════════

1. Структура: Бои/Раунды → Темы → Вопросы (10, 20, 30, 40, 50 очков)
2. Info извлекается из начала файла (авторы, редакторы, благодарности, мораторий)
3. Сохраняй все ударения, специальные символы, форматирование
4. Поддерживай белорусский язык ("Адказ:", "Каментар:")
5. Если в вопросе несколько заглавных местоимений, выбирай основное (обычно последнее перед вопросительным знаком)

Верни ТОЛЬКО валидный JSON, без markdown блоков и дополнительного текста."""

def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def upload_pdf_to_gemini(pdf_path: str):
    """Upload PDF file to Gemini"""
    print(f"Uploading PDF: {pdf_path}")

    # Upload file using file object to avoid Cyrillic path encoding issues
    with open(pdf_path, 'rb') as f:
        file = client.files.upload(
            file=f,
            config=types.UploadFileConfig(
                mime_type='application/pdf',
                display_name='quiz_pack.pdf'
            )
        )

    print(f"File uploaded: {file.name}")

    # Wait for file to be processed
    while file.state == types.FileState.PROCESSING:
        print("Processing file...")
        time.sleep(2)
        file = client.files.get(name=file.name)

    if file.state == types.FileState.FAILED:
        raise ValueError("File processing failed")

    print("File ready for analysis")
    return file

def extract_json_from_response(response_text: str) -> dict:
    """Extract and parse JSON from Gemini response"""
    response_text = response_text.strip()

    # Remove markdown code blocks if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    elif response_text.startswith("```"):
        response_text = response_text[3:]

    if response_text.endswith("```"):
        response_text = response_text[:-3]

    response_text = response_text.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"Response text (first 500 chars): {response_text[:500]}")
        raise

def get_package_structure(uploaded_file) -> dict:
    """Get package metadata and theme names (first pass)"""
    print("Step 1/2: Getting package structure...")

    prompt = """Извлеки из PDF ТОЛЬКО метаданные и список тем (БЕЗ вопросов).

Верни JSON:
{
  "info": "полная информация о пакете: название, авторы, редакторы, благодарности, мораторий",
  "package_name": "название пакета",
  "themes": [
    {"name": "Название темы 1 (Автор: Имя)"},
    {"name": "Название темы 2 (Автор: Имя)"}
  ]
}

ВАЖНО: НЕ включай вопросы, только названия тем. Верни ТОЛЬКО JSON."""

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096
        )
    )

    return extract_json_from_response(response.text)

def parse_theme_questions(uploaded_file, theme_name: str, theme_index: int) -> list:
    """Parse questions for a specific theme (second pass)"""
    print(f"  Parsing theme {theme_index + 1}: {theme_name[:50]}...")

    prompt = f"""Извлеки ТОЛЬКО вопросы для темы "{theme_name}" (тема #{theme_index + 1} в пакете).

ФОРМАТ ПОЛЯ "form" (маркер из вопроса, НЕ ответ!):
- "ОН был профессором" → form: "он"
- "В ЧЕСТЬ НЕГО назвали" → form: "в честь него"
- "ЭТОТ ФРАНЦУЗ" → form: "француз"
- "В ответе одно слово. ОНА" → form: "одним словом, она"

Верни JSON массив вопросов:
[
  {{"cost": 10, "question": "...", "form": "он/она/его/город", "answer": "..."}},
  {{"cost": 20, "question": "...", "form": "...", "answer": "..."}},
  ...
]

ВАЖНО:
- Вопросы должны быть отсортированы по cost (10, 20, 30, 40, 50)
- Включай "comment" и "accept" только если они есть в PDF
- Верни ТОЛЬКО JSON массив, без комментариев"""

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

def parse_pdf_with_gemini_chunked(pdf_path: str) -> dict:
    """Parse PDF file using Gemini API with chunked approach (recommended for large files)"""
    
    total_start = time.time()

    # Upload PDF once
    upload_start = time.time()
    uploaded_file = upload_pdf_to_gemini(pdf_path)
    upload_duration = time.time() - upload_start
    print(f"  ⏱ Upload took: {format_duration(upload_duration)}")

    # Step 1: Get package structure
    structure_start = time.time()
    structure = get_package_structure(uploaded_file)
    structure_duration = time.time() - structure_start
    print(f"  ⏱ Structure extraction took: {format_duration(structure_duration)}")

    if "themes" not in structure or not structure["themes"]:
        raise ValueError("Failed to extract themes from PDF")

    print(f"Found {len(structure['themes'])} themes")

    # Step 2: Parse each theme's questions
    print(f"Step 2/2: Parsing questions for each theme...")
    
    themes_start = time.time()
    theme_times = []

    for i, theme in enumerate(structure["themes"]):
        theme_start = time.time()
        theme_name = theme.get("name", f"Theme {i+1}")
        questions = parse_theme_questions(uploaded_file, theme_name, i)
        theme["questions"] = questions
        theme_duration = time.time() - theme_start
        theme_times.append(theme_duration)
        print(f"    ✓ {len(questions)} questions parsed ({format_duration(theme_duration)})")

    themes_duration = time.time() - themes_start
    total_duration = time.time() - total_start
    
    # Print timing summary
    print()
    print("=" * 50)
    print("⏱ TIMING SUMMARY:")
    print(f"  Upload:              {format_duration(upload_duration)}")
    print(f"  Structure extraction: {format_duration(structure_duration)}")
    print(f"  Themes parsing:      {format_duration(themes_duration)}")
    if theme_times:
        avg_theme = sum(theme_times) / len(theme_times)
        print(f"    Avg per theme:     {format_duration(avg_theme)}")
    print(f"  TOTAL:               {format_duration(total_duration)}")
    print("=" * 50)
    print()

    return structure

def parse_pdf_with_gemini(pdf_path: str, chunked: bool = True) -> dict:
    """Parse PDF file using Gemini API

    Args:
        pdf_path: Path to PDF file
        chunked: If True, use chunked parsing (recommended for large files).
                 If False, use single-shot parsing (faster but may hit token limits).
    """

    if chunked:
        return parse_pdf_with_gemini_chunked(pdf_path)

    # Original single-shot approach (kept for compatibility)
    uploaded_file = upload_pdf_to_gemini(pdf_path)

    print("Parsing PDF with Gemini (single-shot mode)...")

    prompt = """Распарси PDF с вопросами "Своя игра" в JSON.

ФОРМАТ ПОЛЯ "form":
"form" - это маркер ЧТО назвать (ИЗ ВОПРОСА, НЕ ИЗ ОТВЕТА!):
- "ОН был профессором" → form: "он"
- "В ЧЕСТЬ НЕГО назвали" → form: "в честь него"
- "ЭТОТ ФРАНЦУЗ" → form: "француз"
- "В ответе одно слово. ОНА" → form: "одним словом, она"

JSON формат:
{"info":"...", "package_name":"...", "themes":[{"name":"...","questions":[{"cost":10,"question":"...","form":"он/она/его/город","answer":"..."}]}]}

ВАЖНО: Опускай "comment" и "accept" если их нет. Будь краток. Закрой все скобки!"""

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

def save_json(data: dict, output_path: str):
    """Save parsed data to JSON file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"JSON saved to: {output_path}")

def validate_json_structure(data: dict) -> bool:
    """Validate that JSON has required structure and all questions have 'form' field"""
    if "info" not in data:
        print("Warning: Missing 'info' field")
        return False

    if "themes" not in data:
        print("Error: Missing 'themes' field")
        return False

    missing_forms = []
    for theme_idx, theme in enumerate(data["themes"]):
        if "questions" not in theme:
            print(f"Error: Theme {theme_idx} missing 'questions' field")
            return False

        for q_idx, question in enumerate(theme["questions"]):
            if "form" not in question:
                missing_forms.append(f"Theme {theme_idx}, Question {q_idx} (cost: {question.get('cost', '?')})")

    if missing_forms:
        print("ERROR: Missing 'form' field in the following questions:")
        for item in missing_forms:
            print(f"  - {item}")
        return False

    print("✓ JSON structure validation passed")
    print(f"✓ All {sum(len(t['questions']) for t in data['themes'])} questions have 'form' field")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_pdf_with_gemini.py <pdf_file_path> [--single-shot]")
        print("\nOptions:")
        print("  --single-shot    Use single-shot parsing (faster, but may hit limits for large files)")
        print("                   By default, chunked parsing is used (recommended)")
        sys.exit(1)

    pdf_path = sys.argv[1]
    chunked = "--single-shot" not in sys.argv

    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    # Generate output path
    pdf_file = Path(pdf_path)
    output_path = pdf_file.parent / f"{pdf_file.stem}_parsed.json"

    print(f"Input PDF: {pdf_path}")
    print(f"Output JSON: {output_path}")
    print(f"Mode: {'Chunked (theme-by-theme)' if chunked else 'Single-shot'}")
    print("-" * 60)

    try:
        # Parse PDF
        result = parse_pdf_with_gemini(pdf_path, chunked=chunked)

        # Validate structure
        if not validate_json_structure(result):
            print("\n⚠️  WARNING: JSON validation failed!")
            print("The JSON structure is incomplete or missing 'form' fields.")
            response = input("Do you want to save anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(1)

        # Save result
        save_json(result, str(output_path))

        print("-" * 60)
        print("✓ Success! PDF parsed and saved to JSON")
        print(f"  Themes: {len(result['themes'])}")
        print(f"  Total questions: {sum(len(t['questions']) for t in result['themes'])}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
