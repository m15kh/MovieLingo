-- Migration: Add manual payment fields to payments table
-- Date: 2025-11-22

-- Add new columns to payments table
ALTER TABLE payments
ADD COLUMN IF NOT EXISTS payment_receipt_file_id VARCHAR,
ADD COLUMN IF NOT EXISTS payment_method VARCHAR DEFAULT 'manual',
ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Update existing records to have payment_method = 'stripe' if they have a stripe_payment_id
UPDATE payments
SET payment_method = 'stripe'
WHERE stripe_payment_id IS NOT NULL AND payment_method IS NULL;

-- Create index on payment_method for better query performance
CREATE INDEX IF NOT EXISTS idx_payments_payment_method ON payments(payment_method);

-- Verify the changes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'payments'
ORDER BY ordinal_position;
