/**
 * logs.js — Logs panel for MATE.
 * Shows available session log files and allows downloading them.
 */
(function () {
  'use strict';

  let overlay;

  document.addEventListener('DOMContentLoaded', () => {
    overlay = document.getElementById('logs-overlay');

    document.getElementById('sidebar-link-logs')
      .addEventListener('click', (e) => { e.preventDefault(); openLogs(); });

    document.getElementById('logs-close')
      .addEventListener('click', closeLogs);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeLogs();
    });
  });

  async function openLogs() {
    overlay.classList.remove('hidden');
    await refreshLogsList();
  }

  function closeLogs() {
    overlay.classList.add('hidden');
  }

  async function refreshLogsList() {
    const listEl = document.getElementById('logs-list');
    listEl.innerHTML = '<div class="logs-loading">Loading...</div>';
    try {
      const res = await fetch('/api/logs');
      const files = await res.json();
      if (files.length === 0) {
        const settings = window.mateSettings || {};
        const loggingEnabled = settings.logging && settings.logging.enabled;
        listEl.innerHTML = loggingEnabled
          ? '<div class="logs-empty">No log files yet. Start a session to generate logs.</div>'
          : '<div class="logs-empty">File logging is disabled. Enable it in <a href="#" id="logs-goto-settings">Settings</a>.</div>';
        const link = document.getElementById('logs-goto-settings');
        if (link) {
          link.addEventListener('click', (e) => {
            e.preventDefault();
            closeLogs();
            if (typeof window.openSettings === 'function') window.openSettings();
          });
        }
        return;
      }
      listEl.innerHTML = '';
      files.forEach(f => {
        const row = document.createElement('div');
        row.className = 'log-row';
        const sizeKb = (f.size_bytes / 1024).toFixed(1);
        const date = new Date(f.modified).toLocaleString();
        row.innerHTML = `
          <span class="material-symbols-outlined log-icon">description</span>
          <div class="log-info">
            <span class="log-name">${f.filename}</span>
            <span class="log-meta">${date} &middot; ${sizeKb} KB</span>
          </div>
          <a class="log-download btn-secondary" href="/api/logs/${encodeURIComponent(f.filename)}" download="${f.filename}" title="Download">
            <span class="material-symbols-outlined">download</span>
          </a>
        `;
        listEl.appendChild(row);
      });
    } catch (e) {
      listEl.innerHTML = '<div class="logs-empty logs-error">Failed to load logs.</div>';
    }
  }

  window.openLogs = openLogs;
})();
