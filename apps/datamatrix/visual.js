'use strict';

// ── Per-medication visual identity ──────────────────────────────────────────────
// Each product (GTIN) gets a distinctive colour and shape so boxes of the same
// medication are easy to associate at a glance. Auto-derived deterministically
// from the GTIN, but a product can override either (stored in dm_products).

const PALETTE = [
  '#1273b8', '#c23a3a', '#1f9d62', '#7c3aed', '#b26a00', '#0a9d8e', '#d81b60',
  '#3949ab', '#00897b', '#6d4c41', '#e53935', '#43a047', '#8e24aa', '#f4511e',
  '#039be5', '#5e35b1',
];
const SHAPES = ['circle', 'square', 'triangle', 'diamond', 'hexagon', 'star', 'pentagon', 'cross'];

function hash(s) {
  let h = 2166136261;
  const str = String(s || '');
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return Math.abs(h);
}

function autoColor(gtin) { return PALETTE[hash('c' + gtin) % PALETTE.length]; }
function autoShape(gtin) { return SHAPES[hash('s' + gtin) % SHAPES.length]; }

const HEX = /^#[0-9a-fA-F]{6}$/;
function resolveColor(gtin, override) { return HEX.test(String(override || '')) ? override : autoColor(gtin); }
function resolveShape(gtin, override) { return SHAPES.includes(override) ? override : autoShape(gtin); }

module.exports = { PALETTE, SHAPES, autoColor, autoShape, resolveColor, resolveShape };
