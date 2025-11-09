# English Learning Telegram Bot

A comprehensive English learning platform using movie clips, voice recognition, and gamification.

## Features

- 📹 Daily video challenges with movie clips
- 🎤 Voice recognition using Whisper AI
- 🤖 AI-generated questions using Ollama
- 💰 Payment integration
- 📊 Leaderboard system
- 👥 Referral system
- 🔐 Channel membership verification
- ⏰ Challenge scheduling

## Tech Stack

- **Backend**: FastAPI
- **Bot**: python-telegram-bot
- **Voice Recognition**: OpenAI Whisper
- **LLM**: Ollama
- **Database**: PostgreSQL
- **Payment**: Stripe (easily replaceable)
- **Deployment**: Docker

## Prerequisites

- Python 3.10+
- PostgreSQL
- Ollama installed locally or accessible via API
- Telegram Bot Token (from @BotFather)
- Stripe Account (for payments)

## Quick Start

### 1. Clone and Setup

```bash
cd english-learning-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your configuration.

### 3. Setup Database

```bash
# Create database
createdb english_learning_bot

# Run migrations
python -m app.database.init_db
```

### 4. Start Ollama

```bash
# Pull the model
ollama pull llama2

# Ollama should be running on http://localhost:11434
```

### 5. Run the Application

```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# In another terminal, start the bot
python run_bot.py
```

## Docker Deployment

```bash
docker-compose up -d
```

## Project Structure

```
english-learning-bot/
├── app/
│   ├── api/              # FastAPI routes
│   ├── bot/              # Telegram bot handlers
│   ├── core/             # Core configuration
│   ├── database/         # Database models and connection
│   ├── services/         # Business logic services
│   ├── schemas/          # Pydantic models
│   └── utils/            # Utility functions
├── videos/               # Video storage
├── audio/                # Temporary audio files
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Admin Commands

- `/admin_panel` - Open admin dashboard
- `/send_challenge` - Send today's challenge
- `/add_video` - Add new video
- `/approve_payment <user_id>` - Approve payment
- `/stats` - View statistics

## User Flow

1. User starts bot → Channel membership check
2. User shares phone number
3. User pays $1 or invites 5 people
4. Admin approves → User activated
5. User receives daily challenge (3 videos)
6. User attempts voice recognition (2 attempts)
7. If failed → Subtitles shown (2 more attempts)
8. User answers multiple choice question
9. Points awarded → Leaderboard updated

## Configuration

Key settings in `.env`:

- `TELEGRAM_BOT_TOKEN`: Your bot token
- `REQUIRED_CHANNEL_1`: First required channel
- `REQUIRED_CHANNEL_2`: Second required channel
- `ADMIN_USER_IDS`: Comma-separated admin IDs
- `STRIPE_SECRET_KEY`: Payment gateway key
- `DATABASE_URL`: PostgreSQL connection string
- `OLLAMA_API_URL`: Ollama API endpoint

## Development

```bash
# Run tests
pytest

# Format code
black app/
isort app/

# Lint
flake8 app/
```

## Troubleshooting

### Whisper not working
- Ensure ffmpeg is installed: `apt-get install ffmpeg`
- Check audio file format (should be .ogg or .mp3)

### Ollama connection failed
- Verify Ollama is running: `curl http://localhost:11434`
- Check firewall settings

### Database errors
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Run migrations: `python -m app.database.init_db`

## License

MIT License

## Support

For issues and questions, please open a GitHub issue.
