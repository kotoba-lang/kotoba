/**
 * UI Sound Effects — Web Audio API synthesized sounds.
 * Nintendo Switch 2 + Duolingo + Apple inspired.
 * All sounds are synthesized — no external audio files needed.
 */

let ctx: AudioContext | null = null;
let _enabled = true;
let _volume = 1.0;

function getCtx(): AudioContext | null {
	if (!_enabled) return null;
	if (!ctx) {
		try { ctx = new AudioContext(); } catch { return null; }
	}
	if (ctx.state === 'suspended') ctx.resume();
	return ctx;
}

/** Enable or disable all UI sounds globally. */
export function setUISoundsEnabled(enabled: boolean) { _enabled = enabled; }
export function getUISoundsEnabled() { return _enabled; }

/** Set master volume (0.0 to 1.0). */
export function setUISoundsVolume(vol: number) { _volume = Math.max(0, Math.min(1, vol)); }
export function getUISoundsVolume() { return _volume; }

function g(ac: AudioContext, baseGain: number): GainNode {
	const gain = ac.createGain();
	gain.gain.setValueAtTime(baseGain * _volume, ac.currentTime);
	return gain;
}

// ─── Core Interaction Sounds ────────────────────────────────────────────────

/** Soft tap — button/chip press. Switch-style crisp tick. */
export function playTap() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.05);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(2400, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(800, ac.currentTime + 0.02);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.035);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.04);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Select / confirm — Switch-style bright confirmation. */
export function playSelect() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.05);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(880, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(1320, ac.currentTime + 0.04);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.06);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.06);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Back / cancel — Switch-style descending tone. */
export function playBack() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.04);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(600, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(300, ac.currentTime + 0.03);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.04);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.04);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Hover / focus — ultra-subtle tick for cursor movement. */
export function playHover() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.02);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(1800, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(1400, ac.currentTime + 0.015);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.02);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.02);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Scroll tick — micro-feedback at scroll detent points. */
export function playScrollTick() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.015);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(1600, ac.currentTime);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.008);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.01);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Toggle switch — two-tone click. */
export function playToggle(on: boolean) {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.05);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(on ? 1200 : 800, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(on ? 1800 : 500, ac.currentTime + 0.04);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.06);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.06);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

// ─── Navigation Sounds ──────────────────────────────────────────────────────

/** Tab switch — Switch-style quick blip with harmonic. */
export function playTabSwitch() {
	const ac = getCtx(); if (!ac) return;
	try {
		// Primary tone
		const osc1 = ac.createOscillator();
		const gain1 = g(ac, 0.035);
		osc1.type = 'triangle';
		osc1.frequency.setValueAtTime(1600, ac.currentTime);
		osc1.frequency.exponentialRampToValueAtTime(2200, ac.currentTime + 0.03);
		gain1.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.045);
		osc1.connect(gain1).connect(ac.destination);
		osc1.start(ac.currentTime);
		osc1.stop(ac.currentTime + 0.05);
		// Harmonic shimmer
		const osc2 = ac.createOscillator();
		const gain2 = g(ac, 0.015);
		osc2.type = 'sine';
		osc2.frequency.setValueAtTime(3200, ac.currentTime);
		osc2.frequency.exponentialRampToValueAtTime(4400, ac.currentTime + 0.025);
		gain2.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.035);
		osc2.connect(gain2).connect(ac.destination);
		osc2.start(ac.currentTime);
		osc2.stop(ac.currentTime + 0.04);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Navigate forward — depth push sound. */
export function playNavForward() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.04);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(400, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(900, ac.currentTime + 0.08);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.12);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.12);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Navigate back — depth pull sound. */
export function playNavBack() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.035);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(800, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(350, ac.currentTime + 0.08);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.1);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.1);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

// ─── Sheet / Modal Sounds ───────────────────────────────────────────────────

/** Sheet open — rising whoosh with resonance. */
export function playSheetOpen() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.035);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(180, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(800, ac.currentTime + 0.12);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.18);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.18);
		// Breath layer
		const osc2 = ac.createOscillator();
		const gain2 = g(ac, 0.015);
		osc2.type = 'triangle';
		osc2.frequency.setValueAtTime(360, ac.currentTime);
		osc2.frequency.exponentialRampToValueAtTime(1200, ac.currentTime + 0.1);
		gain2.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.15);
		osc2.connect(gain2).connect(ac.destination);
		osc2.start(ac.currentTime);
		osc2.stop(ac.currentTime + 0.15);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Sheet close — falling whoosh. */
export function playSheetClose() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.03);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(600, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(180, ac.currentTime + 0.1);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.12);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.12);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

// ─── Notification / Feedback Sounds ─────────────────────────────────────────

