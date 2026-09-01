/*
 * command-safety.js — dangerous-command classifier + confirmation modal.
 *
 * Owns the "suggest-and-approve" safety gate for AI command blocks
 * (see GitHub issues #6 and #7). Two independent pieces live here:
 *
 *   1. classifyCommand(cmd) — pure function, no DOM. Returns
 *      { dangerous: boolean, reason: string }. Exposed on window (browser)
 *      and via module.exports (so it can be unit-tested under plain Node
 *      — see command-safety.test.js).
 *
 *   2. A confirmation modal, wired the same way as the existing paste
 *      modal (#paste-overlay) in index.html: window.showCommandConfirm(cmd,
 *      reason, deviceLabel, onConfirm) shows it and invokes onConfirm only
 *      if the user explicitly clicks "Run anyway". The markup lives in its
 *      own section of index.html (#cmd-confirm-overlay), separate from the
 *      connection dialog so the two stay out of each other's way.
 *
 * chat.js calls classifyCommand() + showCommandConfirm() from
 * injectCommand() before anything is written to the terminal — see
 * frontend/js/chat.js.
 */
(function (root) {
  'use strict';

  // Rules are matched against the start of the (trimmed, whitespace-
  // collapsed, case-insensitive) command so that things like
  // "show reload" or "show running-config" are never mistaken for the
  // destructive commands they merely mention. First match wins.
  const DANGER_RULES = [
    {
      pattern: /^reload\b/i,
      reason: 'Reboots the device'
    },
    {
      pattern: /^(write\s+erase|wr\s+erase|erase\s+(startup-config|nvram:))/i,
      reason: 'Erases the startup configuration'
    },
    {
      pattern: /^no\s+shutdown\b/i,
      reason: 'Brings an interface up — can black-hole traffic or cause a loop if applied to the wrong port'
    },
    {
      pattern: /^shutdown\b/i,
      reason: 'Disables the interface'
    },
    {
      pattern: /^clear\b/i,
      reason: 'Clears device counters, sessions, or logs — cannot be undone'
    },
    {
      pattern: /^delete\b/i,
      reason: 'Deletes a file from device storage'
    },
    {
      pattern: /^format\b/i,
      reason: 'Formats device storage — erases all files'
    },
    {
      // "copy running-config startup-config" is a routine save and is safe.
      // "copy <anything else> startup-config" overwrites the startup config
      // from an external/remote source and is not.
      pattern: /^copy\s+(?!running-config\b)\S+\s+(startup-config|nvram:)\b/i,
      reason: 'Overwrites the startup configuration from an external source'
    },
    {
      pattern: /^boot\s+system\b/i,
      reason: 'Changes the boot image used on the next reload'
    },
    {
      pattern: /^config-register\b/i,
      reason: 'Changes the configuration register — affects boot behaviour'
    }
  ];

  function classifyCommand(cmd) {
    const normalized = String(cmd == null ? '' : cmd)
      .trim()
      .replace(/\s+/g, ' ');

    for (let i = 0; i < DANGER_RULES.length; i++) {
      if (DANGER_RULES[i].pattern.test(normalized)) {
        return { dangerous: true, reason: DANGER_RULES[i].reason };
      }
    }
    return { dangerous: false, reason: '' };
  }

  // -------------------------------------------------------------------
  // 2. Confirmation modal (browser only — no-op if there is no DOM)
  // -------------------------------------------------------------------

  function initModal() {
    const overlay   = document.getElementById('cmd-confirm-overlay');
    const preview   = document.getElementById('cmd-confirm-preview');
    const reasonEl  = document.getElementById('cmd-confirm-reason');
    const targetEl  = document.getElementById('cmd-confirm-target');
    const btnRun    = document.getElementById('cmd-confirm-run');
    const btnCancel = document.getElementById('cmd-confirm-cancel');

    if (!overlay || !preview || !btnRun || !btnCancel) {
      // Modal markup not present (e.g. this page doesn't include it) —
      // leave window.showCommandConfirm undefined so callers can detect
      // it and fail closed instead of silently sending.
      return;
    }

    let _pendingCb = null;

    function show(cmd, reason, deviceLabel, onConfirm) {
      preview.textContent = cmd;
      if (reasonEl) reasonEl.textContent = reason || 'This command changes device state.';
      if (targetEl) targetEl.textContent = deviceLabel ? `Target: ${deviceLabel}` : '';
      _pendingCb = onConfirm;
      overlay.classList.remove('hidden');
      btnCancel.focus();
    }

    function hide() {
      overlay.classList.add('hidden');
      _pendingCb = null;
    }

    btnRun.addEventListener('click', () => {
      const cb = _pendingCb;
      hide();
      if (cb) cb();
    });

    btnCancel.addEventListener('click', hide);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) hide();
    });

    document.addEventListener('keydown', (e) => {
      if (overlay.classList.contains('hidden')) return;
      if (e.key === 'Escape') hide();
      // Deliberately no Enter-to-confirm here — unlike the paste modal,
      // this gate is protecting destructive commands and should require
      // an explicit pointer click on "Run anyway".
    });

    root.showCommandConfirm = show;
  }

  root.classifyCommand = classifyCommand;

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initModal);
    } else {
      initModal();
    }
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { classifyCommand };
  }
})(typeof window !== 'undefined' ? window : globalThis);
