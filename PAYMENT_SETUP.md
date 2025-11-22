# Manual Payment Setup Guide

## Overview
The bot now supports manual payment verification where users can pay via bank card transfer and submit a receipt for admin approval.

## Configuration

### 1. Update your `.env` file

Add the following bank details to your `.env` file:

```env
# Bank Card Details for Manual Payments
BANK_CARD_NUMBER=1234 5678 9012 3456
BANK_CARD_HOLDER=Your Name
BANK_NAME=Your Bank Name
```

Replace the values with your actual bank card information.

## How It Works

### For Users:

1. User selects "Pay with Card Transfer" option
2. Bot displays your bank card details
3. User makes the payment and takes a screenshot of the receipt
4. User sends the screenshot to the bot
5. Bot confirms receipt and notifies user that admin will review
6. User receives notification when admin approves/rejects

### For Admins:

1. Admin receives immediate notification when user submits payment receipt
2. Notification includes:
   - User information
   - Payment amount
   - Payment receipt image
   - Approve/Reject buttons
3. Admin can:
   - Click "✅ Approve" to activate the user
   - Click "❌ Reject" to deny the payment
4. User is automatically notified of the decision

## Admin Commands

- `/admin_panel` - Open admin panel
- Select "💳 Pending Payments" to see all pending manual payments
- Click "👁️ Review Receipt" to view the payment screenshot

## Database Migration

The following fields were added to the `Payment` model:
- `payment_receipt_file_id` - Stores Telegram file_id of receipt image
- `payment_method` - Either "stripe" or "manual"
- `rejection_reason` - Stores reason if payment is rejected

**Run the database migration:**

```bash
# Activate your conda environment
source ~/miniconda3/bin/activate fu

# Run the migration script
python run_migration.py
```

✅ **Migration completed successfully!** The new columns have been added to the `payments` table.

## Features Implemented

✅ Manual payment option with bank card details
✅ Photo receipt upload from users
✅ Instant admin notification with receipt image
✅ Approve/Reject functionality for admins
✅ Automatic user activation on approval
✅ User notifications for approval/rejection
✅ Payment history tracking
✅ Support for both Stripe and manual payments

## Testing

1. Start the bot: `python run_bot.py`
2. Test as a regular user:
   - Send `/start` to the bot
   - Share phone number
   - Select "💳 Pay with Card Transfer"
   - Send a test image as receipt
3. Test as admin:
   - Check that you receive the notification
   - Try approving/rejecting the payment

## Security Notes

- Payment receipts are stored as Telegram file_ids (not downloaded locally)
- Only users in `ADMIN_USER_IDS` can approve/reject payments
- All payment actions are logged with admin ID and timestamp
