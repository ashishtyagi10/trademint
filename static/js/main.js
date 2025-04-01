// Utility functions
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

function formatNumber(value) {
    if (!value) return '0';
    return new Intl.NumberFormat('en-US').format(value);
}

function formatDate(dateString) {
    if (!dateString) return '';
    return new Date(dateString).toLocaleString();
}

function getStatusColor(status) {
    const colors = {
        'OPEN': 'success',
        'PENDING': 'warning',
        'PARTIALLY_CLOSED': 'info',
        'CLOSED': 'secondary',
        'CANCELLED': 'danger'
    };
    return colors[status] || 'secondary';
}
