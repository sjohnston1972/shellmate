/**
 * terminal.js — xterm.js terminal initialisation for MATE.
 *
 * Each call to initTerminal() creates an independent xterm.js Terminal
 * instance, opens it in a new <div>, and connects it to the backend via
 * a WebSocket at /ws/terminal/{sessionId}.
 *
 * Terminal appearance is driven by settings loaded from /api/settings
 * (via settings.js).  When the user saves new settings, a
 * 'mate:settings-changed' event is fired and all open terminals are updated
 * live without requiring a page reload.
 *
 * Copy / paste behaviour:
 *   - Double-click on the terminal copies the current selection to clipboard.
 *   - Right-click on the terminal pastes from clipboard into the session
 *     (respects the right_click_paste setting).
 *
 * Inactive terminals are hidden with CSS (display:none on the container)
 * but the Terminal and WebSocket objects remain alive — so background
 * sessions continue to receive data and fill their buffers.
 */

(function () {
  'use strict';

  // Track all live terminal instances so we can update them when settings change
  // { sessionId: { terminal, fitAddon, websocket, containerId } }
  const _instances = {};

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  /**
   * Build xterm.js constructor options from the current settings.
   */
  function _buildOptions() {
    const s = (window.mateSettings || {}).terminal || {};
    const schemeName = ((window.mateSettings || {}).appearance || {}).color_scheme || 'deep_space';
    const schemeObj  = typeof window.getColorScheme === 'function'
      ? window.getColorScheme(schemeName)
      : null;
    const theme = schemeObj ? schemeObj.theme : _fallbackTheme();

    return {
      theme,
      fontFamily:       s.font_family      || "'JetBrains Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace",
      fontSize:         s.font_size        || 14,
      lineHeight:       s.line_height      || 1.2,
      cursorBlink:      s.cursor_blink     !== false,
      cursorStyle:      s.cursor_style     || 'block',
      scrollback:       s.scrollback_lines || 5000,
      allowProposedApi: true,
    };
  }

  /** Fallback theme used before settings.js has loaded. */
  function _fallbackTheme() {
    return {
      background:   '#0E0E0E',
      foreground:   '#E5E2E1',
      cursor:       '#C3C0FF',
      cursorAccent: '#0E0E0E',
    };
  }

  // -------------------------------------------------------------------------
  // initTerminal
  // -------------------------------------------------------------------------

  /**
   * Initialise a new xterm.js terminal and connect it to the backend.
   *
   * @param {string} sessionId - The UUID of the session this terminal belongs to.
   * @returns {{terminal: Terminal, fitAddon: FitAddon, websocket: WebSocket, containerId: string}}
   */
  function initTerminal(sessionId) {
    // ------------------------------------------------------------------
    // 1. Create the xterm.js Terminal instance with current settings
    // ------------------------------------------------------------------
    const terminal = new window.Terminal(_buildOptions());

    // ------------------------------------------------------------------
    // 2. Load addons
    // ------------------------------------------------------------------
    const fitAddon      = new window.FitAddon.FitAddon();
    const webLinksAddon = new window.WebLinksAddon.WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    // ------------------------------------------------------------------
    // 3. Create the container div and mount xterm.js
    // ------------------------------------------------------------------
    const containerId = `terminal-${sessionId}`;
    const container   = document.createElement('div');
    container.id        = containerId;
    container.className = 'terminal-container';

    document.getElementById('terminals-container').appendChild(container);

    terminal.open(container);

    // Fit after a brief paint delay so the container has real dimensions
    requestAnimationFrame(() => {
      try { fitAddon.fit(); } catch (_) {}
    });

    // ------------------------------------------------------------------
    // 4. Open WebSocket to the backend
    // ------------------------------------------------------------------
    const wsUrl    = `ws://${window.location.host}/ws/terminal/${sessionId}`;
    const websocket = new WebSocket(wsUrl);

    // ------------------------------------------------------------------
    // 5. Wire WebSocket → terminal (incoming data from device)
    // ------------------------------------------------------------------
    websocket.addEventListener('message', (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (_) {
        terminal.write(event.data);
        return;
      }

      switch (msg.type) {
        case 'output':
          terminal.write(msg.data);
          break;

        case 'hostname_detected':
          if (typeof window.updateTabLabel === 'function') {
            window.updateTabLabel(sessionId, msg.hostname);
          }
          if (typeof window.updateStatusBar === 'function') {
            window.updateStatusBar();
          }
          break;

        default:
          break;
      }
    });

    websocket.addEventListener('close', () => {
      if (typeof window.updateTabStatus === 'function') {
        window.updateTabStatus(sessionId, false);
      }
    });

    websocket.addEventListener('error', (err) => {
      console.error(`WebSocket error for session ${sessionId}:`, err);
    });

    // ------------------------------------------------------------------
    // 6. Wire terminal → WebSocket (outgoing keystrokes to device)
    // ------------------------------------------------------------------
    terminal.onData((data) => {
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // ------------------------------------------------------------------
    // 7. Copy / paste behaviour
    // ------------------------------------------------------------------

    // Double-click: copy selected text to clipboard.
    // xterm.js finishes its own word-selection logic asynchronously, so we
    // wait one tick before reading the selection.
    container.addEventListener('dblclick', () => {
      setTimeout(() => {
        const sel = terminal.getSelection();
        if (sel) {
          navigator.clipboard.writeText(sel).then(() => {
            window._showCopyToast && window._showCopyToast(sel);
          }).catch(() => {});
        }
      }, 50);
    });

    // Right-click: show paste confirmation modal before sending to session
    container.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const settings = window.mateSettings || {};
      if (settings.terminal && settings.terminal.right_click_paste === false) return;
      navigator.clipboard.readText().then(text => {
        if (!text) return;
        window._showPasteModal && window._showPasteModal(text, () => {
          if (websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({ type: 'input', data: text }));
          }
        });
      }).catch(() => {});
    });

    // ------------------------------------------------------------------
    // 8. Handle window resize — refit the active terminal
    // ------------------------------------------------------------------
    window.addEventListener('resize', () => {
      const containerEl = document.getElementById(containerId);
      if (containerEl && containerEl.classList.contains('active')) {
        try {
          fitAddon.fit();
          if (websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
              type: 'resize',
              cols: terminal.cols,
              rows: terminal.rows,
            }));
          }
        } catch (_) {}
      }
    });

    // Send initial resize once the socket is open
    websocket.addEventListener('open', () => {
      try {
        fitAddon.fit();
        websocket.send(JSON.stringify({
          type: 'resize',
          cols: terminal.cols,
          rows: terminal.rows,
        }));
      } catch (_) {}
    });

    // ------------------------------------------------------------------
    // 9. Register instance so settings changes can be applied live
    // ------------------------------------------------------------------
    _instances[sessionId] = { terminal, fitAddon, websocket, containerId };

    return { terminal, fitAddon, websocket, containerId };
  }

  // -------------------------------------------------------------------------
  // Live settings update — apply new settings to all open terminals
  // -------------------------------------------------------------------------

  window.addEventListener('mate:settings-changed', (e) => {
    const detail = e.detail || {};
    const s      = detail.terminal   || {};
    const a      = detail.appearance || {};

    const schemeObj = typeof window.getColorScheme === 'function'
      ? window.getColorScheme(a.color_scheme)
      : null;

    Object.values(_instances).forEach(({ terminal, fitAddon }) => {
      if (schemeObj) {
        terminal.options.theme = schemeObj.theme;
      }
      if (s.font_size)    terminal.options.fontSize    = s.font_size;
      if (s.font_family)  terminal.options.fontFamily   = s.font_family;
      if (s.line_height)  terminal.options.lineHeight   = s.line_height;
      if (s.cursor_style) terminal.options.cursorStyle  = s.cursor_style;
      terminal.options.cursorBlink = s.cursor_blink !== false;
      try { fitAddon.fit(); } catch (_) {}
    });
  });

  // -------------------------------------------------------------------------
  // Expose to global scope
  // -------------------------------------------------------------------------
  window.initTerminal = initTerminal;

})();
