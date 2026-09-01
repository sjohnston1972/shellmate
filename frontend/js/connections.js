/**
 * connections.js — Connection dialog and profile management for ShellMate.
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

    document.getElementById('field-conntype')
      .addEventListener('change', (e) => {
        updateFieldsForType(e.target.value);
        if (e.target.value === 'serial') loadSerialPorts();
      });

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
    updateFieldsForType(document.getElementById('field-conntype').value);
    loadProfiles();
    overlay.classList.remove('hidden');
    if (document.getElementById('field-conntype').value === 'serial') {
      loadSerialPorts();
    }
    // Focus password if prefilled (user only needs to enter password), else
    // hostname — or the serial port field when connection type is serial.
    setTimeout(() => {
      const type = document.getElementById('field-conntype').value;
      const focusId = type === 'serial'
        ? 'field-serial-port'
        : (prefill ? 'field-password' : 'field-hostname');
      const el = document.getElementById(focusId);
      if (el) el.focus();
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
        const wrap = document.createElement('div');
        wrap.className = 'welcome-profile-wrap';

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
        card.addEventListener('click', () => openProfile(p));

        const del = document.createElement('button');
        del.className = 'welcome-profile-delete';
        del.title = 'Remove';
        del.innerHTML = '<span class="material-symbols-outlined">close</span>';
        del.addEventListener('click', async (e) => {
          e.stopPropagation();
          await fetch(`/api/profiles/${p.id}`, { method: 'DELETE' });
          renderWelcomeProfiles();
        });

        wrap.appendChild(card);
        wrap.appendChild(del);
        grid.appendChild(wrap);
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

  /**
   * Click handler for a saved-device tile.
   *
   * If a tab is already open for this profile (matched on hostname+port+username),
   * switch to that tab. Otherwise open the connection dialog pre-filled.
   */
  async function openProfile(p) {
    try {
      const openIds = (typeof window.getOpenSessionIds === 'function')
        ? window.getOpenSessionIds() : [];
      if (openIds.length) {
        const r = await fetch('/api/sessions');
        if (r.ok) {
          const sessions = await r.json();
          const openSet  = new Set(openIds);
          const match = sessions.find(s =>
            openSet.has(s.session_id) &&
            s.hostname === p.hostname &&
            (s.port || 22) === (p.port || 22) &&
            s.username === p.username
          );
          if (match && typeof window.switchToTabBySessionId === 'function') {
            window.switchToTabBySessionId(match.session_id);
            return;
          }
        }
      }
    } catch (_) { /* fall through to dialog */ }

    showConnectionDialog(p);
  }

  function fillFromProfile(p) {
    document.getElementById('field-label').value    = p.name || '';
    document.getElementById('field-conntype').value = p.connection_type || 'ssh';

    if (p.connection_type === 'serial') {
      // Serial profiles reuse the generic hostname/port profile fields:
      // hostname holds the port string (e.g. "COM3"), port holds the baud rate.
      document.getElementById('field-serial-port').value = p.hostname || '';
      document.getElementById('field-baud').value = String(p.port || 9600);
    } else {
      document.getElementById('field-hostname').value = p.hostname || '';
      document.getElementById('field-port').value     = p.port || 22;
      document.getElementById('field-username').value = p.username || '';
    }

    updateFieldsForType(p.connection_type || 'ssh');
    if (p.connection_type === 'serial') {
      loadSerialPorts();
    } else {
      document.getElementById('field-password').focus();
    }
  }

  /**
   * Show/hide the SSH-only vs serial-only field groups in the connection
   * dialog based on the selected connection type.
   */
  function updateFieldsForType(connType) {
    const isSerial = connType === 'serial';
    document.getElementById('ssh-fields').classList.toggle('hidden', isSerial);
    document.getElementById('serial-fields').classList.toggle('hidden', !isSerial);
  }

  /**
   * Populate the serial port datalist from GET /api/serial/ports.
   * Best-effort — the port field remains a free-text input if this fails
   * or returns nothing, so users can always type a port manually.
   */
  async function loadSerialPorts() {
    const datalist = document.getElementById('serial-ports-datalist');
    if (!datalist) return;
    try {
      const res = await fetch('/api/serial/ports');
      if (!res.ok) return;
      const ports = await res.json();
      datalist.innerHTML = '';
      ports.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.device;
        opt.label = p.description ? `${p.device} — ${p.description}` : p.device;
        datalist.appendChild(opt);
      });
    } catch (e) { /* silently fall back to free text */ }
  }

  async function handleSaveProfile() {
    const connType = document.getElementById('field-conntype').value;
    let payload;

    if (connType === 'serial') {
      const serialPort = document.getElementById('field-serial-port').value.trim();
      if (!serialPort) {
        showError('Fill in a serial port to save a profile.');
        return;
      }
      payload = {
        name:            document.getElementById('field-label').value.trim() || serialPort,
        hostname:        serialPort,
        port:            parseInt(document.getElementById('field-baud').value, 10) || 9600,
        username:        '',
        connection_type: 'serial',
      };
    } else {
      const hostname = document.getElementById('field-hostname').value.trim();
      const username = document.getElementById('field-username').value.trim();
      if (!hostname || !username) {
        showError('Fill in hostname and username to save a profile.');
        return;
      }
      payload = {
        name:            document.getElementById('field-label').value.trim() || hostname,
        hostname,
        port:            parseInt(document.getElementById('field-port').value, 10) || 22,
        username,
        connection_type: 'ssh',
      };
    }

    try {
      await fetch('/api/profiles', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      await loadProfiles();
      if (typeof window.renderWelcomeProfiles === 'function') {
        window.renderWelcomeProfiles();
      }
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

    const connType = document.getElementById('field-conntype').value;
    let payload;

    if (connType === 'serial') {
      const serialPort = document.getElementById('field-serial-port').value.trim();
      if (!serialPort) { showError('Serial port is required.'); return; }

      payload = {
        connection_type: 'serial',
        serial_port:     serialPort,
        baud_rate:       parseInt(document.getElementById('field-baud').value, 10) || 9600,
        display_label:   document.getElementById('field-label').value.trim(),
      };
    } else {
      const hostname = document.getElementById('field-hostname').value.trim();
      const username = document.getElementById('field-username').value.trim();
      const password = document.getElementById('field-password').value;

      if (!hostname) { showError('Hostname is required.'); return; }
      if (!username) { showError('Username is required.'); return; }
      if (!password) { showError('Password is required.'); return; }

      payload = {
        hostname,
        port:             parseInt(document.getElementById('field-port').value, 10) || 22,
        username,
        password,
        connection_type:  'ssh',
        display_label:    document.getElementById('field-label').value.trim(),
      };
    }

    setLoading(true);
    await attemptConnect(payload);
  }

  /**
   * POST /api/sessions and handle the result, including the
   * trust-on-first-use (TOFU) host-key approval flow (issue #12):
   * a 409 with `needs_host_key_approval` means the server's SSH host key
   * isn't recognised yet. We show the fingerprint, and only on explicit
   * user acceptance do we call POST /api/host-keys to remember it, then
   * retry the connection. Declining aborts cleanly with no session created
   * and no key stored.
   */
  async function attemptConnect(payload) {
    try {
      const data = await postCreateSession(payload);
      await onConnectSuccess(data, payload);
    } catch (err) {
      if (err && err.hostKeyApproval) {
        const hk = err.hostKeyApproval;
        const accepted = window.confirm(
          `Unrecognised SSH host key for ${hk.hostname}\n\n` +
          `${hk.key_type} ${hk.fingerprint}\n\n` +
          `Only accept this if you expect it (e.g. this is the first time ` +
          `connecting to this device). If you weren't expecting a new key, ` +
          `click Cancel — this could indicate someone is intercepting the ` +
          `connection.\n\nAccept and remember this key?`
        );
        if (!accepted) {
          showError('Connection cancelled — host key was not accepted.');
          setLoading(false);
          return;
        }
        try {
          await approveHostKey(hk);
        } catch (approveErr) {
          showError(approveErr.message || 'Could not store the approved host key.');
          setLoading(false);
          return;
        }
        // Key is now trusted — retry the same connection.
        await attemptConnect(payload);
        return;
      }
      showError(err.message || 'Could not connect. Check host and credentials.');
      setLoading(false);
    }
  }

  /**
   * POST /api/sessions. Resolves with the session dict on success. On a
   * 409 host-key-approval response, rejects with an Error carrying a
   * `hostKeyApproval` property (the fingerprint payload) instead of a
   * generic message, so callers can branch on it. Any other non-OK
   * response rejects with a plain Error.
   */
  async function postCreateSession(payload) {
    const response = await fetch('/api/sessions', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      if (response.status === 409 && data && data.detail && data.detail.needs_host_key_approval) {
        const err = new Error(data.detail.message || 'Unrecognised SSH host key.');
        err.hostKeyApproval = data.detail;
        throw err;
      }
      throw new Error((data && data.detail) || `Server error ${response.status}`);
    }
    return data;
  }

  /** POST /api/host-keys to persist a user-approved fingerprint. */
  async function approveHostKey(hk) {
    const res = await fetch('/api/host-keys', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        hostname:   hk.hostname,
        key_type:   hk.key_type,
        key_base64: hk.key_base64,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || 'Could not store the approved host key.');
    }
    return data;
  }

  /** Shared success path for a newly created session (initial or post-approval retry). */
  async function onConnectSuccess(data, payload) {
    hideConnectionDialog();
    if (typeof window.createTab === 'function') {
      window.createTab(data);
    } else {
      console.error('createTab() not found — is tabs.js loaded?');
    }

    // Auto-save profile (no password) so it persists across refreshes.
    // Skip if a matching profile already exists. Serial profiles reuse
    // the generic hostname/port profile fields (hostname = port string,
    // port = baud rate) the same way session metadata does.
    try {
      const r = await fetch('/api/profiles');
      const existing = r.ok ? await r.json() : [];

      const profilePayload = payload.connection_type === 'serial'
        ? {
            name:            payload.display_label || payload.serial_port,
            hostname:        payload.serial_port,
            port:            payload.baud_rate,
            username:        '',
            connection_type: 'serial',
          }
        : {
            name:            payload.display_label || payload.hostname,
            hostname:        payload.hostname,
            port:            payload.port,
            username:        payload.username,
            connection_type: 'ssh',
          };

      const dup = existing.some(p =>
        p.connection_type === profilePayload.connection_type &&
        p.hostname === profilePayload.hostname &&
        p.username === profilePayload.username &&
        (p.port || 0) === (profilePayload.port || 0)
      );
      if (!dup) {
        await fetch('/api/profiles', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(profilePayload),
        });
        // Refresh both the in-dialog list and the welcome-screen grid so
        // the new profile is visible without a page reload.
        await loadProfiles();
        if (typeof window.renderWelcomeProfiles === 'function') {
          window.renderWelcomeProfiles();
        }
      }
    } catch (_) { /* non-fatal */ }
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

  window.showConnectionDialog  = showConnectionDialog;
  window.hideConnectionDialog  = hideConnectionDialog;
  window.renderWelcomeProfiles = renderWelcomeProfiles;

})();
