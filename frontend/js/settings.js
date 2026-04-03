/**
 * settings.js — Settings panel for MATE.
 * Manages the settings overlay panel, loads/saves settings via the API,
 * and notifies other modules when settings change.
 */
(function () {
  'use strict';

  let panel, overlay;
  let currentSettings = {};

  // Color scheme definitions (xterm.js theme objects)
  const COLOR_SCHEMES = {
    deep_space: {
      label: 'Deep Space (Default)',
      theme: {
        background:    '#0E0E0E',
        foreground:    '#E5E2E1',
        cursor:        '#C3C0FF',
        cursorAccent:  '#0E0E0E',
        black:         '#2A2A2A',
        red:           '#FFB4AB',
        green:         '#B7C8E1',
        yellow:        '#F9E2AF',
        blue:          '#C3C0FF',
        magenta:       '#CBA6F7',
        cyan:          '#89DCEB',
        white:         '#E5E2E1',
        brightBlack:   '#353535',
        brightRed:     '#FFB4AB',
        brightGreen:   '#B7C8E1',
        brightYellow:  '#F9E2AF',
        brightBlue:    '#C3C0FF',
        brightMagenta: '#CBA6F7',
        brightCyan:    '#89DCEB',
        brightWhite:   '#FFFFFF',
      },
    },
    solarized_dark: {
      label: 'Solarized Dark',
      theme: {
        background:    '#002B36',
        foreground:    '#839496',
        cursor:        '#839496',
        cursorAccent:  '#002B36',
        black:         '#073642',
        red:           '#DC322F',
        green:         '#859900',
        yellow:        '#B58900',
        blue:          '#268BD2',
        magenta:       '#D33682',
        cyan:          '#2AA198',
        white:         '#EEE8D5',
        brightBlack:   '#002B36',
        brightRed:     '#CB4B16',
        brightGreen:   '#586E75',
        brightYellow:  '#657B83',
        brightBlue:    '#839496',
        brightMagenta: '#6C71C4',
        brightCyan:    '#93A1A1',
        brightWhite:   '#FDF6E3',
      },
    },
    nord: {
      label: 'Nord',
      theme: {
        background:    '#2E3440',
        foreground:    '#D8DEE9',
        cursor:        '#D8DEE9',
        cursorAccent:  '#2E3440',
        black:         '#3B4252',
        red:           '#BF616A',
        green:         '#A3BE8C',
        yellow:        '#EBCB8B',
        blue:          '#81A1C1',
        magenta:       '#B48EAD',
        cyan:          '#88C0D0',
        white:         '#E5E9F0',
        brightBlack:   '#4C566A',
        brightRed:     '#BF616A',
        brightGreen:   '#A3BE8C',
        brightYellow:  '#EBCB8B',
        brightBlue:    '#81A1C1',
        brightMagenta: '#B48EAD',
        brightCyan:    '#8FBCBB',
        brightWhite:   '#ECEFF4',
      },
    },
    one_dark: {
      label: 'One Dark',
      theme: {
        background:    '#282C34',
        foreground:    '#ABB2BF',
        cursor:        '#528BFF',
        cursorAccent:  '#282C34',
        black:         '#3F4451',
        red:           '#E06C75',
        green:         '#98C379',
        yellow:        '#E5C07B',
        blue:          '#61AFEF',
        magenta:       '#C678DD',
        cyan:          '#56B6C2',
        white:         '#ABB2BF',
        brightBlack:   '#4F5666',
        brightRed:     '#BE5046',
        brightGreen:   '#98C379',
        brightYellow:  '#E5C07B',
        brightBlue:    '#61AFEF',
        brightMagenta: '#C678DD',
        brightCyan:    '#56B6C2',
        brightWhite:   '#FFFFFF',
      },
    },
  };

  document.addEventListener('DOMContentLoaded', () => {
    panel   = document.getElementById('settings-panel');
    overlay = document.getElementById('settings-overlay');

    document.getElementById('sidebar-link-settings')
      .addEventListener('click', (e) => { e.preventDefault(); openSettings(); });

    document.getElementById('settings-close')
      .addEventListener('click', closeSettings);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeSettings();
    });

    document.getElementById('settings-save')
      .addEventListener('click', saveSettings);

    // Load settings on startup so terminals start with correct config
    loadSettings();
  });

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      currentSettings = await res.json();
      window.mateSettings = currentSettings;
    } catch (e) {
      console.warn('Could not load settings:', e);
    }
  }

  function openSettings() {
    populateForm(currentSettings);
    overlay.classList.remove('hidden');
  }

  function closeSettings() {
    overlay.classList.add('hidden');
  }

  function populateForm(s) {
    const t = s.terminal   || {};
    const l = s.logging    || {};
    const a = s.appearance || {};

    _val('setting-font-family',      t.font_family      || 'JetBrains Mono, monospace');
    _val('setting-font-size',        t.font_size        || 14);
    _val('setting-line-height',      t.line_height      || 1.2);
    _val('setting-cursor-style',     t.cursor_style     || 'block');
    _val('setting-scrollback',       t.scrollback_lines || 5000);
    _checked('setting-cursor-blink',      t.cursor_blink      !== false);
    _checked('setting-right-click-paste', t.right_click_paste !== false);
    _checked('setting-copy-on-select',    !!t.copy_on_select);
    _checked('setting-logging-enabled',   !!l.enabled);
    _val('setting-log-dir',          l.directory || 'logs');
    _val('setting-color-scheme',     a.color_scheme || 'deep_space');
  }

  async function saveSettings() {
    const s = {
      terminal: {
        font_family:       _gval('setting-font-family'),
        font_size:         parseInt(_gval('setting-font-size'), 10),
        line_height:       parseFloat(_gval('setting-line-height')),
        cursor_style:      _gval('setting-cursor-style'),
        cursor_blink:      _gchecked('setting-cursor-blink'),
        scrollback_lines:  parseInt(_gval('setting-scrollback'), 10),
        right_click_paste: _gchecked('setting-right-click-paste'),
        copy_on_select:    _gchecked('setting-copy-on-select'),
      },
      logging: {
        enabled:   _gchecked('setting-logging-enabled'),
        directory: _gval('setting-log-dir'),
      },
      appearance: {
        color_scheme: _gval('setting-color-scheme'),
      },
    };

    try {
      const res = await fetch('/api/settings', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ settings: s }),
      });
      currentSettings = await res.json();
      window.mateSettings = currentSettings;
      // Notify terminal.js to apply new settings
      window.dispatchEvent(new CustomEvent('mate:settings-changed', { detail: currentSettings }));
      closeSettings();
    } catch (e) {
      console.error('Failed to save settings:', e);
    }
  }

  function _val(id, v)     { const el = document.getElementById(id); if (el) el.value = v; }
  function _checked(id, v) { const el = document.getElementById(id); if (el) el.checked = !!v; }
  function _gval(id)       { const el = document.getElementById(id); return el ? el.value : ''; }
  function _gchecked(id)   { const el = document.getElementById(id); return el ? el.checked : false; }

  // Public API
  window.getColorScheme     = (name) => COLOR_SCHEMES[name] || COLOR_SCHEMES.deep_space;
  window.getAllColorSchemes  = () => COLOR_SCHEMES;
  window.openSettings       = openSettings;

})();
