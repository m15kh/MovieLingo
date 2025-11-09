#!/bin/bash

# Quick Start Script for English Learning Bot

echo "======================================"
echo "English Learning Bot - Quick Start"
echo "======================================"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✓ .env file created. Please edit it with your credentials:"
    echo "  nano .env"
    echo ""
    echo "Required values:"
    echo "  - TELEGRAM_BOT_TOKEN"
    echo "  - REQUIRED_CHANNEL_1"
    echo "  - REQUIRED_CHANNEL_2"
    echo "  - ADMIN_USER_IDS"
    echo "  - DATABASE_URL"
    echo "  - STRIPE_SECRET_KEY"
    echo "  - STRIPE_PUBLISHABLE_KEY"
    echo ""
    read -p "Press Enter after you've configured .env..."
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Check if database needs initialization
read -p "Initialize database? (y/n): " init_db
if [ "$init_db" = "y" ]; then
    echo "Initializing database..."
    python -m app.database.init_db
    echo "✓ Database initialized"
fi

# Check if Ollama is running
echo "Checking Ollama..."
if curl -s http://localhost:11434 > /dev/null 2>&1; then
    echo "✓ Ollama is running"
else
    echo "⚠️  Ollama is not running. Start it with: ollama serve"
fi

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To start the bot:"
echo "  1. Start FastAPI: uvicorn app.main:app --reload"
echo "  2. Start Bot: python run_bot.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose up -d"
echo ""
