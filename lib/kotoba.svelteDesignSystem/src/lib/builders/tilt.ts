import type { TiltOptions } from '../motion/index.js';
import { computeTilt, resetTilt } from '../motion/index.js';
import { playHover, haptic } from '../audio/ui-sounds.js';

export type TiltActionOptions = TiltOptions & {
	/** Play hover sound on enter (default: false) */
	sound?: boolean;
	/** Trigger haptic on enter (default: false) */
	hapticFeedback?: boolean;
	/** Shadow intensity on hover. 0 = no shadow (default: 0.3) */
	shadowOpacity?: number;
	/** Disable tilt entirely (for reduced-motion) */
	disabled?: boolean;
};

/** Svelte action: 3D perspective tilt on pointer move.
 *  Usage: `<div use:tilt={{ maxDeg: 8, liftPx: 12 }}>` */
export function tilt(node: HTMLElement, options: TiltActionOptions = {}) {
	let opts = { ...options };
	const origTransition = node.style.transition;

	function onEnter() {
		if (opts.disabled) return;
		node.style.transition = `transform ${opts.duration ?? 150}ms ease-out, box-shadow ${opts.duration ?? 150}ms ease-out`;
		if (opts.sound) playHover();
		if (opts.hapticFeedback) haptic('light');
	}

	function onMove(e: PointerEvent) {
		if (opts.disabled) return;
		const rect = node.getBoundingClientRect();
		node.style.transform = computeTilt(rect, e.clientX, e.clientY, opts);
		const shadowOp = opts.shadowOpacity ?? 0.3;
		if (shadowOp > 0) {
			node.style.boxShadow = `0 20px 40px rgba(0,0,0,${shadowOp})`;
		}
	}

	function onLeave() {
		node.style.transform = resetTilt(opts);
		node.style.boxShadow = '';
		setTimeout(() => {
			node.style.transition = origTransition;
		}, opts.duration ?? 150);
	}

	node.addEventListener('pointerenter', onEnter);
	node.addEventListener('pointermove', onMove);
	node.addEventListener('pointerleave', onLeave);

	return {
		update(newOpts: TiltActionOptions) {
			opts = { ...newOpts };
		},
		destroy() {
			node.removeEventListener('pointerenter', onEnter);
			node.removeEventListener('pointermove', onMove);
			node.removeEventListener('pointerleave', onLeave);
			node.style.transform = '';
			node.style.boxShadow = '';
		}
	};
}

/** Svelte action: scroll-linked parallax.
 *  Usage: `<div use:parallax={{ factor: 0.1 }}>` */
export function parallax(node: HTMLElement, options: { factor?: number; disabled?: boolean } = {}) {
	let opts = { ...options };
	let scrollParent: HTMLElement | null = null;

	function findScrollParent(el: HTMLElement): HTMLElement {
		let parent = el.parentElement;
		while (parent) {
			const style = getComputedStyle(parent);
			if (style.overflowY === 'auto' || style.overflowY === 'scroll') return parent;
			parent = parent.parentElement;
		}
		return document.documentElement;
	}

	function onScroll() {
		if (opts.disabled) return;
		const scrollTop = scrollParent?.scrollTop ?? 0;
		const rect = node.getBoundingClientRect();
		const parentRect = scrollParent?.getBoundingClientRect();
		const elementTop = rect.top - (parentRect?.top ?? 0) + scrollTop;
		const factor = opts.factor ?? 0.1;
		const offset = (scrollTop - elementTop) * factor;
		node.style.transform = `translateY(${offset}px)`;
	}

	scrollParent = findScrollParent(node);
	scrollParent.addEventListener('scroll', onScroll, { passive: true });
	onScroll();

	return {
		update(newOpts: { factor?: number; disabled?: boolean }) {
			opts = { ...newOpts };
		},
		destroy() {
			scrollParent?.removeEventListener('scroll', onScroll);
			node.style.transform = '';
		}
	};
}
