#!/usr/bin/env python3
"""
Parse quiz pack PDF/DOCX files using a local LLM (Ollama, LM Studio, vLLM, etc.)

Usage:
  python parse_pdf_with_local_llm.py pack.docx
  python parse_pdf_with_local_llm.py pack.pdf --model qwen2.5:32b
  python parse_pdf_with_local_llm.py pack.docx --api-type openai --base-url http://localhost:1234/v1
"""

import argparse
import os
import sys
import time
from pathlib import Path

import requests
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

DEFAULT_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5:32b")
DEFAULT_API_TYPE = os.environ.get("LOCAL_LLM_API_TYPE", "ollama")
DEFAULT_MAX_TOKENS = int(os.environ.get("LOCAL_LLM_MAX_TOKENS", "8192"))
DEFAULT_TIMEOUT = int(os.environ.get("LOCAL_LLM_TIMEOUT", "600"))


class LocalLLMClient:
    """Client for local LLM backends: Ollama or OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_type: str = DEFAULT_API_TYPE,
        temperature: float = 0.1,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: int = DEFAULT_TIMEOUT,
        json_mode: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_type = api_type.lower()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.json_mode = json_mode

        if self.api_type not in ("ollama", "openai"):
            raise ValueError(f"Unsupported api_type: {api_type}. Use 'ollama' or 'openai'.")

    def check_connection(self) -> None:
        try:
            if self.api_type == "ollama":
                response = requests.get(f"{self.base_url}/api/tags", timeout=10)
                response.raise_for_status()
                models = [m.get("name", "") for m in response.json().get("models", [])]
                if models and not any(self.model in m or m.startswith(self.model) for m in models):
                    print(f"⚠️  Model '{self.model}' not found locally. Available: {', '.join(models[:5])}")
                    print(f"   Pull it with: ollama pull {self.model}")
            else:
                response = requests.get(f"{self.base_url}/models", timeout=10)
                response.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(
                f"Cannot connect to local LLM at {self.base_url}\n"
                f"Error: {e}\n"
                f"Make sure Ollama/LM Studio/vLLM is running."
            ) from e

    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        if self.api_type == "ollama":
            return self._generate_ollama(user_prompt, system_prompt)
        return self._generate_openai(user_prompt, system_prompt)

    def _generate_ollama(self, user_prompt: str, system_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if self.json_mode:
            payload["format"] = "json"

        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(f"Ollama error: {data['error']}")

        message = data.get("message", {})
        content = message.get("content")
        if not content:
            raise ValueError(f"Empty response from Ollama: {data}")
        return content

    def _generate_openai(self, user_prompt: str, system_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Empty response from OpenAI-compatible API: {data}")

        content = choices[0].get("message", {}).get("content")
        if not content:
            raise ValueError(f"Empty content in response: {data}")
        return content


def get_package_structure(client: LocalLLMClient, text_content: str, is_merged: bool = False) -> dict:
    print("Step 1/2: Getting package structure...")

    prompt = build_structure_prompt(is_merged=is_merged)
    user_message = build_user_message(prompt, text_content)

    response_text = client.generate(user_message)
    return extract_json_from_response(response_text)


def parse_theme_questions(
    client: LocalLLMClient,
    text_content: str,
    theme_name: str,
    theme_index: int = 0,
    is_merged: bool = False,
) -> dict:
    print(f"  Parsing theme {theme_index + 1}: {theme_name[:50]}...")

    prompt = build_theme_prompt(theme_name, theme_index, is_merged=is_merged)
    user_message = build_user_message(prompt, text_content)

    response_text = client.generate(user_message)
    result = extract_json_from_response(response_text)

    if isinstance(result, list):
        return {"questions": result}
    if isinstance(result, dict) and "questions" in result:
        return result
    raise ValueError(f"Expected dict with questions or list, got {type(result)}")


def parse_with_local_llm(
    file_path: str,
    client: LocalLLMClient,
    is_merged: bool = False,
) -> dict:
    total_start = time.time()

    extract_start = time.time()
    print(f"Extracting text from: {Path(file_path).name}")
    text_content = extract_text(file_path)
    extract_duration = time.time() - extract_start
    print(f"  ⏱ Text extraction took: {format_duration(extract_duration)}")
    print(f"  Text length: {len(text_content)} chars")

    structure_start = time.time()
    structure = get_package_structure(client, text_content, is_merged=is_merged)
    structure_duration = time.time() - structure_start
    print(f"  ⏱ Structure extraction took: {format_duration(structure_duration)}")

    if "themes" not in structure or not structure["themes"]:
        raise ValueError("Failed to extract themes from text")

    print(f"Found {len(structure['themes'])} themes")
    print("Step 2/2: Parsing questions for each theme...")

    themes_start = time.time()
    theme_times = []
    failed_themes = []

    for i, theme in enumerate(structure["themes"]):
        theme_start = time.time()
        theme_name = theme.get("name", f"Theme {i + 1}")
        try:
            result = parse_theme_questions(
                client,
                text_content,
                theme_name=theme_name,
                theme_index=i,
                is_merged=is_merged,
            )
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

    themes_duration = time.time() - themes_start
    total_duration = time.time() - total_start

    print()
    print("=" * 50)
    print("⏱ TIMING SUMMARY (LOCAL LLM):")
    print(f"  Text extraction:      {format_duration(extract_duration)}")
    print(f"  Structure extraction: {format_duration(structure_duration)}")
    print(f"  Themes parsing:       {format_duration(themes_duration)}")
    if theme_times:
        avg_theme = sum(theme_times) / len(theme_times)
        print(f"    Avg per theme:      {format_duration(avg_theme)}")
    print(f"  TOTAL:                {format_duration(total_duration)}")
    if failed_themes:
        print(f"  ⚠️ FAILED THEMES:     {len(failed_themes)}")
        for num, name, err in failed_themes:
            print(f"    - Theme {num}: {name[:40]}...")
    print("=" * 50)
    print()

    return structure


def resolve_input_file(input_path: Path, is_folder: bool) -> tuple[str, bool, Path]:
    is_merged = False

    if is_folder or (input_path.exists() and input_path.is_dir()):
        print(f"Folder mode: processing {input_path}")
        print("-" * 60)

        pdf_files = sorted(input_path.glob('*.pdf'))
        docx_files = sorted([f for f in input_path.glob('*.docx') if not f.name.startswith('~$')])

        if not pdf_files and not docx_files:
            print(f"❌ Error: No PDF or DOCX files found in {input_path}")
            sys.exit(1)

        print(f"Found {len(pdf_files)} PDF file(s) and {len(docx_files)} DOCX file(s)")

        all_pdfs = []
        if pdf_files:
            all_pdfs.extend(pdf_files)
            print(f"  ✓ {len(pdf_files)} PDF file(s) ready")

        if docx_files:
            print(f"  Converting {len(docx_files)} DOCX file(s) to PDF...")
            for i, docx_file in enumerate(docx_files, 1):
                print(f"    [{i}/{len(docx_files)}] Converting {docx_file.name}...")
                try:
                    converted_pdf = convert_docx_to_pdf(str(docx_file))
                    all_pdfs.append(Path(converted_pdf))
                    print(f"      ✓ Created: {Path(converted_pdf).name}")
                except Exception as e:
                    print(f"      ⚠️  Failed to convert {docx_file.name}: {e}")

        if not all_pdfs:
            print("❌ Error: No valid PDF files to process")
            sys.exit(1)

        all_pdfs = sorted(all_pdfs, key=lambda p: p.name)
        merged_pdf_path = input_path / f"{input_path.name}_merged.pdf"

        print(f"\nMerging {len(all_pdfs)} PDF file(s) into one...")
        merge_pdfs(all_pdfs, str(merged_pdf_path))
        print(f"✓ Merged PDF created: {merged_pdf_path}")

        return str(merged_pdf_path), True, input_path

    if input_path.exists() and input_path.is_file():
        if input_path.suffix.lower() == '.docx':
            print("Converting DOCX to PDF for text extraction...")
            file_path = convert_docx_to_pdf(str(input_path))
        else:
            file_path = str(input_path)
        return file_path, False, input_path

    print(f"Error: Path not found: {input_path}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Parse quiz pack PDF/DOCX files using a local LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ollama (default)
  python parse_pdf_with_local_llm.py pack.docx
  python parse_pdf_with_local_llm.py pack.pdf --model qwen2.5:32b

  # LM Studio / vLLM (OpenAI-compatible API)
  python parse_pdf_with_local_llm.py pack.docx --api-type openai --base-url http://localhost:1234/v1

  # Folder with multiple files
  python parse_pdf_with_local_llm.py Лагерь_Блик_2024_ЭК/

Recommended models (see README_LOCAL_LLM_PARSER.md):
  ollama pull qwen2.5:32b        # best balance (16+ GB VRAM)
  ollama pull qwen2.5:14b        # good quality (10+ GB VRAM)
  ollama pull deepseek-r1:14b    # strong reasoning
        """
    )
    parser.add_argument('input_path', help='PDF file, DOCX file, or folder path')
    parser.add_argument('--folder', action='store_true', help='Treat input_path as folder and merge files')
    parser.add_argument('--model', default=DEFAULT_MODEL, help=f'Model name (default: {DEFAULT_MODEL})')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL, help=f'API base URL (default: {DEFAULT_BASE_URL})')
    parser.add_argument('--api-type', choices=['ollama', 'openai'], default=DEFAULT_API_TYPE,
                        help=f'API type: ollama or openai-compatible (default: {DEFAULT_API_TYPE})')
    parser.add_argument('--temperature', type=float, default=0.1, help='Sampling temperature (default: 0.1)')
    parser.add_argument('--max-tokens', type=int, default=DEFAULT_MAX_TOKENS, help='Max output tokens')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='Request timeout in seconds')
    parser.add_argument('--no-json-mode', action='store_true', help='Disable JSON mode (structured output)')

    args = parser.parse_args()

    input_path = Path(args.input_path)
    file_path, is_merged, output_base = resolve_input_file(input_path, args.folder)

    if is_merged:
        output_path = output_base / f"{output_base.name}_parsed.json"
    else:
        output_path = Path(file_path).parent / f"{Path(file_path).stem}_parsed.json"

    client = LocalLLMClient(
        base_url=args.base_url,
        model=args.model,
        api_type=args.api_type,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        json_mode=not args.no_json_mode,
    )

    print(f"Input: {input_path}")
    print(f"Output JSON: {output_path}")
    print(f"Model: {args.model}")
    print(f"API: {args.api_type} @ {args.base_url}")
    print(f"JSON mode: {not args.no_json_mode}")
    if is_merged:
        print("Note: Processing merged file (multiple боёв)")
    print("-" * 60)

    try:
        client.check_connection()
        result = parse_with_local_llm(file_path, client, is_merged=is_merged)

        save_json(result, str(output_path))
        print()

        validation_passed = validate_json_structure(result)

        if not validation_passed:
            print("\n⚠️  WARNING: JSON validation failed!")
            print("The JSON structure is incomplete or missing 'form' fields.")
            print(f"⚠️  JSON saved anyway to: {output_path}")
            print("You can fix it manually or re-run with a larger/better model.")
            sys.exit(1)

        print("-" * 60)
        print("✓ Success! File parsed and saved to JSON")
        print(f"  Themes: {len(result['themes'])}")
        print(f"  Total questions: {sum(len(t['questions']) for t in result['themes'])}")

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
