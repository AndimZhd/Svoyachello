# Svoyachello 🎮

A Telegram bot for playing "Своя игра" (Russian Jeopardy!) with friends.

## Features

- **Multiplayer games** — Create and join games in group chats
- **Question packs** — Import question packs from PDF files
- **Smart pack selection** — Automatically selects packs with unplayed themes for all players
- **Partial question display** — Long questions can be revealed progressively in parts
- **Game state machine** — Automated question flow with pause/resume support
- **Score tracking** — Real-time score updates with correction support
- **Player statistics** — ELO rating, win streaks, answer accuracy, and more

## Setup

### 1. Prerequisites

- Python 3.13+
- PostgreSQL database
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Install dependencies

```bash
python -m venv .
source bin/activate  # On Windows: .\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your-bot-token-here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=svoyachello
DB_USER=your-username
DB_PASSWORD=your-password
```

### 4. Initialize database

Run the migration script in PostgreSQL:

```bash
psql -d svoyachello -f migrations/001_user_stats.sql
```

### 5. Add game chats

The bot uses dedicated chats for running games. Add chat IDs to `migrations/002_insert_game_chats.sql` and run it.

### 6. Run the bot

```bash
python bot.py
```

## Commands

### Registration Chat (Group Chats)

| Command | Alias | Description |
|---------|-------|-------------|
| `/register` | `+` | Join the current game |
| `/unregister` | `-` | Leave the current game |
| `/themes <N>` | `темы <N>` | Set number of themes (default: 6) |
| `/pack <name>` | `пак <name>` | Select a question pack |
| `/pack_list` | `паки` | List available packs |
| `/start` | `старт` | Start the game |
| `/player_info` | — | View your statistics |

### Game Chat (During Game)

| Command | Alias | Description |
|---------|-------|-------------|
| `/answer` | `+` | Buzz in to answer |
| `/pause` | `пауза`, `стоямба` | Pause the game |
| `/resume` | `продолжить`, `го` | Resume the game |
| `/yes` | `да` | Confirm correct answer (score correction) |
| `/no` | `нет` | Mark answer as incorrect (score correction) |
| `/accidentally` | `случайно` | Mark accidental buzz-in |
| `/partial_display` | `постепенный показ` | Toggle partial question display |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/abort_all` | Cancel all active games |

## Importing Question Packs

Use the PDF parser script to import question packs:

```bash
python scripts/parse_pack.py <pack_name> <short_name> <pdf_file>
```

Example:
```bash
python scripts/parse_pack.py "Синхрон от КМС" "kmssync" packs/kms_sync.pdf
```

### PDF Format Requirements

The parser expects packs in this format:
- **Pack info** at the beginning
- **Themes** in bold with numbers: `1. Theme Name`
- **Author** after theme: `Автор: Author Name`
- **Questions** numbered: `1. Question text`
- **Answers** marked: `Ответ: Answer text`
- **Alternative answers**: `Зачёт: Alternative answer`
- **Comments** (optional): `Комментарий: Comment text`

## Project Structure

```
├── bot.py                 # Main entry point
├── commands/              # Command handlers
│   ├── register.py        # /register, /unregister
│   ├── start.py           # /start game
│   ├── answer.py          # /answer, /yes, /no
│   ├── pause.py           # /pause, /resume
│   ├── settings.py        # /themes, /pack, /pack_list
│   ├── player_info.py     # /player_info
│   └── events.py          # Chat member events
├── database/              # Database operations
│   ├── connection.py      # PostgreSQL connection
│   ├── players.py         # Player CRUD
│   ├── games.py           # Game CRUD
│   ├── packs.py           # Pack CRUD
│   └── game_chats.py      # Game chat management
├── game/                  # Game logic
│   └── state_machine.py   # Game state machine
├── messages/              # Bot message templates
├── migrations/            # SQL migrations
├── scripts/               # Utility scripts
│   └── parse_pack.py      # PDF pack parser
└── sql/                   # SQL queries
```

## Game Flow

1. **Registration** — Players join in a group chat using `/register`
2. **Configuration** — Set themes count and select pack (optional)
3. **Start** — Bot creates invite link to a game chat
4. **Play** — Bot automatically sends questions, players buzz in with `+`
5. **Score Correction** — After each question, players can correct scores
6. **End** — Game ends after all themes are played

## License

[THE BEER-WARE LICENSE](LICENSE)
