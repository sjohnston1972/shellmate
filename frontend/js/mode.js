/**
 * mode.js — Learn / Troubleshoot mode toggle.
 *
 * The mode controls which AI persona is activated by the backend:
 *   - "tshoot" (default): terse senior engineer focused on fixing the problem.
 *   - "learn": patient mentor who explains the why before suggesting a command.
 *
 * The active mode is persisted to localStorage and also sent to the backend
 * with every chat message (via chat.js). A chat-header pill mirrors the
 * welcome-screen toggle so the user can flip modes mid-session.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'shellmate:mode';
  const VALID_MODES = ['tshoot', 'learn'];

  let _currentMode = _readStored();

  function _readStored() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      return VALID_MODES.includes(v) ? v : 'tshoot';
    } catch (_) {
      return 'tshoot';
    }
  }

  function getMode() { return _currentMode; }

  function setMode(mode) {
    if (!VALID_MODES.includes(mode)) return;
    _currentMode = mode;
    try { localStorage.setItem(STORAGE_KEY, mode); } catch (_) {}
    _refreshUI();
    window.dispatchEvent(new CustomEvent('shellmate:mode-changed', { detail: { mode } }));
  }

  const LABELS = { tshoot: 'Tshoot', learn: 'Learn' };

  function _refreshUI() {
    const btn  = document.getElementById('mode-toggle-btn');
    const text = document.getElementById('mode-toggle-text');
    if (btn)  btn.dataset.mode = _currentMode;
    if (text) text.textContent = LABELS[_currentMode] || LABELS.tshoot;
    if (btn) {
      const next = _currentMode === 'tshoot' ? 'Learn' : 'Troubleshoot';
      btn.title = `Active mode: ${LABELS[_currentMode]}. Click to switch to ${next}.`;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('mode-toggle-btn');
    if (btn) {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        setMode(_currentMode === 'tshoot' ? 'learn' : 'tshoot');
      });
    }

    _refreshUI();
  });

  // Public API used by chat.js
  window.getShellmateMode = getMode;
  window.setShellmateMode = setMode;
})();
