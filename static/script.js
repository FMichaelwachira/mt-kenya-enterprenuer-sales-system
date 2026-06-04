
// ── Show/Hide Password ─────────────────────────────────────
function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
}

// ── Tab Navigation ─────────────────────────────────────────
function showTab(tabName, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + tabName).classList.add('active');
    if (btn) btn.classList.add('active');
}

// ── Table Search Filter ────────────────────────────────────
function filterTable() {
    const input = document.getElementById('searchInput').value.toLowerCase();
    document.querySelectorAll('#salesTable tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(input) ? '' : 'none';
    });
}

// ── Add Seller ─────────────────────────────────────────────
function addSeller() {
    const username = document.getElementById('new_username').value.trim();
    const password = document.getElementById('new_password').value.trim();
    const role = document.getElementById('new_role').value;
    const alertDiv = document.getElementById('seller-alert');
    if (!username || !password) {
        showAlert(alertDiv, 'error', '⚠️ Please fill in both fields.');
        return;
    }
    fetch('/add_seller', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}&role=${encodeURIComponent(role)}`
    })
    .then(r => r.json())
    .then(data => {
        showAlert(alertDiv, data.success ? 'success' : 'error',
                  (data.success ? '✅ ' : '❌ ') + data.message);
        if (data.success) {
            document.getElementById('new_username').value = '';
            document.getElementById('new_password').value = '';
            setTimeout(() => location.reload(), 1500);
        }
    });
}

// ── Save Settings ──────────────────────────────────────────
function saveSettings() {
    const alertDiv = document.getElementById('settings-alert');
    const data = new URLSearchParams({
        business_name: document.getElementById('business_name').value,
        business_location: document.getElementById('business_location').value,
        business_currency: document.getElementById('business_currency').value,
        business_color: document.getElementById('business_color').value,
        owner_phone: document.getElementById('owner_phone').value,
        owner_email: document.getElementById('owner_email').value,
        at_username: document.getElementById('at_username').value,
        at_api_key: document.getElementById('at_api_key').value,
        gmail_address: document.getElementById('gmail_address').value,
        gmail_app_password: document.getElementById('gmail_app_password').value,
        low_stock_threshold: document.getElementById('low_stock_threshold').value,
        sms_enabled: document.getElementById('sms_enabled').checked ? '1' : '',
        email_enabled: document.getElementById('email_enabled').checked ? '1' : ''
    });
    fetch('/save_settings', {method:'POST', body:data})
    .then(r => r.json())
    .then(res => {
        showAlert(alertDiv, res.success ? 'success' : 'error',
                  res.success ? '✅ ' + res.message : '❌ ' + res.message);
    });
}

// ── Test SMS ───────────────────────────────────────────────
function testSMS() {
    const alertDiv = document.getElementById('settings-alert');
    showAlert(alertDiv, 'info', '📱 Sending test SMS...');
    fetch('/test_sms').then(r => r.json()).then(data => {
        showAlert(alertDiv, data.success ? 'success' : 'error',
                  data.success ? '✅ Test SMS sent!' : '❌ SMS failed. Check your credentials.');
    });
}

// ── Test Email ─────────────────────────────────────────────
function testEmail() {
    const alertDiv = document.getElementById('settings-alert');
    showAlert(alertDiv, 'info', '📧 Sending test email...');
    fetch('/test_email').then(r => r.json()).then(data => {
        showAlert(alertDiv, data.success ? 'success' : 'error',
                  data.success ? '✅ Test email sent!' : '❌ Email failed: ' + data.error);
    });
}

// ── Show Alert Helper ──────────────────────────────────────
function showAlert(div, type, message) {
    if (!div) return;
    div.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    setTimeout(() => { if (div) div.innerHTML = ''; }, 5000);
}

// ── Auto dismiss alerts ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s ease';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });
});
