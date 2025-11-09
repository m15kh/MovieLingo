# Complete Setup Guide

This guide will walk you through setting up the English Learning Telegram Bot from scratch.

## Prerequisites

1. **Python 3.10 or higher**
   ```bash
   python --version  # Should be 3.10+
   ```

2. **PostgreSQL Database**
   ```bash
   # Install on Ubuntu/Debian
   sudo apt update
   sudo apt install postgresql postgresql-contrib
   
   # Install on macOS
   brew install postgresql
   ```

3. **Ollama** (for AI features)
   ```bash
   # Install Ollama
   curl https://ollama.ai/install.sh | sh
   
   # Pull the model
   ollama pull llama2
   ```

4. **FFmpeg** (for audio processing)
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

## Step 1: Get Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this token - you'll need it for configuration

## Step 2: Create Required Telegram Channels

1. Create two Telegram channels for membership requirements
2. Make your bot an administrator in both channels
3. Get channel usernames (e.g., `@your_channel_1`, `@your_channel_2`)

## Step 3: Get Stripe API Keys (for payments)

1. Sign up at https://stripe.com
2. Go to Developers → API Keys
3. Copy your:
   - Secret Key (sk_test_...)
   - Publishable Key (pk_test_...)

## Step 4: Setup the Project

### Clone and Navigate

```bash
cd english-learning-bot
```

### Create Virtual Environment

```bash
python -m venv venv

# Activate on Linux/macOS
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 5: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` file with your credentials:
   ```bash
   nano .env  # or use any text editor
   ```

3. Fill in the required values:

```env
# REQUIRED - Telegram Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
REQUIRED_CHANNEL_1=@your_channel_1
REQUIRED_CHANNEL_2=@your_channel_2
ADMIN_USER_IDS=123456789,987654321  # Your Telegram user ID

# REQUIRED - Database
DATABASE_URL=postgresql+asyncpg://your_username:your_password@localhost:5432/english_learning_bot

# REQUIRED - Stripe
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here

# Optional - Can use defaults
OLLAMA_API_URL=http://localhost:11434
WHISPER_MODEL=base
SECRET_KEY=your-super-secret-key-change-this
```

### How to Get Your Telegram User ID

1. Send a message to `@userinfobot` on Telegram
2. It will reply with your user ID
3. Add this ID to `ADMIN_USER_IDS` in `.env`

## Step 6: Setup Database

1. Create PostgreSQL database:
   ```bash
   # Login to PostgreSQL
   sudo -u postgres psql
   
   # Create database and user
   CREATE DATABASE english_learning_bot;
   CREATE USER your_username WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE english_learning_bot TO your_username;
   \q
   ```

2. Initialize database tables:
   ```bash
   python -m app.database.init_db
   ```

   You should see:
   ```
   🚀 Starting database initialization...
   ✅ Database initialized successfully
   ✨ Database setup complete!
   ```

## Step 7: Start Ollama

```bash
# Start Ollama service
ollama serve

# In another terminal, verify it's running
curl http://localhost:11434
```

## Step 8: Run the Application

### Option 1: Run Locally (Development)

1. Start the FastAPI server (Terminal 1):
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. Start the Telegram bot (Terminal 2):
   ```bash
   python run_bot.py
   ```

### Option 2: Run with Docker (Production)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Step 9: Test the Bot

1. Open Telegram and search for your bot
2. Send `/start` command
3. Follow the prompts to:
   - Join required channels
   - Share phone number
   - Complete payment or invite friends

## Step 10: Admin Setup

### Access Admin Panel

1. Send `/admin_panel` to your bot
2. You should see admin controls

### Create First Challenge

1. Use `/create_challenge Daily Challenge 1`
2. Note the Challenge ID (e.g., 1)

### Add Videos

1. For each video (need 3 videos per challenge):
   ```
   /add_video 1
   [Send video file]
   /set_phrase "Break a leg"
   /set_subtitle "Break a leg" (optional)
   /finalize_video
   ```

2. Repeat for all 3 videos

### Launch Challenge

1. Use `/admin_panel`
2. Click "📤 Send Challenge"
3. Active users will receive notifications

## Troubleshooting

### Bot Not Responding

1. Check bot token is correct in `.env`
2. Verify bot is running: `ps aux | grep python`
3. Check logs for errors

### Database Connection Error

1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check DATABASE_URL in `.env`
3. Ensure database exists and user has permissions

### Whisper/Audio Processing Issues

1. Install ffmpeg: `sudo apt install ffmpeg`
2. Check audio file format (should be .ogg)
3. Verify AUDIO_STORAGE_PATH exists

### Ollama Not Working

1. Check if Ollama is running: `curl http://localhost:11434`
2. Pull the model: `ollama pull llama2`
3. Check OLLAMA_API_URL in `.env`

### Payment Issues

1. Verify Stripe keys in `.env`
2. Check Stripe dashboard for test transactions
3. Ensure webhook is configured (for production)

## Production Deployment

### Security Checklist

- [ ] Change SECRET_KEY to a strong random value
- [ ] Use production Stripe keys
- [ ] Set DEBUG=False
- [ ] Use environment-specific .env file
- [ ] Enable HTTPS for webhook endpoints
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Set up monitoring

### Recommended Hosting

1. **VPS Options**: DigitalOcean, AWS, Google Cloud
2. **Database**: Managed PostgreSQL
3. **Minimum Requirements**:
   - 2 GB RAM
   - 2 CPU cores
   - 20 GB storage
   - GPU optional (for faster Whisper)

### Using Docker in Production

```bash
# Build and run
docker-compose -f docker-compose.yml up -d

# Update
git pull
docker-compose build
docker-compose up -d

# Backup database
docker exec english_bot_db pg_dump -U botuser english_learning_bot > backup.sql
```

## Maintenance

### Regular Tasks

1. **Database Backups**: Daily
   ```bash
   pg_dump -U username english_learning_bot > backup_$(date +%Y%m%d).sql
   ```

2. **Clean Audio Files**: Weekly
   ```bash
   find ./audio -mtime +7 -delete
   ```

3. **Monitor Logs**: Daily
   ```bash
   tail -f app.log
   ```

4. **Update Dependencies**: Monthly
   ```bash
   pip list --outdated
   pip install --upgrade package_name
   ```

## Support

For issues or questions:
1. Check logs: `tail -f app.log`
2. Review error messages
3. Check GitHub issues
4. Contact support

## Next Steps

1. Customize welcome messages in `app/bot/handlers.py`
2. Add more language learning features
3. Integrate analytics
4. Add user feedback system
5. Create admin dashboard UI

Congratulations! Your English Learning Bot is now ready! 🎉
