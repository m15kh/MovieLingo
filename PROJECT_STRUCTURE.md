# Project Structure

This document explains the organization and purpose of each file in the English Learning Bot project.

## Directory Structure

```
english-learning-bot/
├── app/                          # Main application package
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI application entry point
│   ├── bot.py                   # Telegram bot setup and configuration
│   │
│   ├── core/                    # Core configuration
│   │   ├── __init__.py
│   │   └── config.py            # Settings and configuration management
│   │
│   ├── database/                # Database layer
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models (User, Challenge, Video, etc.)
│   │   ├── database.py          # Database connection and session management
│   │   └── init_db.py           # Database initialization script
│   │
│   ├── services/                # Business logic services
│   │   ├── __init__.py
│   │   ├── whisper_service.py   # Voice recognition using Whisper
│   │   ├── ollama_service.py    # AI question generation using Ollama
│   │   ├── payment_service.py   # Payment processing with Stripe
│   │   ├── user_service.py      # User management operations
│   │   └── challenge_service.py # Challenge and video attempt management
│   │
│   └── bot/                     # Telegram bot handlers
│       ├── __init__.py
│       ├── handlers.py          # Main user interaction handlers
│       ├── voice_handler.py     # Voice message processing
│       ├── message_handler.py   # Text message handling
│       └── admin_handlers.py    # Admin-only commands and features
│
├── videos/                      # Video storage directory
│   └── .gitkeep
│
├── audio/                       # Temporary audio file storage
│   └── .gitkeep
│
├── logs/                        # Application logs
│   └── .gitkeep
│
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── docker-compose.yml           # Docker Compose configuration
├── Dockerfile                   # Docker image definition
├── requirements.txt             # Python dependencies
├── run_bot.py                   # Bot startup script
├── quick_start.sh               # Quick setup script
├── README.md                    # Project overview
├── SETUP_GUIDE.md              # Detailed setup instructions
└── PROJECT_STRUCTURE.md        # This file
```

## Core Components

### 1. Database Models (`app/database/models.py`)

Defines all database tables:

- **User**: User accounts, status, points, referrals
- **Payment**: Payment records and verification
- **Challenge**: Daily challenges
- **Video**: Video content for challenges
- **Question**: Multiple choice questions for videos
- **ChallengeAttempt**: User's progress in a challenge
- **VideoAttempt**: User's attempts for each video
- **WaitlistEntry**: Users waiting for next challenge

### 2. Services Layer

#### Whisper Service (`app/services/whisper_service.py`)
- Transcribes voice messages
- Compares transcription with target phrases
- Calculates similarity scores
- Provides feedback to users

#### Ollama Service (`app/services/ollama_service.py`)
- Generates multiple choice questions
- Validates phrases for learning
- Uses local LLM for AI features

#### Payment Service (`app/services/payment_service.py`)
- Creates Stripe payment intents
- Verifies payments
- Generates payment links
- Handles refunds

#### User Service (`app/services/user_service.py`)
- User creation and management
- Phone number verification
- Referral tracking
- Points management
- Leaderboard queries

#### Challenge Service (`app/services/challenge_service.py`)
- Challenge creation and management
- Video attempt tracking
- Progress monitoring
- Point calculation

### 3. Bot Handlers

#### Main Handlers (`app/bot/handlers.py`)
- `/start` command - Welcome and registration
- Channel membership verification
- Activation process (payment/referral)
- Challenge initiation
- Video sending
- Leaderboard display
- User statistics

#### Voice Handler (`app/bot/voice_handler.py`)
- Voice message reception
- Audio file processing
- Whisper transcription
- Phrase matching
- Attempt tracking
- Question triggering

#### Message Handler (`app/bot/message_handler.py`)
- Text message processing
- Menu navigation
- Question answering
- Help system

#### Admin Handlers (`app/bot/admin_handlers.py`)
- Admin panel
- Video upload and management
- Challenge creation
- Challenge distribution
- Payment approval
- System statistics

### 4. FastAPI Application (`app/main.py`)

