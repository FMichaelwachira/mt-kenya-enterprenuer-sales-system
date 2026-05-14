// ── Tab Navigation ────────────────────────────────────────────
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + tabName).classList.add('active');
    event.target.classList.add('active');
}

// ── Table Search Filter ───────────────────────────────────────
function filterTable() {
    const input = document.getElementById('searchInput').value.toLowerCase();
    const rows = document.querySelectorAll('#salesTable tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(input) ? '' : 'none';
    });
}

// ── Add Seller ────────────────────────────────────────────────
function addSeller() {
    const username = document.getElementById('new_username').value.trim();
    const password = document.getElementById('new_password').value.trim();
    const alertDiv = document.getElementById('seller-alert');

    if (!username || !password) {
        showAlert(alertDiv, 'error', '⚠️ Please fill in both fields.');
        return;
    }

    fetch('/add_seller', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showAlert(alertDiv, 'success', '✅ ' + data.message);
            document.getElementById('new_username').value = '';
            document.getElementById('new_password').value = '';
            setTimeout(() => location.reload(), 1500);
        } else {
            showAlert(alertDiv, 'error', '❌ ' + data.message);
        }
    });
}

// ── Save Settings ─────────────────────────────────────────────
function saveSettings() {
    const alertDiv = document.getElementById('settings-alert');
    const data = new URLSearchParams({
        owner_phone: document.getElementById('owner_phone').value,
        owner_email: document.getElementById('owner_email').value,
        at_username: document.getElementById('at_username').value,
        at_api_key: document.getElementById('at_api_key').value,
        gmail_address: document.getElementById('gmail_address').value,
        gmail_app_password: document.getElementById('gmail_app_password').value,
        sms_enabled: document.getElementById('sms_enabled').checked ? '1' : '',
        email_enabled: document.getElementById('email_enabled').checked ? '1' : ''
    });

    fetch('/save_settings', {method: 'POST', body: data})
    .then(r => r.json())
    .then(res => {
        showAlert(alertDiv, res.success ? 'success' : 'error',
                  res.success ? '✅ ' + res.message : '❌ ' + res.message);
    });
}

// ── Test SMS ──────────────────────────────────────────────────
function testSMS() {
    const alertDiv = document.getElementById('settings-alert');
    showAlert(alertDiv, 'info', '📱 Sending test SMS...');
    fetch('/test_sms')
    .then(r => r.json())
    .then(data => {
        showAlert(alertDiv, data.success ? 'success' : 'error',
                  data.success ? '✅ Test SMS sent!' : '❌ SMS failed. Check your credentials.');
    });
}

// ── Test Email ────────────────────────────────────────────────
function testEmail() {
    const alertDiv = document.getElementById('settings-alert');
    showAlert(alertDiv, 'info', '📧 Sending test email...');
    fetch('/test_email')
    .then(r => r.json())
    .then(data => {
        showAlert(alertDiv, data.success ? 'success' : 'error',
                  data.success ? '✅ Test email sent!' : '❌ Email failed: ' + data.error);
    });
}

// ── Daily Summary ─────────────────────────────────────────────
function sendDailySummary() {
    const alertDiv = document.getElementById('summary-alert');
    showAlert(alertDiv, 'info', '📤 Sending summary...');
    fetch('/send_daily_summary')
    .then(r => r.json())
    .then(data => {
        showAlert(alertDiv, data.success ? 'success' : 'error',
                  data.success ? '✅ Daily summary sent!' : '❌ Failed to send summary.');
    });
}

// ── Show Alert Helper ─────────────────────────────────────────
function showAlert(div, type, message) {
    if (!div) return;
    div.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    setTimeout(() => { if (div) div.innerHTML = ''; }, 5000);
}

// ── Auto-dismiss alerts ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s ease';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });
});
