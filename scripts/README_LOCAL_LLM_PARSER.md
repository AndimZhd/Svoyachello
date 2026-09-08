# Local LLM Parser для пакетов Своячка

Парсинг PDF/DOCX файлов с вопросами в JSON через локальную open-source модель (Ollama, LM Studio, vLLM).

Архитектура повторяет `parse_pdf_with_gemini.py`:
1. Извлечение текста из PDF/DOCX
2. Проход 1: метаданные + список тем
3. Проход 2: парсинг вопросов по каждой теме отдельно

## Установка

```bash
pip install -r scripts/requirements_local_llm.txt
```

### Ollama (рекомендуется)

```bash
# macOS
brew install ollama
ollama serve

# Скачать модель
ollama pull qwen2.5:32b
```

### LM Studio / vLLM

Запустите сервер с OpenAI-compatible API и укажите `--api-type openai --base-url http://localhost:PORT/v1`.

## Переменные окружения (.env)

```bash
LOCAL_LLM_BASE_URL=http://localhost:11434   # Ollama по умолчанию
LOCAL_LLM_MODEL=qwen2.5:32b
LOCAL_LLM_API_TYPE=ollama                   # или openai
LOCAL_LLM_MAX_TOKENS=8192
LOCAL_LLM_TIMEOUT=600
```

## Использование

```bash
# Один файл
python scripts/parse_pdf_with_local_llm.py pack.docx
python scripts/parse_pdf_with_local_llm.py pack.pdf --model qwen2.5:32b

# Папка с несколькими файлами
python scripts/parse_pdf_with_local_llm.py Лагерь_Блик_2024_ЭК/

# LM Studio
python scripts/parse_pdf_with_local_llm.py pack.docx \
  --api-type openai \
  --base-url http://localhost:1234/v1 \
  --model qwen2.5-32b-instruct
```

Результат: `НАЗВАНИЕ_ПАКА_parsed.json` в той же папке.

## Рекомендуемые open-source модели

Задача требует: русский язык, следование сложным инструкциям, структурированный JSON, извлечение поля `form` из контекста.

### Топ-рекомендации

| Модель | VRAM | Качество | Скорость | Комментарий |
|--------|------|----------|----------|-------------|
| **Qwen2.5:32b** | 16–20 GB | ★★★★★ | ★★★☆☆ | **Лучший баланс.** Отличный русский, нативная поддержка JSON, 128K контекст |
| **Qwen2.5:14b** | 10–12 GB | ★★★★☆ | ★★★★☆ | Хороший компромисс для Mac с 16 GB RAM |
| **DeepSeek-R1:14b** | 10–12 GB | ★★★★☆ | ★★☆☆☆ | Сильное рассуждение, но медленнее из-за chain-of-thought |
| **Qwen2.5:7b** | 6–8 GB | ★★★☆☆ | ★★★★★ | Для слабого железа; `form` будет чаще ошибаться |
| **Llama 3.3:70b** | 40+ GB | ★★★★★ | ★★☆☆☆ | Высокое качество, но русский слабее Qwen |
| **Mistral-Nemo:12b** | 8–10 GB | ★★★☆☆ | ★★★★☆ | Мультиязычная, но хуже с кириллицей |

### Не рекомендуется для этой задачи

- **Gemma 2 (9B/27B)** — слабый русский
- **Phi-4 (14B)** — хорош в коде, но слаб в длинных русскоязычных документах
- **Модели < 7B** — не справляются с полем `form` и длинными пакетами

### Почему Qwen2.5 — оптимальный выбор

1. Обучена на 18T токенов, 29+ языков включая русский и белорусский
2. Улучшенный instruction following и JSON output (важно для поля `form`)
3. Контекст 128K — весь пакет помещается в один запрос
4. Ollama поддерживает `format: "json"` для гарантированного JSON
5. Qwen2.5-32B по бенчмаркам близка к GPT-4o-mini в structured tasks

### Требования к железу (Ollama, Q4 квантизация)

| Модель | RAM/VRAM | Пример |
|--------|----------|--------|
| qwen2.5:7b | 6 GB | MacBook Air M2 8GB (медленно) |
| qwen2.5:14b | 10 GB | MacBook Pro M3 16GB |
| qwen2.5:32b | 20 GB | Mac Studio M2 Ultra / RTX 4090 |
| qwen2.5:72b | 48 GB | 2× RTX 4090 / Mac Studio 192GB |

## Сравнение с Gemini

| | Gemini 2.5 Pro | Local Qwen2.5:32b |
|--|----------------|-------------------|
| Стоимость | ~$1 за пакет 36 тем | Бесплатно |
| Скорость | ~5–10 мин | ~20–60 мин (зависит от GPU) |
| Качество `form` | ★★★★★ | ★★★★☆ |
| Приватность | Данные уходят в API | Полностью локально |
| PDF upload | Да (vision) | Нет (только текст) |

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `Cannot connect to local LLM` | Запустите `ollama serve` или LM Studio |
| `Model not found` | `ollama pull qwen2.5:32b` |
| JSON обрезан | Увеличьте `--max-tokens 16384` |
| Медленный парсинг | Используйте GPU; попробуйте qwen2.5:14b |
| Плохое поле `form` | Переключитесь на 32b+ модель |
| `Missing 'form' field` | JSON сохранится с предупреждением; перезапустите с лучшей моделью |

## Добавление пакета в БД

```bash
python scripts/append_pack.py <short_name> <json_file> --name "<полное название>"
```
