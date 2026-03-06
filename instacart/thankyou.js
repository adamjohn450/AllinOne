document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session') || localStorage.getItem('instacart_session');
    
    // Log completion
    console.log('Account verification completed!', {
        sessionId: sessionId,
        timestamp: new Date().toISOString()
    });
    
    // Clear stored data
    setTimeout(() => {
        // Keep session for a bit, then clear
        localStorage.removeItem('instacart_contact');
        localStorage.removeItem('instacart_contact_type');
        localStorage.removeItem('instacart_card_last4');
        localStorage.setItem('instacart_verified', 'true');
    }, 2000);
    
    // Optional: Send completion event to backend
    if (sessionId) {
        fetch('/api/verification-complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session: sessionId,
                timestamp: Date.now()
            })
        }).catch(error => {
            console.log('Completion event error (expected in demo):', error);
        });
    }
});
