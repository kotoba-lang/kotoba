import type { FlyParams, FadeParams, ScaleParams, SlideParams } from 'svelte/transition';

type SpringOptions = {
	stiffness?: number;
	damping?: number;
	precision?: number;
};

// ─── Staggered Transitions ──────────────────────────────────────────────────

/** Staggered fly transition — delays each item by index */
export function staggerFly(index: number, opts?: Partial<FlyParams>): FlyParams {
	return {
		y: opts?.y ?? 20,
		duration: opts?.duration ?? 200,
		delay: Math.min(index * (opts?.delay ?? 50), 500),
		...opts
	};
}

/** Staggered fade transition */
export function staggerFade(index: number, opts?: Partial<FadeParams>): FadeParams {
	return {
		duration: opts?.duration ?? 200,
		delay: Math.min(index * (opts?.delay ?? 40), 400),
		...opts
	};
}

/** Staggered scale transition */
export function staggerScale(index: number, opts?: Partial<ScaleParams>): ScaleParams {
	return {
		start: opts?.start ?? 0.85,
		duration: opts?.duration ?? 200,
		delay: Math.min(index * (opts?.delay ?? 30), 300),
		...opts
	};
}

// ─── Spring Presets ──────────────────────────────────────────────────────────

/** Spring preset for snap navigation (BottomNav indicator, TabBar underline) */
export const snapSpring: SpringOptions = { stiffness: 0.2, damping: 0.75 };

/** Spring preset for smooth UI elements (sheets, overlays) */
export const smoothSpring: SpringOptions = { stiffness: 0.15, damping: 0.8 };

/** Spring preset for bouncy reactions (heart taps, FAB press) */
export const bounceSpring: SpringOptions = { stiffness: 0.3, damping: 0.6 };

/** Duolingo-style button press — quick compress + slight overshoot */
export const duoPress: SpringOptions = { stiffness: 0.35, damping: 0.55 };

/** Duolingo-style celebration bounce — larger overshoot, playful */
export const duoBounce: SpringOptions = { stiffness: 0.25, damping: 0.45 };

/** Apple Liquid morphing — slow, fluid, high damping (Dynamic Island) */
export const liquidMorph: SpringOptions = { stiffness: 0.12, damping: 0.85 };

/** Apple rubber-band overscroll — snappy return with slight bounce */
export const rubberBand: SpringOptions = { stiffness: 0.4, damping: 0.7 };

/** Gentle floating — ambient background elements, parallax layers */
export const gentleFloat: SpringOptions = { stiffness: 0.08, damping: 0.9 };

/** Switch-style card float — responsive hover lift with slight bounce */
export const cardFloat: SpringOptions = { stiffness: 0.28, damping: 0.65 };

/** Switch-style focus ring — snappy glow transition */
export const focusGlow: SpringOptions = { stiffness: 0.32, damping: 0.7 };

// ─── Easing Functions ────────────────────────────────────────────────────────

/** Overshoot ease-out (used in sheets, depth transitions) */
export function overshootEase(t: number): number {
	const c1 = 1.70158;
	const c3 = c1 + 1;
	return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}

/** Elastic ease-out (used in springEnter, bounce) */
export function elasticEase(t: number): number {
	const c4 = (2 * Math.PI) / 3;
	return t === 0 ? 0 : t === 1 ? 1
		: Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
}

// ─── Slide Transitions ──────────────────────────────────────────────────────

/** Slide-in from bottom params for sheets/modals */
export function slideUp(opts?: Partial<SlideParams>): SlideParams {
	return {
		duration: opts?.duration ?? 250,
		axis: 'y',
		...opts
	};
}

/** Slide-in from right params for panel transitions */
export function slideRight(opts?: Partial<SlideParams>): SlideParams {
	return {
		duration: opts?.duration ?? 250,
		axis: 'x',
		...opts
	};
}

// ─── Advanced Transitions ───────────────────────────────────────────────────

/** Spring-based entrance — scale 0.85 → 1.02 → 1.0 with overshoot feel */
export function springEnter(index: number, opts?: Partial<ScaleParams>): ScaleParams {
	return {
		start: opts?.start ?? 0.8,
		duration: opts?.duration ?? 350,
		delay: Math.min(index * (opts?.delay ?? 40), 400),
		easing: elasticEase,
		...opts
	};
}

