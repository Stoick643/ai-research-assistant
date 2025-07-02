// Main JavaScript for AI Research Assistant

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize form validation
    initializeFormValidation();
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            var closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        });
    }, 5000);
}

function initializeFormValidation() {
    // Research form validation
    const researchForm = document.getElementById('research-form');
    if (researchForm) {
        researchForm.addEventListener('submit', function(event) {
            const topic = document.getElementById('topic').value.trim();
            
            if (topic.length < 10) {
                event.preventDefault();
                showAlert('Please enter a research topic with at least 10 characters.', 'error');
                return false;
            }
            
            if (topic.length > 1000) {
                event.preventDefault();
                showAlert('Research topic cannot exceed 1000 characters.', 'error');
                return false;
            }
            
            // Show loading state
            const submitButton = researchForm.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting Research...';
                submitButton.disabled = true;
            }
            
            return true;
        });
    }
}

function showAlert(message, type = 'info') {
    const alertContainer = document.querySelector('main .container');
    if (!alertContainer) return;
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        <i class="bi bi-${type === 'error' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.insertBefore(alertDiv, alertContainer.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(function() {
        const closeButton = alertDiv.querySelector('.btn-close');
        if (closeButton) {
            closeButton.click();
        }
    }, 5000);
}

// Utility functions for API calls
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Progress tracking utilities
function startProgressTracking(researchId, callback) {
    const interval = setInterval(async function() {
        try {
            const data = await apiCall(`/api/research/status/${researchId}`);
            callback(data);
            
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(interval);
            }
        } catch (error) {
            console.error('Progress tracking error:', error);
            clearInterval(interval);
        }
    }, 3000); // Check every 3 seconds
    
    return interval;
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Form utilities
function toggleSection(buttonId, sectionId) {
    const button = document.getElementById(buttonId);
    const section = document.getElementById(sectionId);
    
    if (button && section) {
        button.addEventListener('click', function() {
            section.classList.toggle('d-none');
            const icon = button.querySelector('i');
            if (icon) {
                icon.classList.toggle('bi-chevron-down');
                icon.classList.toggle('bi-chevron-up');
            }
        });
    }
}

// Language selection utilities
function updateLanguageFlags() {
    const languageSelects = document.querySelectorAll('select[name*="language"]');
    languageSelects.forEach(function(select) {
        select.addEventListener('change', function() {
            // Could add flag icons here
            console.log('Language changed to:', this.value);
        });
    });
}

// Copy to clipboard utility
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showAlert('Copied to clipboard!', 'success');
    }).catch(function(err) {
        console.error('Failed to copy: ', err);
        showAlert('Failed to copy to clipboard', 'error');
    });
}

// Download utilities
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Loading state utilities
function setLoadingState(element, loading = true) {
    if (!element) return;
    
    if (loading) {
        element.classList.add('loading');
        element.style.pointerEvents = 'none';
    } else {
        element.classList.remove('loading');
        element.style.pointerEvents = 'auto';
    }
}

// Statistics dashboard utilities
function loadDashboardStats() {
    apiCall('/api/stats/dashboard')
        .then(data => {
            updateStatsDisplay(data);
        })
        .catch(error => {
            console.error('Failed to load dashboard stats:', error);
        });
}

function updateStatsDisplay(data) {
    const elements = {
        'total-research': data.totals?.total_research || 0,
        'completed-research': data.totals?.completed_research || 0,
        'success-rate': (data.totals?.success_rate || 0) + '%',
        'recent-activity': data.recent_activity || 0
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
}

// Initialize dashboard if on home page
if (window.location.pathname === '/') {
    loadDashboardStats();
}