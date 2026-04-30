/**
 * jira.js — Conclude Session / Jira integration for ShellMate.
 *
 * Two modes:
 *   "new"      — create a brand-new Jira issue with the session data
 *   "existing" — search for a ticket and append the session as a comment
 *
 * Public API:
 *   window.openJiraModal()              — open the modal (called from chat.js /jira command)
 *   window.addJiraChatMessage(role,txt) — record a message into the chat history
 *   window.getJiraChatHistory()         — return a copy of the history array
 */
(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // Chat history — populated by chat.js via addJiraChatMessage()
  // -------------------------------------------------------------------------
  const chatHistory = [];

  window.addJiraChatMessage = (role, text) => chatHistory.push({ role, text });
  window.getJiraChatHistory = () => chatHistory.slice();

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  let mode             = 'new';       // 'new' | 'existing'
  let selectedTicket   = null;        // {key, summary} when in existing mode
  let searchDebounce   = null;
  let jiraConfigured   = false;
  let jiraProjectKey   = '';
  let jiraUrl          = '';

  // -------------------------------------------------------------------------
  // DOM refs (populated on DOMContentLoaded)
  // -------------------------------------------------------------------------
  let overlay, summaryInput, descriptionInput, issueTypeSelect,
      projectBadge, tabsSummaryEl, errorEl, successEl,
      submitBtn, submitLabel, submitSpinner,
      modeBtnNew, modeBtnExisting,
      newFields, searchFields,
      searchInput, searchBtn, searchResultsEl,
      selectedTicketEl, selectedKeyEl, selectedSummaryEl, clearSelectionBtn;

  document.addEventListener('DOMContentLoaded', async () => {
    overlay            = document.getElementById('jira-overlay');
    summaryInput       = document.getElementById('jira-summary');
    descriptionInput   = document.getElementById('jira-description');
    issueTypeSelect    = document.getElementById('jira-issue-type');
    projectBadge       = document.getElementById('jira-project-badge');
    tabsSummaryEl      = document.getElementById('jira-tabs-summary');
    errorEl            = document.getElementById('jira-error');
    successEl          = document.getElementById('jira-success');
    submitBtn          = document.getElementById('jira-submit');
    submitLabel        = document.getElementById('jira-submit-label');
    submitSpinner      = document.getElementById('jira-submit-spinner');
    modeBtnNew         = document.getElementById('jira-mode-new');
    modeBtnExisting    = document.getElementById('jira-mode-existing');
    newFields          = document.getElementById('jira-new-fields');
    searchFields       = document.getElementById('jira-search-fields');
    searchInput        = document.getElementById('jira-search-input');
    searchBtn          = document.getElementById('jira-search-btn');
    searchResultsEl    = document.getElementById('jira-search-results');
    selectedTicketEl   = document.getElementById('jira-selected-ticket');
    selectedKeyEl      = document.getElementById('jira-selected-key');
    selectedSummaryEl  = document.getElementById('jira-selected-summary');
    clearSelectionBtn  = document.getElementById('jira-clear-selection');

    // Button wiring
    document.getElementById('btn-conclude-session').addEventListener('click', openJiraModal);
    document.getElementById('jira-close').addEventListener('click', closeJiraModal);
    document.getElementById('jira-cancel').addEventListener('click', closeJiraModal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeJiraModal(); });
    submitBtn.addEventListener('click', submitToJira);
    modeBtnNew.addEventListener('click', () => setMode('new'));
    modeBtnExisting.addEventListener('click', () => setMode('existing'));
    searchBtn.addEventListener('click', runSearch);
    searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runSearch(); });
    searchInput.addEventListener('input', () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(runSearch, 400);
    });
    clearSelectionBtn.addEventListener('click', clearSelection);

    // Load Jira config
    try {
      const r   = await fetch('/api/jira/config');
      const cfg = await r.json();
      jiraConfigured = cfg.configured;
      jiraProjectKey = cfg.project_key || '';
      jiraUrl        = cfg.jira_url    || '';
      if (projectBadge) projectBadge.textContent = jiraProjectKey || '—';

      if (jiraConfigured) {
        const tr = await fetch('/api/jira/issue-types');
        if (tr.ok) {
          const types = await tr.json();
          if (types.length) {
            issueTypeSelect.innerHTML = types
              .map(t => `<option value="${esc(t)}"${t === 'Task' ? ' selected' : ''}>${esc(t)}</option>`)
              .join('');
          }
        }
      }
    } catch (_) {}
  });

  // -------------------------------------------------------------------------
  // Mode switching
  // -------------------------------------------------------------------------

  function setMode(m) {
    mode = m;
    modeBtnNew.classList.toggle('active', m === 'new');
    modeBtnExisting.classList.toggle('active', m === 'existing');
    newFields.classList.toggle('hidden', m !== 'new');
    searchFields.classList.toggle('hidden', m !== 'existing');
    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');
    _updateSubmitButton();

    if (m === 'existing') {
      setTimeout(() => { searchInput.focus(); runSearch(); }, 50);
    }
  }

  // -------------------------------------------------------------------------
  // Search
  // -------------------------------------------------------------------------

  async function runSearch() {
    const q = searchInput.value.trim();

    searchResultsEl.innerHTML = '<div class="jira-search-loading"><span class="jira-spinner-sm"></span> Searching…</div>';
    searchResultsEl.classList.remove('hidden');

    try {
      const r = await fetch(`/api/jira/search?q=${encodeURIComponent(q)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const issues = await r.json();
      renderSearchResults(issues);
    } catch (e) {
      searchResultsEl.innerHTML = `<div class="jira-search-error">Search failed: ${esc(e.message)}</div>`;
    }
  }

  function renderSearchResults(issues) {
    if (!issues.length) {
      searchResultsEl.innerHTML = '<div class="jira-search-empty">No tickets found.</div>';
      return;
    }

    searchResultsEl.innerHTML = issues.map(issue => `
      <button class="jira-result-item" data-key="${esc(issue.key)}" data-summary="${esc(issue.summary)}">
        <span class="jira-result-key">${esc(issue.key)}</span>
        <span class="jira-result-summary">${esc(issue.summary)}</span>
        <span class="jira-result-status">${esc(issue.status)}</span>
      </button>
    `).join('');

    searchResultsEl.querySelectorAll('.jira-result-item').forEach(btn => {
      btn.addEventListener('click', () => {
        selectTicket(btn.dataset.key, btn.dataset.summary);
      });
    });
  }

  function selectTicket(key, summary) {
    selectedTicket = { key, summary };
    selectedKeyEl.textContent     = key;
    selectedSummaryEl.textContent = summary;
    selectedTicketEl.classList.remove('hidden');
    searchResultsEl.classList.add('hidden');
    searchInput.value = '';
    _updateSubmitButton();
    errorEl.classList.add('hidden');
  }

  function clearSelection() {
    selectedTicket = null;
    selectedTicketEl.classList.add('hidden');
    _updateSubmitButton();
  }

  // -------------------------------------------------------------------------
  // Open / close
  // -------------------------------------------------------------------------

  function openJiraModal() {
    // Pre-fill title
    const activeTab = typeof window.getActiveTab === 'function' ? window.getActiveTab() : null;
    const label     = activeTab ? activeTab.label : '';
    const today     = new Date().toISOString().slice(0, 10);
    summaryInput.value     = label ? `${label} — session ${today}` : `ShellMate session ${today}`;
    descriptionInput.value = '';

    // Reset to new-ticket mode
    setMode('new');
    clearSelection();
    searchInput.value = '';
    searchResultsEl.classList.add('hidden');
    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');
    _setLoading(false);

    _renderTabsSummary();

    submitBtn.disabled = !jiraConfigured;
    if (!jiraConfigured) {
      _showError('Jira is not configured. Add JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY to your .env file.');
    }

    overlay.classList.remove('hidden');
    setTimeout(() => summaryInput.select(), 50);
  }

  function closeJiraModal() {
    overlay.classList.add('hidden');
  }

  window.openJiraModal = openJiraModal;

  // -------------------------------------------------------------------------
  // Submit
  // -------------------------------------------------------------------------

  async function submitToJira() {
    if (!jiraConfigured) return;

    if (mode === 'existing' && !selectedTicket) {
      _showError('Search for a ticket and select it before submitting.');
      searchInput.focus();
      return;
    }

    if (mode === 'new' && !summaryInput.value.trim()) {
      _showError('Please enter a ticket title.');
      summaryInput.focus();
      return;
    }

    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');
    _setLoading(true);

    const openIds = typeof window.getOpenSessionIds === 'function'
      ? window.getOpenSessionIds() : [];

    const payload = {
      summary:          summaryInput.value.trim(),
      description:      descriptionInput.value.trim(),
      issue_type:       issueTypeSelect.value,
      open_session_ids: openIds,
      chat_messages:    chatHistory,
    };

    if (mode === 'existing' && selectedTicket) {
      payload.existing_issue_key = selectedTicket.key;
    }

    try {
      const resp = await fetch('/api/jira/session', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      _setLoading(false);

      const verb = data.mode === 'comment' ? 'Added to' : 'Created';
      _showSuccess(verb, data.issue_key, data.url);

    } catch (e) {
      _setLoading(false);
      _showError(`Failed: ${e.message}`);
    }
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  function _updateSubmitButton() {
    if (!jiraConfigured) { submitBtn.disabled = true; return; }
    if (mode === 'existing') {
      submitLabel.textContent = selectedTicket
        ? `Add to ${selectedTicket.key}`
        : 'Add to existing ticket';
      submitBtn.disabled = !selectedTicket;
    } else {
      submitLabel.textContent = 'Send to Jira';
      submitBtn.disabled = false;
    }
  }

  function _renderTabsSummary() {
    if (!tabsSummaryEl) return;
    const ids = typeof window.getOpenSessionIds === 'function'
      ? window.getOpenSessionIds() : [];

    if (!ids.length) {
      tabsSummaryEl.innerHTML = '<p class="jira-tabs-none">No active terminal sessions — chat history only will be included.</p>';
      return;
    }

    const pills = ids.map((_, i) => {
      const t     = typeof window.getTabByNumber === 'function' ? window.getTabByNumber(i + 1) : null;
      const label = t ? (t.label || `Tab ${i + 1}`) : `Tab ${i + 1}`;
      return `<span class="jira-tab-pill"><span class="material-symbols-outlined">terminal</span>${esc(label)}</span>`;
    }).join('');

    tabsSummaryEl.innerHTML = `
      <p class="jira-tabs-label">Terminal sessions to include:</p>
      <div class="jira-tab-pills">${pills}</div>`;
  }

  function _setLoading(loading) {
    submitBtn.disabled = loading;
    if (!loading) _updateSubmitButton();
    else submitLabel.textContent = mode === 'existing' ? 'Sending…' : 'Creating…';
    submitSpinner.classList.toggle('hidden', !loading);
  }

  function _showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.remove('hidden');
  }

  function _showSuccess(verb, issueKey, url) {
    successEl.innerHTML = `
      <span class="material-symbols-outlined">check_circle</span>
      ${esc(verb)} <a href="${esc(url)}" target="_blank" rel="noopener">${esc(issueKey)}</a>
      — <a href="${esc(url)}" target="_blank" rel="noopener">Open in Jira ↗</a>`;
    successEl.classList.remove('hidden');
    submitBtn.disabled = true;
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

})();
