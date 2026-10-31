/**
 * KAMI Motion SDK v1.0.0
 * Nintendo-inspired animation primitives for kami-engine UI.
 * Zero-dependency. Easing, spring physics, stagger, and transition helpers.
 *
 * Usage:
 *   KamiMotion.spring(el, { scale: [0, 1], y: [20, 0] }, { stiffness: 300 });
 *   KamiMotion.fadeIn(el);
 *   KamiMotion.stagger('.card', { y: [30, 0], opacity: [0, 1] }, { delay: 60 });
 *
 * @license MIT
 * @see https://kami.etzhayyim.com/motion-sdk
 */
(function(root) {
"use strict";

const PI = Math.PI;
const raf = requestAnimationFrame.bind(window);
const now = () => performance.now();

// ━━━ Easing ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const ease = {
  // Nintendo-style: bouncy, snappy, playful
  linear: t => t,
  easeOut: t => 1 - (1 - t) ** 3,              // cubic out (smooth decel)
  easeIn: t => t ** 3,                           // cubic in
  easeInOut: t => t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2,
  bounce: t => {                                  // Mario coin bounce
    if (t < 0.3636) return 7.5625 * t * t;
    if (t < 0.7272) return 7.5625 * (t -= 0.5454) * t + 0.75;
    if (t < 0.9090) return 7.5625 * (t -= 0.8181) * t + 0.9375;
    return 7.5625 * (t -= 0.9545) * t + 0.984375;
  },
  elastic: t => {                                 // Splatoon splat
    if (t === 0 || t === 1) return t;
    return -(2 ** (10 * t - 10)) * Math.sin((t * 10 - 10.75) * (2 * PI / 3));
  },
  back: t => {                                    // overshoot snap
    const c = 1.70158;
    return (c + 1) * t ** 3 - c * t ** 2;
  },
  backOut: t => {
    const c = 1.70158;
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2;
  },
  pop: t => {                                     // Nintendo switch pop
    if (t < 0.4) return ease.easeOut(t / 0.4) * 1.1;
    if (t < 0.7) return 1.1 - 0.1 * ease.easeInOut((t - 0.4) / 0.3);
    return 1.0;
  },
};

// ━━━ Tween ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Animate numeric properties over time.
 * @param {object} opts - { from, to, duration, easing, onUpdate, onComplete }
 * @returns {{ cancel }}
 */
function tween(opts) {
  const from = opts.from || 0;
  const to = opts.to !== undefined ? opts.to : 1;
  const duration = opts.duration || 300;
  const easeFn = (typeof opts.easing === 'function') ? opts.easing : (ease[opts.easing] || ease.easeOut);
  const onUpdate = opts.onUpdate || (() => {});
  const onComplete = opts.onComplete || (() => {});
  const start = now();
  let cancelled = false;

  function tick() {
    if (cancelled) return;
    const elapsed = now() - start;
    const t = Math.min(elapsed / duration, 1);
    const v = from + (to - from) * easeFn(t);
    onUpdate(v, t);
    if (t < 1) raf(tick);
    else onComplete();
  }
  raf(tick);

  return { cancel() { cancelled = true; } };
}

// ━━━ Spring ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Spring physics animation (Nintendo bouncy feel).
 * @param {HTMLElement} el
 * @param {object} props - { scale: [from, to], x: [from, to], y: [from, to], opacity: [from, to], rotate: [from, to] }
 * @param {object} opts - { stiffness, damping, mass, onComplete }
 * @returns {{ cancel }}
 */
function spring(el, props, opts) {
  opts = opts || {};
  const stiffness = opts.stiffness || 200;
  const damping = opts.damping || 15;
  const mass = opts.mass || 1;
  const onComplete = opts.onComplete || (() => {});

  // State per property
  const state = {};
  for (const key in props) {
    const [from, to] = Array.isArray(props[key]) ? props[key] : [null, props[key]];
    state[key] = { pos: from !== null ? from : _getCurrentValue(el, key), vel: 0, target: to };
  }

  let cancelled = false;
  let lastTime = now();

  function tick() {
    if (cancelled) return;
    const t = now();
    const dt = Math.min((t - lastTime) / 1000, 0.064); // cap at ~15fps min
    lastTime = t;

    let settled = true;
    for (const key in state) {
      const s = state[key];
      const force = -stiffness * (s.pos - s.target);
      const dampForce = -damping * s.vel;
      const accel = (force + dampForce) / mass;
      s.vel += accel * dt;
      s.pos += s.vel * dt;

      if (Math.abs(s.vel) > 0.01 || Math.abs(s.pos - s.target) > 0.001) {
        settled = false;
      } else {
        s.pos = s.target;
        s.vel = 0;
      }
    }

    _applyProps(el, state);

    if (!settled) raf(tick);
    else onComplete();
  }
  raf(tick);

  return { cancel() { cancelled = true; } };
}

// ━━━ Preset Animations ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/** Fade in (opacity 0→1 + slight Y shift). Nintendo menu item entrance. */
function fadeIn(el, opts) {
  opts = opts || {};
  el.style.opacity = '0';
  el.style.transform = 'translateY(' + (opts.y || 12) + 'px)';
  return spring(el, { opacity: [0, 1], y: [opts.y || 12, 0] }, {
    stiffness: opts.stiffness || 180,
    damping: opts.damping || 18,
    ...opts,
  });
}

/** Fade out (opacity 1→0 + slight Y shift down). */
function fadeOut(el, opts) {
  opts = opts || {};
  return spring(el, { opacity: [1, 0], y: [0, opts.y || 8] }, {
    stiffness: opts.stiffness || 200,
    damping: opts.damping || 20,
    onComplete: () => { el.style.display = 'none'; if (opts.onComplete) opts.onComplete(); },
    ...opts,
  });
}

/** Pop in (scale 0→1 with overshoot). Nintendo Switch icon bounce. */
function popIn(el, opts) {
  opts = opts || {};
  el.style.opacity = '0';
  el.style.transform = 'scale(0)';
  return spring(el, { scale: [0, 1], opacity: [0, 1] }, {
    stiffness: opts.stiffness || 300,
    damping: opts.damping || 12,
    ...opts,
  });
}

/** Pop out (scale 1→0). */
function popOut(el, opts) {
  opts = opts || {};
  return spring(el, { scale: [1, 0], opacity: [1, 0] }, {
    stiffness: opts.stiffness || 250,
    damping: opts.damping || 18,
    onComplete: () => { el.style.display = 'none'; if (opts.onComplete) opts.onComplete(); },
    ...opts,
  });
}

/** Shake (horizontal wobble). Error feedback. */
function shake(el, opts) {
  opts = opts || {};
  const intensity = opts.intensity || 8;
  const duration = opts.duration || 400;
  return tween({
    from: 0, to: 1, duration,
    easing: 'linear',
    onUpdate: (_, t) => {
      const decay = 1 - t;
      const x = Math.sin(t * PI * 6) * intensity * decay;
      el.style.transform = 'translateX(' + x + 'px)';
    },
    onComplete: () => { el.style.transform = ''; },
  });
}

/** Pulse (scale breathe). Highlight/attention. */
function pulse(el, opts) {
  opts = opts || {};
  const scale = opts.scale || 1.08;
  return spring(el, { scale: [1, scale] }, {
    stiffness: 150, damping: 8,
    onComplete: () => spring(el, { scale: [scale, 1] }, { stiffness: 200, damping: 14 }),
  });
}

/** Slide in from direction. */
function slideIn(el, opts) {
  opts = opts || {};
  const dir = opts.direction || 'left';
  const dist = opts.distance || 40;
  const from = dir === 'left' ? -dist : dir === 'right' ? dist : 0;
  const fromY = dir === 'up' ? -dist : dir === 'down' ? dist : 0;
  el.style.opacity = '0';
  return spring(el, { opacity: [0, 1], x: [from, 0], y: [fromY, 0] }, {
    stiffness: opts.stiffness || 180,
    damping: opts.damping || 16,
    ...opts,
  });
}

// ━━━ Stagger ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Stagger animation across multiple elements.
 * @param {string|NodeList|Array} selector
 * @param {object} props - spring props
 * @param {object} opts - { delay: ms per item, stiffness, damping, animation: 'spring'|'fadeIn'|'popIn'|'slideIn' }
 */
function stagger(selector, props, opts) {
  opts = opts || {};
  const els = typeof selector === 'string' ? document.querySelectorAll(selector) : selector;
  const delay = opts.delay || 50;
  const anim = opts.animation || 'spring';
  const handles = [];

  Array.from(els).forEach((el, i) => {
    setTimeout(() => {
      let h;
      if (anim === 'fadeIn') h = fadeIn(el, opts);
      else if (anim === 'popIn') h = popIn(el, opts);
      else if (anim === 'slideIn') h = slideIn(el, opts);
      else h = spring(el, props, opts);
      handles.push(h);
    }, i * delay);
  });

  return { cancel() { handles.forEach(h => h && h.cancel()); } };
}

// ━━━ Transition ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * CSS transition helper with promise.
 * @param {HTMLElement} el
 * @param {object} styles - target CSS props
 * @param {object} opts - { duration, easing }
 * @returns {Promise}
 */
function transition(el, styles, opts) {
  opts = opts || {};
  const dur = (opts.duration || 300) + 'ms';
  const easing = opts.easing || 'cubic-bezier(0.22, 1, 0.36, 1)'; // Nintendo ease-out
  el.style.transition = 'all ' + dur + ' ' + easing;
  return new Promise(resolve => {
    const onEnd = () => { el.removeEventListener('transitionend', onEnd); resolve(); };
    el.addEventListener('transitionend', onEnd);
    raf(() => Object.assign(el.style, styles));
  });
}

// ━━━ Helpers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function _getCurrentValue(el, key) {
  if (key === 'opacity') return parseFloat(getComputedStyle(el).opacity) || 1;
  if (key === 'scale') return 1;
  if (key === 'x' || key === 'y' || key === 'rotate') return 0;
  return 0;
}

function _applyProps(el, state) {
  let transform = '';
  if ('x' in state || 'y' in state) {
    const x = state.x ? state.x.pos : 0;
    const y = state.y ? state.y.pos : 0;
    transform += 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px) ';
  }
  if ('scale' in state) {
    transform += 'scale(' + state.scale.pos.toFixed(3) + ') ';
  }
  if ('rotate' in state) {
    transform += 'rotate(' + state.rotate.pos.toFixed(1) + 'deg) ';
  }
  if (transform) el.style.transform = transform;
  if ('opacity' in state) el.style.opacity = state.opacity.pos.toFixed(3);
}

// ━━━ Public API ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

root.KamiMotion = {
  VERSION: '1.0.0',
  ease,
  tween,
  spring,
  // Presets
  fadeIn,
  fadeOut,
  popIn,
  popOut,
  shake,
  pulse,
  slideIn,
  // Orchestration
  stagger,
  transition,
};

})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
