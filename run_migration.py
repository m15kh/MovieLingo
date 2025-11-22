#!/usr/bin/env python3
"""
Script to run database migration for payment fields
"""
import asyncio
from sqlalchemy import text
from app.database.database import engine
from loguru import logger


async def run_migration():
    """Run the migration to add new payment fields"""

    logger.info("Starting database migration...")

    migration_sql = """
    -- Add new columns to payments table
    ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS payment_receipt_file_id VARCHAR,
    ADD COLUMN IF NOT EXISTS payment_method VARCHAR DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

    -- Update existing records to have payment_method = 'stripe' if they have a stripe_payment_id
    UPDATE payments
    SET payment_method = 'stripe'
    WHERE stripe_payment_id IS NOT NULL AND payment_method = 'manual';

    -- Create index on payment_method for better query performance
    CREATE INDEX IF NOT EXISTS idx_payments_payment_method ON payments(payment_method);
    """

    try:
        async with engine.begin() as conn:
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in migration_sql.split(';') if s.strip()]

            for statement in statements:
                logger.info(f"Executing: {statement[:50]}...")
                await conn.execute(text(statement))

            logger.success("✅ Migration completed successfully!")

            # Verify the changes
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'payments'
                ORDER BY ordinal_position;
            """))

            logger.info("\nPayments table structure:")
            for row in result:
                logger.info(f"  - {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
