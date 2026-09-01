/*
 * command-safety.js — dangerous-command classifier for AI command blocks.
 *
 * Owns the classification half of the "suggest-and-approve" safety gate
 * (see GitHub issue #6). classifyCommand(cmd) is a pure function, no DOM:
 * it returns { dangerous: boolean, reason: string }. Exposed on window
 * (browser) and via module.exports (so it can be unit-tested under plain
 * Node — see command-safety.test.js).
 *
 * The confirmation modal that consumes this (issue #7) is added to this
 * same file in a later change; chat.js's injectCommand() is the call site.
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

  root.classifyCommand = classifyCommand;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { classifyCommand };
  }
})(typeof window !== 'undefined' ? window : globalThis);
