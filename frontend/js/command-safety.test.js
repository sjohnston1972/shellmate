/*
 * command-safety.test.js — unit tests for classifyCommand() (issue #6).
 *
 * There is no JS test framework configured in this repo (no package.json,
 * no bundled test runner). This is a plain Node script with zero
 * dependencies so it can run as-is: `node frontend/js/command-safety.test.js`.
 * It exits non-zero on any failure so it can be wired into CI later without
 * changes.
 */
'use strict';

const assert = require('assert');
const { classifyCommand } = require('./command-safety.js');

let passed = 0;
let failed = 0;

function dangerous(cmd) {
  try {
    const result = classifyCommand(cmd);
    assert.strictEqual(result.dangerous, true, `expected dangerous:true for ${JSON.stringify(cmd)}`);
    assert.ok(result.reason && result.reason.length > 0, `expected non-empty reason for ${JSON.stringify(cmd)}`);
    console.log(`  PASS  dangerous: ${JSON.stringify(cmd)} -> ${result.reason}`);
    passed++;
  } catch (e) {
    console.log(`  FAIL  dangerous: ${JSON.stringify(cmd)} -> ${e.message}`);
    failed++;
  }
}

function safe(cmd) {
  try {
    const result = classifyCommand(cmd);
    assert.strictEqual(result.dangerous, false, `expected dangerous:false for ${JSON.stringify(cmd)}, got reason "${result.reason}"`);
    console.log(`  PASS  safe: ${JSON.stringify(cmd)}`);
    passed++;
  } catch (e) {
    console.log(`  FAIL  safe: ${JSON.stringify(cmd)} -> ${e.message}`);
    failed++;
  }
}

console.log('-- Dangerous commands (must be flagged) --');
dangerous('reload');
dangerous('reload in 5');
dangerous('reload at 23:00');
dangerous('write erase');
dangerous('wr erase');
dangerous('erase startup-config');
dangerous('erase nvram:');
dangerous('shutdown');
dangerous('no shutdown');
dangerous('clear counters');
dangerous('clear logging');
dangerous('delete flash:');
dangerous('delete flash:old-image.bin');
dangerous('format flash:');
dangerous('copy tftp: startup-config');
dangerous('copy ftp://server/config startup-config');
dangerous('boot system flash:new-image.bin');
dangerous('config-register 0x2142');
// Whitespace / case-insensitivity
dangerous('  RELOAD  ');
dangerous('Write Erase');
dangerous('  reload   in   5  ');

console.log('\n-- Safe / read-only commands (must NOT be flagged) --');
safe('show ip interface brief');
safe('show running-config');
safe('show reload');
safe('show reload-reason');
safe('show version');
safe('show clock');
safe('show interfaces status');
safe('copy running-config startup-config');
safe('ping 8.8.8.8');
safe('traceroute 10.0.0.1');
safe('  show ip route  ');
safe('SHOW VERSION');

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
