/**
 * KAMI Effect SDK v1.0.0
 * Nintendo-inspired visual effects (DOM particle system).
 * Zero-dependency. Lightweight overlay effects on top of WebGPU canvas.
 *
 * Usage:
 *   KamiEffect.confetti(x, y);
 *   KamiEffect.sparkle(element);
 *   KamiEffect.ripple(x, y);
 *
 * @license MIT
 * @see https://kami.etzhayyim.com/effect-sdk
 */
(function(root) {
"use strict";

const PI = Math.PI, TAU = PI * 2;

// Nintendo pastel colors
const COLORS = ['#fa5757', '#33bfff', '#66e673', '#ffbf33', '#b366f2', '#26d9b3', '#ff8c4d', '#f272b3', '#5555ff', '#f5e642'];

function _rnd(a, b) { return a + Math.random() * (b - a); }
function _pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

let _container = null;
function _ensure() {
  if (_container) return _container;
  _container = document.createElement('div');
  _container.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;overflow:hidden;z-index:100';
  document.body.appendChild(_container);
  return _container;
}

// ━━━ Confetti ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Confetti burst — celebration particles (Mario star, Splatoon win).
 * @param {number} x - center X (screen px)
 * @param {number} y - center Y (screen px)
 * @param {object} opts - { count, spread, duration, colors }
 */
function confetti(x, y, opts) {
  opts = opts || {};
  const count = opts.count || 30;
  const spread = opts.spread || 200;
  const duration = opts.duration || 1200;
  const colors = opts.colors || COLORS;
  const c = _ensure();

  for (let i = 0; i < count; i++) {
    const el = document.createElement('div');
    const size = _rnd(4, 10);
    const color = _pick(colors);
    const angle = _rnd(0, TAU);
    const velocity = _rnd(spread * 0.3, spread);
    const rotation = _rnd(0, 720);
    const shape = Math.random() > 0.5 ? '2px' : '50%'; // square or circle

    el.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${size}px;height:${size * _rnd(0.5, 1.5)}px;background:${color};border-radius:${shape};pointer-events:none;z-index:100`;

    c.appendChild(el);

    const dx = Math.cos(angle) * velocity;
    const dy = Math.sin(angle) * velocity - spread * 0.5; // bias upward
    const startTime = performance.now();

    function animate() {
      const elapsed = performance.now() - startTime;
      const t = Math.min(elapsed / duration, 1);
      const ease = 1 - (1 - t) * (1 - t); // easeOut quad

      const px = x + dx * ease;
      const py = y + dy * ease + 400 * t * t; // gravity
      const rot = rotation * t;
      const opacity = t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3;

      el.style.transform = `translate(${px - x}px, ${py - y}px) rotate(${rot}deg)`;
      el.style.opacity = opacity;

      if (t < 1) requestAnimationFrame(animate);
      else el.remove();
    }
    requestAnimationFrame(animate);
  }
}

// ━━━ Sparkle ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Sparkle — twinkling stars around an element (Zelda fairy).
 * @param {HTMLElement} target
 * @param {object} opts - { count, duration, radius, colors }
 */
function sparkle(target, opts) {
  opts = opts || {};
  const count = opts.count || 8;
  const duration = opts.duration || 800;
  const radius = opts.radius || 30;
  const rect = target.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const c = _ensure();

  for (let i = 0; i < count; i++) {
    const el = document.createElement('div');
    const angle = (i / count) * TAU;
    const r = _rnd(radius * 0.5, radius);
    const size = _rnd(3, 7);

    el.style.cssText = `position:absolute;left:${cx}px;top:${cy}px;width:${size}px;height:${size}px;background:#fff;border-radius:50%;box-shadow:0 0 ${size}px #ffbf33, 0 0 ${size * 2}px #ffbf33;pointer-events:none`;

    c.appendChild(el);
    const delay = i * 30;
    const startTime = performance.now() + delay;

    function animate() {
      const elapsed = performance.now() - startTime;
      if (elapsed < 0) { requestAnimationFrame(animate); return; }
      const t = Math.min(elapsed / duration, 1);

      const scale = t < 0.3 ? t / 0.3 : t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3;
      const px = Math.cos(angle + t * PI) * r * (1 + t * 0.5);
      const py = Math.sin(angle + t * PI) * r * (1 + t * 0.5) - 10 * t;

      el.style.transform = `translate(${px}px, ${py}px) scale(${scale})`;
      el.style.opacity = scale;

      if (t < 1) requestAnimationFrame(animate);
      else el.remove();
    }
    requestAnimationFrame(animate);
  }
}

// ━━━ Ripple ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Ripple — expanding ring (Splatoon ink impact, touch feedback).
 * @param {number} x
 * @param {number} y
 * @param {object} opts - { color, size, duration }
 */
function ripple(x, y, opts) {
  opts = opts || {};
  const color = opts.color || '#33bfff';
  const maxSize = opts.size || 80;
  const duration = opts.duration || 500;
  const c = _ensure();

  const el = document.createElement('div');
  el.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:0;height:0;border:3px solid ${color};border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;opacity:0.8`;
  c.appendChild(el);

  const startTime = performance.now();
  function animate() {
    const t = Math.min((performance.now() - startTime) / duration, 1);
    const size = maxSize * (1 - (1 - t) ** 3); // easeOut
    el.style.width = size + 'px';
    el.style.height = size + 'px';
    el.style.opacity = (1 - t) * 0.8;
    el.style.borderWidth = Math.max(1, 3 * (1 - t)) + 'px';

    if (t < 1) requestAnimationFrame(animate);
    else el.remove();
  }
  requestAnimationFrame(animate);
}

// ━━━ Float Text ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Float text — rising text (damage numbers, "+1", score popup).
 * @param {string} text
 * @param {number} x
 * @param {number} y
 * @param {object} opts - { color, fontSize, duration }
 */
function floatText(text, x, y, opts) {
  opts = opts || {};
  const duration = opts.duration || 1000;
  const c = _ensure();

  const el = document.createElement('div');
  el.textContent = text;
  el.style.cssText = `position:absolute;left:${x}px;top:${y}px;font-family:'Nunito',system-ui;font-size:${opts.fontSize || 18}px;font-weight:900;color:${opts.color || '#ffbf33'};text-shadow:0 2px 4px rgba(0,0,0,0.2);pointer-events:none;white-space:nowrap;transform:translate(-50%,0)`;
  c.appendChild(el);

  const startTime = performance.now();
  function animate() {
    const t = Math.min((performance.now() - startTime) / duration, 1);
    const y_offset = -60 * (1 - (1 - t) ** 2); // easeOut rise
    const scale = t < 0.15 ? t / 0.15 * 1.2 : t < 0.3 ? 1.2 - 0.2 * (t - 0.15) / 0.15 : 1;
    const opacity = t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3;

    el.style.transform = `translate(-50%, ${y_offset}px) scale(${scale})`;
    el.style.opacity = opacity;

    if (t < 1) requestAnimationFrame(animate);
    else el.remove();
  }
  requestAnimationFrame(animate);
}

// ━━━ Trail ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Cursor trail — follow mouse with fading dots (Kirby star trail).
 * @param {object} opts - { color, size, count, decay }
 * @returns {{ destroy }}
 */
function trail(opts) {
  opts = opts || {};
  const color = opts.color || '#ffbf33';
  const size = opts.size || 8;
  const count = opts.count || 12;
  const decay = opts.decay || 0.9;
  const c = _ensure();

  const dots = [];
  for (let i = 0; i < count; i++) {
    const el = document.createElement('div');
    el.style.cssText = `position:absolute;width:${size}px;height:${size}px;background:${color};border-radius:50%;pointer-events:none;opacity:0;transition:none`;
    c.appendChild(el);
    dots.push({ el, x: 0, y: 0 });
  }

  let mx = 0, my = 0, running = true;
  function onMove(e) { mx = e.clientX; my = e.clientY; }
  document.addEventListener('mousemove', onMove);

  function animate() {
    if (!running) return;
    dots[0].x = mx; dots[0].y = my;
    for (let i = dots.length - 1; i > 0; i--) {
      dots[i].x += (dots[i - 1].x - dots[i].x) * (1 - decay);
      dots[i].y += (dots[i - 1].y - dots[i].y) * (1 - decay);
    }
    for (let i = 0; i < dots.length; i++) {
      const d = dots[i];
      const s = size * (1 - i / dots.length);
      d.el.style.left = (d.x - s / 2) + 'px';
      d.el.style.top = (d.y - s / 2) + 'px';
      d.el.style.width = s + 'px';
      d.el.style.height = s + 'px';
      d.el.style.opacity = (1 - i / dots.length) * 0.6;
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  return {
    destroy() {
      running = false;
      document.removeEventListener('mousemove', onMove);
      dots.forEach(d => d.el.remove());
    }
  };
}

// ━━━ Screen Flash ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Screen flash — full-screen color flash (damage, transition).
 * @param {object} opts - { color, duration }
 */
function flash(opts) {
  opts = opts || {};
  const c = _ensure();
  const el = document.createElement('div');
  el.style.cssText = `position:fixed;top:0;left:0;width:100%;height:100%;background:${opts.color || '#fff'};pointer-events:none;opacity:0.6;z-index:200`;
  c.appendChild(el);

  const duration = opts.duration || 200;
  const startTime = performance.now();
  function animate() {
    const t = Math.min((performance.now() - startTime) / duration, 1);
    el.style.opacity = 0.6 * (1 - t);
    if (t < 1) requestAnimationFrame(animate);
    else el.remove();
  }
  requestAnimationFrame(animate);
}

// ━━━ Public API ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

root.KamiEffect = {
  VERSION: '1.0.0',
  confetti,
  sparkle,
  ripple,
  floatText,
  trail,
  flash,
  COLORS,
};

})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
