const detectedBasePath = /^\/hangman(?:\/|$)/.test(window.location.pathname || '')
    ? '/hangman'
    : '';

window.APP_BASE_PATH = window.APP_BASE_PATH || detectedBasePath;

function apiUrl(path) {
    return (window.APP_BASE_PATH || '') + path;
}

const themesList = document.getElementById('themes-list');
const themesForm = document.getElementById('themes-form');
const adminMessage = document.getElementById('admin-message');

function renderMessage(text, isError) {
    adminMessage.textContent = text;
    adminMessage.className = isError ? 'admin-message error' : 'admin-message success';
}

function renderThemes(themes) {
    if (!themes.length) {
        themesList.innerHTML = '<p>No themes found.</p>';
        return;
    }

    themesList.innerHTML = themes.map((theme) => {
        const checked = theme.is_active ? 'checked' : '';
        const badge = theme.is_active ? '<span class="active-badge">Active</span>' : '';
        return `
            <label class="theme-option">
                <input type="radio" name="theme_id" value="${theme.id}" ${checked}>
                <span>${theme.name}</span>
                ${badge}
            </label>
        `;
    }).join('');
}

async function loadThemes() {
    const response = await fetch(apiUrl('/api/admin/themes'), { credentials: 'same-origin' });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || 'Failed to load themes');
    }
    renderThemes(payload.themes || []);
}

themesForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const selected = themesForm.querySelector('input[name="theme_id"]:checked');
    if (!selected) {
        renderMessage('Please select a theme.', true);
        return;
    }

    const response = await fetch(apiUrl('/api/admin/themes/select'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ theme_id: Number(selected.value) }),
    });
    const payload = await response.json();
    if (!response.ok) {
        renderMessage(payload.error || 'Failed to apply theme', true);
        return;
    }

    renderMessage('Active theme updated.', false);
    await loadThemes();
});

loadThemes().catch((error) => {
    renderMessage(error.message || 'Failed to load themes', true);
});
