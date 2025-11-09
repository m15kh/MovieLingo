import asyncio
from app.database.database import init_db


async def main():
    """Initialize the database"""
    print("🚀 Starting database initialization...")
    await init_db()
    print("✨ Database setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