REST API endpoints:

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /api/users/{telegram_id}` - Get user info
- `GET /api/leaderboard` - Get top users
- `GET /api/challenges/active` - Get active challenge
- `GET /api/user/{telegram_id}/progress/{challenge_id}` - User progress
- `POST /api/webhook/stripe` - Stripe webhook handler
- `GET /api/stats` - System statistics

## Data Flow

### User Registration Flow
1. User starts bot → `handlers.start_command()`
2. Check channel membership → `handlers.check_channel_membership()`
3. Request phone number → User shares contact
4. Show activation options → Payment or referral
5. Admin approves → User activated

### Challenge Flow
1. Admin creates challenge → `admin_handlers.handle_create_challenge()`
2. Admin adds 3 videos → `admin_handlers.handle_video_upload()`
3. AI generates questions → `ollama_service.generate_question()`
4. Admin sends challenge → All active users notified
5. User starts challenge → `handlers.handle_start_challenge()`
6. For each video:
   - Send video → `handlers.send_next_video()`
   - User sends voice → `voice_handler.handle_voice()`
   - Whisper transcribes → `whisper_service.transcribe_audio()`
   - Check match → Record attempt
   - Send question → User answers
   - Award points → Update leaderboard
7. Complete challenge → Show results

### Payment Flow
1. User chooses payment → `handlers.handle_activation_callback()`
2. Generate Stripe link → `payment_service.create_payment_link()`
3. User pays → Stripe webhook triggers
4. Admin approves → `admin_handlers.approve_payment()`
5. User activated → Can participate

## Key Features

### Voice Recognition
- Uses OpenAI Whisper (base model by default)
- Configurable similarity threshold (75% default)
- 2 attempts without subtitles
- Subtitle reveal after failed attempts
- 2 more attempts with subtitles

### AI Question Generation
- Uses Ollama with Llama2
- Generates contextual questions
- 4 multiple choice options
- Example sentences provided
- Fallback questions if AI fails

### Gamification
- Points for correct voice (50 points)
- Points for correct answers (50 points)
- Real-time leaderboard
- Referral system
- Daily challenges

### Payment System
- Stripe integration
- $1 activation fee
- Admin approval required
- Payment verification
- Webhook support

### Admin Features
- Video management
- Challenge scheduling
- Payment approval
- User statistics
- Bulk notifications

## Configuration

All configuration is managed through environment variables in `.env`:

- Bot token and channels
- Database connection
- Ollama settings
- Whisper model
- Stripe keys
- Point values
- Timing settings

See `.env.example` for all available options.

## Dependencies

### Core
- `fastapi` - Web framework
- `python-telegram-bot` - Telegram integration
- `sqlalchemy` - Database ORM
- `asyncpg` - PostgreSQL async driver

### AI/ML
- `openai-whisper` - Voice recognition
- `ollama` - Local LLM
- `torch` - PyTorch for Whisper

### Utilities
- `stripe` - Payment processing
- `pydub` - Audio processing
- `loguru` - Logging

## Development Tips

### Adding New Features

1. **New Database Model**: Add to `models.py`
2. **New Service**: Create in `services/`
3. **New Bot Command**: Add handler in `bot/handlers.py`
4. **New API Endpoint**: Add to `main.py`

### Testing

```bash
# Run tests
pytest

# Test specific module
pytest app/services/test_user_service.py

# Check coverage
pytest --cov=app
```

### Debugging

1. Check logs: `tail -f app.log`
2. Enable debug: Set `DEBUG=True` in `.env`
3. Database queries: SQLAlchemy echo enabled in debug mode
4. Bot updates: Check Telegram bot logs

## Deployment

### Development
```bash
uvicorn app.main:app --reload
python run_bot.py
```

### Production
```bash
docker-compose up -d
```

## Security Considerations

1. **Environment Variables**: Never commit `.env`
2. **Admin Access**: Verify user IDs in `ADMIN_USER_IDS`
3. **Payment Verification**: Validate Stripe webhooks
4. **User Data**: Encrypt sensitive information
5. **Rate Limiting**: Implement for API endpoints

## Performance Optimization

1. **Caching**: Video file_ids cached after first send
2. **Database**: Indexes on frequently queried columns
3. **Connection Pool**: Configured in `database.py`
4. **Async Operations**: All I/O operations are async
5. **Media Storage**: Local filesystem, consider S3 for scale

## Maintenance

### Regular Tasks
- Database backups
- Log rotation
- Dependency updates
- Performance monitoring
- User support

### Monitoring
- Check bot uptime
- Monitor error logs
- Track user metrics
- Review payment processing
- Database performance

## Future Enhancements

Potential features to add:
- User profiles and avatars
- Achievement system
- Social features (friend challenges)
- Multiple difficulty levels
- Progress tracking over time
- Mobile app integration
- Advanced analytics
- Multiple language support

---

For more information, see:
- [README.md](README.md) - Project overview
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Setup instructions
