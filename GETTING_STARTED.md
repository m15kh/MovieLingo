# 🚀 Getting Started - Quick Guide

Welcome to the English Learning Telegram Bot! This guide will get you up and running in under 10 minutes.

## ⚡ Quick Start (3 Steps)

### 1. Prerequisites Check
```bash
# Check Python (need 3.10+)
python3 --version

# Install if needed
# Ubuntu: sudo apt install python3.10
# macOS: brew install python@3.10
```

### 2. Configure & Setup
```bash
# Run the quick start script
chmod +x quick_start.sh
./quick_start.sh
```

### 3. Edit Configuration
```bash
# Open and edit .env file
nano .env
```

**Minimum required settings:**
```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
REQUIRED_CHANNEL_1=@your_channel_1
REQUIRED_CHANNEL_2=@your_channel_2
ADMIN_USER_IDS=your_telegram_user_id
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/english_learning_bot
STRIPE_SECRET_KEY=sk_test_your_stripe_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_key
```

## 🎯 Get Your Credentials

### Telegram Bot Token
1. Search `@BotFather` on Telegram
2. Send `/newbot`
3. Follow prompts
4. Copy token (looks like: `1234567890:ABC...`)

### Your Telegram User ID
1. Search `@userinfobot` on Telegram
2. Send any message
3. Copy your user ID

### Stripe Keys (for payments)
1. Sign up at https://stripe.com
2. Go to: Developers → API Keys
3. Copy test keys (start with `sk_test_` and `pk_test_`)

## 🏃 Running the Bot

### Quick Method (Docker)
```bash
docker-compose up -d
```

### Manual Method
```bash
# Terminal 1 - Start API
uvicorn app.main:app --reload

# Terminal 2 - Start Bot
python run_bot.py
```

## ✅ Verify It's Working

1. Open Telegram
2. Search for your bot
3. Send `/start`
4. You should get a welcome message!

## 📚 Next Steps

1. **Create Channels**: Make 2 Telegram channels
2. **Add Bot as Admin**: In both channels
3. **Create First Challenge**: Use `/admin_panel` command
4. **Add Videos**: Upload 3 video clips
5. **Launch**: Send challenge to users

## 📖 Detailed Documentation

- **Full Setup**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Project Structure**: See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- **README**: See [README.md](README.md)

## 🆘 Common Issues

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Database connection failed"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Create database
createdb english_learning_bot
```

### "Ollama not responding"
```bash
# Start Ollama
ollama serve

# In another terminal
ollama pull llama2
```

### "Bot not responding"
- Check bot token in `.env`
- Verify bot is running: `ps aux | grep python`
- Check logs: `tail -f app.log`

## 💡 Pro Tips

1. **Test Mode**: Use Stripe test keys for development
2. **Debug**: Set `DEBUG=True` in `.env` for verbose logs
3. **Backup**: Regular database backups are crucial
4. **Monitor**: Check logs regularly
5. **Updates**: Keep dependencies updated

## 🎬 Admin Workflow

```
/admin_panel                    # Open admin controls
/create_challenge My Challenge  # Create new challenge
/add_video 1                    # Start adding video
[Upload video file]             # Send video
/set_phrase "Break a leg"       # Set the phrase
/finalize_video                 # Complete video
[Repeat for 2 more videos]      # Add remaining videos
/admin_panel → Send Challenge   # Launch to users
```

## 📞 Support

If you encounter issues:
1. Check the logs: `tail -f app.log`
2. Review error messages carefully
3. Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed troubleshooting
4. Verify all environment variables are set

## 🎉 You're Ready!

Your English Learning Bot is ready to go! Start by:
1. Testing the user flow yourself
2. Creating your first challenge
3. Inviting test users
4. Gathering feedback
5. Iterating and improving

Good luck! 🚀

---

**Quick Command Reference**

User Commands:
- `/start` - Start the bot
- `/help` - Get help

Admin Commands:
- `/admin_panel` - Admin dashboard
- `/create_challenge` - New challenge
- `/add_video` - Add video to challenge

---

For detailed documentation, see the other MD files in this project.
