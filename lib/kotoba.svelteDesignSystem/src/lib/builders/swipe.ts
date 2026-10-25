/** Headless swipe detection — returns Svelte action for touch/pointer handling */
export interface SwipeOpts {
	threshold?: number;
	velocityThreshold?: number;
	onSwipeLeft?: () => void;
	onSwipeRight?: () => void;
	onSwipeUp?: () => void;
	onSwipeDown?: () => void;
}

export function createSwipe(opts: SwipeOpts = {}) {
	const threshold = opts.threshold ?? 50;
	const velocityThreshold = opts.velocityThreshold ?? 0.3;

	function swipeAction(node: HTMLElement) {
		let startX = 0;
		let startY = 0;
		let startTime = 0;

		function handleTouchStart(e: TouchEvent) {
			const touch = e.touches[0];
			startX = touch.clientX;
			startY = touch.clientY;
			startTime = Date.now();
		}

		function handleTouchEnd(e: TouchEvent) {
			const touch = e.changedTouches[0];
			const dx = touch.clientX - startX;
			const dy = touch.clientY - startY;
			const dt = Date.now() - startTime;
			const vx = Math.abs(dx) / dt;
			const vy = Math.abs(dy) / dt;

			if (Math.abs(dx) > Math.abs(dy)) {
				if (Math.abs(dx) > threshold || vx > velocityThreshold) {
					if (dx > 0) opts.onSwipeRight?.();
					else opts.onSwipeLeft?.();
				}
			} else {
				if (Math.abs(dy) > threshold || vy > velocityThreshold) {
					if (dy > 0) opts.onSwipeDown?.();
					else opts.onSwipeUp?.();
				}
			}
		}

		node.addEventListener('touchstart', handleTouchStart, { passive: true });
		node.addEventListener('touchend', handleTouchEnd, { passive: true });

		return {
			destroy() {
				node.removeEventListener('touchstart', handleTouchStart);
				node.removeEventListener('touchend', handleTouchEnd);
			}
		};
	}

	return { action: swipeAction };
}
