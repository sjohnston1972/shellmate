/**
 * connections.js — Connection dialog and profile management for MATE.
 *
 * Handles showing/hiding the modal, reading form fields, POSTing to
 * the backend to create a new session, and saving/loading connection profiles.
 * On connect success it calls createTab() (defined in tabs.js).
 */
(function () {
  'use strict';

  let overlay, form, errorBox, connectBtn, connectLabel, connectSpinner;
  let profilesList;

  document.addEventListener('DOMContentLoaded', () => {
    overlay         = document.getElementById('modal-overlay');
    form            = document.getElementById('connection-form');
    errorBox        = document.getElementById('form-error');
    connectBtn      = document.getElementById('btn-connect');
    connectLabel    = document.getElementById('btn-connect-label');
    connectSpinner  = document.getElementById('btn-connect-spinner');
    profilesList    = document.getElementById('saved-profiles-list');

    // Populate welcome screen quick-launch grid on startup
    renderWelcomeProfiles();

    document.getElementById('btn-new-tab')
      .addEventListener('click', showConnectionDialog);

    document.getElementById('btn-welcome-connect')
      .addEventListener('click', showConnectionDialog);

    document.getElementById('modal-close')
      .addEventListener('click', hideConnectionDialog);

    document.getElementById('btn-cancel')
      .addEventListener('click', hideConnectionDialog);

    document.getElementById('btn-save-profile')
      .addEventListener('click', handleSaveProfile);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) hideConnectionDialog();
    });

    form.addEventListener('submit', handleSubmit);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !overlay.classList.contains('hidden')) {
        hideConnectionDialog();
      }
    });
  });

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Show the connection modal, reset the form, and load saved profiles.
   */
  function showConnectionDialog(prefill) {
    clearError();
    form.reset();
    document.getElementById('field-port').value = '22';
    if (prefill) fillFromProfile(prefill);
    loadProfiles();
    overlay.classList.remove('hidden');
    // Focus password if prefilled (user only needs to enter password), else hostname
    setTimeout(() => {
      document.getElementById(prefill ? 'field-password' : 'field-hostname').focus();
    }, 50);
  }

  /**
   * Hide the connection modal and re-enable the Connect button.
   */
  function hideConnectionDialog() {
    overlay.classList.add('hidden');
    setLoading(false);
  }

  // -------------------------------------------------------------------------
  // Profiles
  // -------------------------------------------------------------------------

  async function loadProfiles() {
    if (!profilesList) return;
    try {
      const res = await fetch('/api/profiles');
      const profiles = await res.json();
      renderProfiles(profiles);
    } catch (e) {
      profilesList.innerHTML = '';
    }
  }

  async function renderWelcomeProfiles() {
    const grid = document.getElementById('welcome-profiles-grid');
    if (!grid) return;
    try {
      const res = await fetch('/api/profiles');
      const profiles = await res.json();
      grid.innerHTML = '';
      profiles.forEach(p => {
        const card = document.createElement('button');
        card.className = 'welcome-profile-card';
        card.title = `${p.hostname}:${p.port} (${p.connection_type.toUpperCase()})`;
        card.innerHTML = `
          <span class="material-symbols-outlined welcome-profile-icon">
            ${p.connection_type === 'serial' ? 'cable' : 'terminal'}
          </span>
          <span class="welcome-profile-name">${p.name}</span>
          <span class="welcome-profile-host">${p.hostname}</span>
        `;
        card.addEventListener('click', () => showConnectionDialog(p));
        grid.appendChild(card);
      });
    } catch (e) { /* silently skip if API unavailable */ }
  }

  function renderProfiles(profiles) {
    if (!profilesList) return;
    profilesList.innerHTML = '';
    if (profiles.length === 0) {
      profilesList.innerHTML = '<span class="profiles-empty">No saved connections</span>';
      return;
    }
    profiles.forEach(p => {
      const chip = document.createElement('div');
      chip.className = 'profile-chip';
      chip.innerHTML = `
        <span class="profile-chip-label" title="${p.hostname}:${p.port}">${p.name}</span>
        <button class="profile-chip-delete" data-id="${p.id}" title="Delete">x</button>
      `;
      chip.querySelector('.profile-chip-label').addEventListener('click', () => fillFromProfile(p));
      chip.querySelector('.profile-chip-delete').addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/api/profiles/${p.id}`, { method: 'DELETE' });
        await loadProfiles(); renderWelcomeProfiles();
      });
      profilesList.appendChild(chip);
    });
  }

  function fillFromProfile(p) {
    document.getElementById('field-label').value    = p.name || '';
    document.getElementById('field-hostname').value = p.hostname || '';
    document.getElementById('field-port').value     = p.port || 22;
    document.getElementById('field-username').value = p.username || '';
    document.getElementById('field-conntype').value = p.connection_type || 'ssh';
    document.getElementById('field-password').focus();
  }

  async function handleSaveProfile() {
    const hostname = document.getElementById('field-hostname').value.trim();
    const username = document.getElementById('field-username').value.trim();
    if (!hostname || !username) {
      showError('Fill in hostname and username to save a profile.');
      return;
    }
    const payload = {
      name:            document.getElementById('field-label').value.trim() || hostname,
      hostname,
      port:            parseInt(document.getElementById('field-port').value, 10) || 22,
      username,
      connection_type: document.getElementById('field-conntype').value,
    };
    try {
      await fetch('/api/profiles', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      await loadProfiles();
    } catch (e) {
      showError('Could not save profile.');
    }
  }

  // -------------------------------------------------------------------------
  // Form submission
  // -------------------------------------------------------------------------

  async function handleSubmit(e) {
    e.preventDefault();
    clearError();

    const hostname = document.getElementById('field-hostname').value.trim();
    const username = document.getElementById('field-username').value.trim();
    const password = document.getElementById('field-password').value;

    if (!hostname) { showError('Hostname is required.'); return; }
    if (!username) { showError('Username is required.'); return; }
    if (!password) { showError('Password is required.'); return; }

    const payload = {
      hostname,
      port:             parseInt(document.getElementById('field-port').value, 10) || 22,
      username,
      password,
      connection_type:  document.getElementById('field-conntype').value,
      display_label:    document.getElementById('field-label').value.trim(),
    };

    setLoading(true);

    try {
      const response = await fetch('/api/sessions', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Server error ${response.status}`);
      }

      hideConnectionDialog();
      if (typeof window.createTab === 'function') {
        window.createTab(data);
      } else {
        console.error('createTab() not found — is tabs.js loaded?');
      }

    } catch (err) {
      showError(err.message || 'Could not connect. Check host and credentials.');
      setLoading(false);
    }
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove('hidden');
  }

  function clearError() {
    errorBox.textContent = '';
    errorBox.classList.add('hidden');
  }

  function setLoading(loading) {
    connectBtn.disabled = loading;
    connectLabel.textContent = loading ? 'Connecting…' : 'Connect';
    connectSpinner.classList.toggle('hidden', !loading);
  }

  window.showConnectionDialog = showConnectionDialog;
  window.hideConnectionDialog = hideConnectionDialog;

})();