/** Morph fade — combined scale + fade for shape morphing transitions */
export function morphFade(opts?: Partial<ScaleParams & FadeParams>): ScaleParams {
	return {
		start: opts?.start ?? 0.92,
		duration: opts?.duration ?? 300,
		...opts
	};
}

/** Liquid slide — spring-like slide with overshoot, for sheets/panels */
export function liquidSlide(opts?: Partial<SlideParams>): SlideParams {
	return {
		duration: opts?.duration ?? 350,
		axis: opts?.axis ?? 'y',
		easing: overshootEase,
		...opts
	};
}

// ─── Switch 2 Depth Transitions ─────────────────────────────────────────────

/** Depth enter — page zooms in from behind (forward navigation).
 *  scale(1.06) + opacity(0) → scale(1.0) + opacity(1) with overshoot easing. */
export function depthEnter(opts?: Partial<ScaleParams>): ScaleParams {
	return {
		start: opts?.start ?? 1.06,
		duration: opts?.duration ?? 320,
		easing: overshootEase,
		...opts
	};
}

/** Depth exit — page shrinks + fades to background (forward navigation).
 *  scale(1.0) → scale(0.94) + opacity(0) + blur. */
export function depthExit(opts?: Partial<ScaleParams>): ScaleParams {
	return {
		start: opts?.start ?? 0.94,
		duration: opts?.duration ?? 250,
		...opts
	};
}

/** Depth back enter — page zooms from shrunk state (back navigation).
 *  scale(0.94) → scale(1.0). Reverse of depthExit. */
export function depthBackEnter(opts?: Partial<ScaleParams>): ScaleParams {
	return {
		start: opts?.start ?? 0.94,
		duration: opts?.duration ?? 280,
		easing: overshootEase,
		...opts
	};
}

/** Depth back exit — page zooms out forward (back navigation).
 *  scale(1.0) → scale(1.06) + opacity(0). Reverse of depthEnter. */
export function depthBackExit(opts?: Partial<ScaleParams>): ScaleParams {
	return {
		start: opts?.start ?? 1.06,
		duration: opts?.duration ?? 220,
		...opts
	};
}

/** Tab slide — horizontal slide for lateral tab navigation. */
export function tabSlide(direction: 'left' | 'right', opts?: Partial<FlyParams>): FlyParams {
	return {
		x: direction === 'right' ? 60 : -60,
		duration: opts?.duration ?? 250,
		easing: overshootEase,
		...opts
	};
}

// ─── Card Tilt Utilities ────────────────────────────────────────────────────

export type TiltOptions = {
	/** Max rotation in degrees (default: 8) */
	maxDeg?: number;
	/** Z translation on hover in px (default: 12) */
	liftPx?: number;
	/** Perspective distance in px (default: 800) */
	perspective?: number;
	/** Transition duration in ms for settle (default: 150) */
	duration?: number;
};

/** Compute 3D tilt transform string from pointer position within an element. */
export function computeTilt(
	rect: DOMRect,
	clientX: number,
	clientY: number,
	opts: TiltOptions = {}
): string {
	const maxDeg = opts.maxDeg ?? 8;
	const liftPx = opts.liftPx ?? 12;
	const perspective = opts.perspective ?? 800;
	const relX = (clientX - rect.left) / rect.width - 0.5; // -0.5 to 0.5
	const relY = (clientY - rect.top) / rect.height - 0.5;
	const rotateY = relX * maxDeg;
	const rotateX = -relY * maxDeg;
	return `perspective(${perspective}px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(${liftPx}px)`;
}

/** Reset tilt transform string. */
export function resetTilt(opts: TiltOptions = {}): string {
	const perspective = opts.perspective ?? 800;
	return `perspective(${perspective}px) rotateX(0deg) rotateY(0deg) translateZ(0px)`;
}

// ─── Parallax Scroll Utility ────────────────────────────────────────────────

/** Compute parallax translateY offset based on scroll position.
 *  @param scrollTop - current scroll position
 *  @param elementTop - element's top offset
 *  @param factor - parallax speed factor (0 = static, 1 = scroll speed, 0.1 = subtle) */
export function parallaxY(scrollTop: number, elementTop: number, factor: number = 0.1): string {
	const offset = (scrollTop - elementTop) * factor;
	return `translateY(${offset}px)`;
}
