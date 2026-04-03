/**
 * tabs.js — Tab bar management for MATE.
 *
 * Maintains an array of tab objects (one per session), handles creating,
 * switching and closing tabs, and updates the status bar.  The actual
 * xterm.js initialisation is delegated to terminal.js via initTerminal().
 *
 * Tab object structure:
 *   { sessionId, label, terminalInstance, fitAddon, websocket,
 *     isConnected, containerId }
 */

(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------

  /** @type {Array<Object>} All open tabs */
  const tabs = [];

  /** @type {number} Index of the currently visible tab (-1 = none) */
  let activeTabIndex = -1;

  // -------------------------------------------------------------------------
  // DOM references
  // -------------------------------------------------------------------------

  let tabList, welcomeScreen, terminalsContainer;

  document.addEventListener('DOMContentLoaded', () => {
    tabList            = document.getElementById('tab-list');
    welcomeScreen      = document.getElementById('welcome-screen');
    terminalsContainer = document.getElementById('terminals-container');

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboard);

    // Initial status bar
    updateStatusBar();
  });

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create a new tab for an established session.
   *
   * Called by connections.js after a successful POST /api/sessions.
   *
   * @param {Object} sessionData - Session metadata returned by the backend.
   *   Must include: session_id, display_label, hostname, connection_type,
   *   connected_at, is_connected.
   */
  function createTab(sessionData) {
    const { session_id, display_label, hostname } = sessionData;
    const label = display_label || hostname || session_id.slice(0, 8);

    // Build the tab DOM element
    const tabEl = document.createElement('div');
    tabEl.className = 'tab';
    tabEl.dataset.sessionId = session_id;

    const dot = document.createElement('span');
    dot.className = 'tab-dot';

    const labelEl = document.createElement('span');
    labelEl.className = 'tab-label';
    labelEl.textContent = label;
    labelEl.title = label;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'tab-close';
    closeBtn.textContent = '×';
    closeBtn.title = 'Close tab (Ctrl+W)';

    tabEl.appendChild(dot);
    tabEl.appendChild(labelEl);
    tabEl.appendChild(closeBtn);
    tabList.appendChild(tabEl);

    // Initialise terminal and WebSocket (defined in terminal.js)
    const termData = window.initTerminal(session_id);

    const tabObj = {
      sessionId:        session_id,
      label,
      terminalInstance: termData.terminal,
      fitAddon:         termData.fitAddon,
      websocket:        termData.websocket,
      isConnected:      true,
      containerId:      termData.containerId,
      tabEl,
      labelEl,
    };

    tabs.push(tabObj);
    const newIndex = tabs.length - 1;

    // Wire up click events
    tabEl.addEventListener('click', (e) => {
      if (e.target === closeBtn) return;  // handled below
      switchToTab(newIndex);
    });

    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Find current index at click time (array may have shifted)
      const idx = tabs.findIndex(t => t.sessionId === session_id);
      if (idx !== -1) closeTab(idx);
    });

    // Hide the welcome screen now that we have a tab
    welcomeScreen.classList.add('hidden');

    // Switch to the new tab
    switchToTab(newIndex);
  }

  /**
   * Switch the visible terminal to the tab at `index`.
   *
   * Hides all other terminal containers and marks the tab as active.
   *
   * @param {number} index
   */
  function switchToTab(index) {
    if (index < 0 || index >= tabs.length) return;

    // Deactivate all tabs and hide all terminals
    tabs.forEach((tab, i) => {
      tab.tabEl.classList.toggle('active', i === index);
      const container = document.getElementById(tab.containerId);
      if (container) {
        container.classList.toggle('active', i === index);
      }
    });

    activeTabIndex = index;

    // Let xterm.js recalculate dimensions after becoming visible
    const activeTab = tabs[index];
    if (activeTab && activeTab.fitAddon) {
      requestAnimationFrame(() => {
        try {
          activeTab.fitAddon.fit();
        } catch (_) { /* ignore if terminal not ready */ }
      });
    }

    updateStatusBar();
  }

  /**
   * Close the tab at `index`.
   *
   * Sends DELETE /api/sessions/{id}, closes the WebSocket, disposes the
   * xterm.js terminal, removes the DOM element, and switches to an adjacent
   * tab (or shows the welcome screen if none remain).
   *
   * @param {number} index
   */
  function closeTab(index) {
    if (index < 0 || index >= tabs.length) return;

    const tab = tabs[index];
    const { sessionId, websocket, terminalInstance, containerId, tabEl } = tab;

    // Tell the backend to tear down the session
    fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' }).catch(() => {
      // Best-effort — don't block UI on network error
    });

    // Close WebSocket
    try { websocket.close(); } catch (_) {}

    // Dispose terminal instance
    try { terminalInstance.dispose(); } catch (_) {}

    // Remove terminal container from DOM
    const container = document.getElementById(containerId);
    if (container) container.remove();

    // Remove tab DOM element
    tabEl.remove();

    // Remove from array
    tabs.splice(index, 1);

    // Decide what to show next
    if (tabs.length === 0) {
      activeTabIndex = -1;
      welcomeScreen.classList.remove('hidden');
    } else {
      // Switch to the tab to the left, or the first one
      const nextIndex = Math.min(index, tabs.length - 1);
      switchToTab(nextIndex);
    }

    updateStatusBar();
  }

  /**
   * Return the currently active tab object, or null.
   * @returns {Object|null}
   */
  function getActiveTab() {
    if (activeTabIndex < 0 || activeTabIndex >= tabs.length) return null;
    return tabs[activeTabIndex];
  }

  /**
   * Update a tab's label text.
   * @param {string} sessionId
   * @param {string} label
   */
  function updateTabLabel(sessionId, label) {
    const tab = tabs.find(t => t.sessionId === sessionId);
    if (!tab) return;
    tab.label = label;
    tab.labelEl.textContent = label;
    tab.labelEl.title = label;
    updateStatusBar();
  }

  /**
   * Mark a tab as connected or disconnected.
   * @param {string} sessionId
   * @param {boolean} isConnected
   */
  function updateTabStatus(sessionId, isConnected) {
    const tab = tabs.find(t => t.sessionId === sessionId);
    if (!tab) return;
    tab.isConnected = isConnected;
    tab.tabEl.classList.toggle('disconnected', !isConnected);
    if (!isConnected) {
      tab.labelEl.textContent = tab.label + ' (disconnected)';
    }
    updateStatusBar();
  }

  /**
   * Refresh the status bar with information about the active session.
   */
  function updateStatusBar() {
    const connEl   = document.getElementById('status-connection');
    const bufferEl = document.getElementById('status-buffer');
    const tabsEl   = document.getElementById('status-tabs');

    tabsEl.textContent = `Tabs: ${tabs.length}`;

    const active = getActiveTab();
    if (!active) {
      connEl.textContent  = 'No active session';
      bufferEl.textContent = 'Buffer: 0L';
      return;
    }

    const stateText = active.isConnected ? 'Connected' : 'Disconnected';
    connEl.textContent = `SSH: ${active.label} | ${stateText}`;

    // Buffer line count comes from the terminal's rows as a rough proxy;
    // accurate count will come from the backend in Phase 2
    bufferEl.textContent = 'Buffer: —';
  }

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  // -------------------------------------------------------------------------

  function handleKeyboard(e) {
    // Ctrl+T — new tab
    if (e.ctrlKey && e.key === 't') {
      e.preventDefault();
      if (typeof window.showConnectionDialog === 'function') {
        window.showConnectionDialog();
      }
      return;
    }

    // Ctrl+W — close active tab
    if (e.ctrlKey && e.key === 'w') {
      // Only intercept when a terminal is active (not when a form has focus)
      if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
      e.preventDefault();
      if (activeTabIndex >= 0) closeTab(activeTabIndex);
      return;
    }

    // Ctrl+1 through Ctrl+9 — switch to tab N
    if (e.ctrlKey && e.key >= '1' && e.key <= '9') {
      const targetIndex = parseInt(e.key, 10) - 1;
      if (targetIndex < tabs.length) {
        e.preventDefault();
        switchToTab(targetIndex);
      }
    }
  }

  // -------------------------------------------------------------------------
  // Expose to global scope
  // -------------------------------------------------------------------------

  window.createTab        = createTab;
  window.switchToTab      = switchToTab;
  window.closeTab         = closeTab;
  window.getActiveTab     = getActiveTab;
  window.updateTabLabel   = updateTabLabel;
  window.updateTabStatus  = updateTabStatus;
  window.updateStatusBar  = updateStatusBar;

})();