/** Toast notification — gentle bell with type-specific pitch. */
export function playToast(type: 'info' | 'success' | 'warning' | 'error' = 'info') {
	const ac = getCtx(); if (!ac) return;
	try {
		const freqMap = { info: 880, success: 1047, warning: 660, error: 440 };
		const freq = freqMap[type];
		const osc = ac.createOscillator();
		const gain = g(ac, 0.04);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(freq, ac.currentTime);
		osc.frequency.setValueAtTime(freq * 1.5, ac.currentTime + 0.08);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.2);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.2);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Switch-style notification chime — bright double bell. */
export function playNotification() {
	const ac = getCtx(); if (!ac) return;
	try {
		[1047, 1319].forEach((freq, i) => {
			const osc = ac.createOscillator();
			const gain = g(ac, 0.04);
			osc.type = 'sine';
			osc.frequency.setValueAtTime(freq, ac.currentTime + i * 0.1);
			gain.gain.setValueAtTime(0, ac.currentTime);
			gain.gain.linearRampToValueAtTime(0.04 * _volume, ac.currentTime + i * 0.1 + 0.01);
			gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + i * 0.1 + 0.2);
			osc.connect(gain).connect(ac.destination);
			osc.start(ac.currentTime + i * 0.1);
			osc.stop(ac.currentTime + i * 0.1 + 0.25);
		});
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Snap scroll — soft thud on snap point. */
export function playSnap() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.06);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(150, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(60, ac.currentTime + 0.05);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.06);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.07);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

// ─── Achievement / Reward Sounds ────────────────────────────────────────────

/** Duolingo-style success — ascending major chord (C-E-G). */
export function playSuccess() {
	const ac = getCtx(); if (!ac) return;
	try {
		[523, 659, 784].forEach((freq, i) => {
			const osc = ac.createOscillator();
			const gain = g(ac, 0);
			osc.type = 'sine';
			osc.frequency.setValueAtTime(freq, ac.currentTime + i * 0.06);
			gain.gain.linearRampToValueAtTime(0.05 * _volume, ac.currentTime + i * 0.06 + 0.02);
			gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + i * 0.06 + 0.2);
			osc.connect(gain).connect(ac.destination);
			osc.start(ac.currentTime + i * 0.06);
			osc.stop(ac.currentTime + i * 0.06 + 0.25);
		});
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Celebration fanfare — ascending scale burst. */
export function playCelebrate() {
	const ac = getCtx(); if (!ac) return;
	try {
		[440, 554, 659, 880, 1047].forEach((freq, i) => {
			const osc = ac.createOscillator();
			const gain = g(ac, 0);
			osc.type = 'triangle';
			osc.frequency.setValueAtTime(freq, ac.currentTime + i * 0.04);
			gain.gain.linearRampToValueAtTime(0.04 * _volume, ac.currentTime + i * 0.04 + 0.01);
			gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + i * 0.04 + 0.15);
			osc.connect(gain).connect(ac.destination);
			osc.start(ac.currentTime + i * 0.04);
			osc.stop(ac.currentTime + i * 0.04 + 0.2);
		});
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Level up — warm ascending sweep. */
export function playLevelUp() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.05);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(300, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(1200, ac.currentTime + 0.25);
		gain.gain.linearRampToValueAtTime(0.06 * _volume, ac.currentTime + 0.1);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.35);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.35);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Soft error — descending minor second. */
export function playError() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.045);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(440, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(370, ac.currentTime + 0.08);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.15);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.15);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Apple-style liquid pop — bubbly burst. */
export function playLiquidPop() {
	const ac = getCtx(); if (!ac) return;
	try {
		const osc = ac.createOscillator();
		const gain = g(ac, 0.06);
		osc.type = 'sine';
		osc.frequency.setValueAtTime(800, ac.currentTime);
		osc.frequency.exponentialRampToValueAtTime(1600, ac.currentTime + 0.02);
		osc.frequency.exponentialRampToValueAtTime(400, ac.currentTime + 0.08);
		gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.1);
		osc.connect(gain).connect(ac.destination);
		osc.start(ac.currentTime);
		osc.stop(ac.currentTime + 0.1);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

// ─── Haptic Feedback ────────────────────────────────────────────────────────

/** Trigger device vibration (Vibration API). Falls back silently. */
export function haptic(pattern: 'light' | 'medium' | 'heavy' | number[] = 'light') {
	try {
		if (!navigator?.vibrate) return;
		const patterns: Record<string, number[]> = {
			light: [8],
			medium: [15],
			heavy: [30],
		};
		navigator.vibrate(Array.isArray(pattern) ? pattern : patterns[pattern] ?? [8]);
	} catch (error) { console.warn("[silent-fail] packages/svelte/design-system/src/lib/audio/ui-sounds.ts: suppressed error", error); }
}

/** Combined tap sound + haptic for Switch-like tactile feedback. */
export function tactile(sound: 'tap' | 'select' | 'back' | 'hover' = 'tap') {
	const sounds: Record<string, () => void> = { tap: playTap, select: playSelect, back: playBack, hover: playHover };
	sounds[sound]?.();
	haptic(sound === 'hover' ? 'light' : sound === 'select' ? 'medium' : 'light');
}
