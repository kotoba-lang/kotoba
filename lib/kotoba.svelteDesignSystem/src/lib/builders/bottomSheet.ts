/** Headless bottom sheet builder — drag, snap points, open/close */
export interface CreateBottomSheetOpts {
	snapPoints?: number[];
	defaultOpen?: boolean;
	onOpenChange?: (open: boolean) => void;
}

export function createBottomSheet(opts: CreateBottomSheetOpts = {}) {
	const snapPoints = opts.snapPoints ?? [0.5, 0.9];
	let isOpen = $state(opts.defaultOpen ?? false);
	let translateY = $state(0);
	let dragging = $state(false);
	let startY = 0;
	let startTranslate = 0;

	function open() {
		isOpen = true;
		translateY = 0;
		opts.onOpenChange?.(true);
	}

	function close() {
		isOpen = false;
		translateY = 0;
		opts.onOpenChange?.(false);
	}

	function handleDragStart(clientY: number) {
		dragging = true;
		startY = clientY;
		startTranslate = translateY;
	}

	function handleDragMove(clientY: number, containerHeight: number) {
		if (!dragging) return;
		const dy = clientY - startY;
		const newTranslate = Math.max(0, startTranslate + dy);
		translateY = Math.min(newTranslate, containerHeight);
	}

	function handleDragEnd(containerHeight: number) {
		dragging = false;
		const ratio = translateY / containerHeight;

		if (ratio > 0.5) {
			close();
			return;
		}

		let closest = 0;
		let minDist = Infinity;
		for (const snap of snapPoints) {
			const snapY = containerHeight * (1 - snap);
			const dist = Math.abs(translateY - snapY);
			if (dist < minDist) {
				minDist = dist;
				closest = snapY;
			}
		}
		translateY = closest;
	}

	function dragHandleAction(node: HTMLElement) {
		function onTouchStart(e: TouchEvent) {
			handleDragStart(e.touches[0].clientY);
		}
		function onTouchMove(e: TouchEvent) {
			const container = node.closest('[data-bottom-sheet-content]');
			if (container) handleDragMove(e.touches[0].clientY, container.clientHeight);
		}
		function onTouchEnd() {
			const container = node.closest('[data-bottom-sheet-content]');
			if (container) handleDragEnd(container.clientHeight);
		}

		node.addEventListener('touchstart', onTouchStart, { passive: true });
		node.addEventListener('touchmove', onTouchMove, { passive: true });
		node.addEventListener('touchend', onTouchEnd, { passive: true });

		return {
			destroy() {
				node.removeEventListener('touchstart', onTouchStart);
				node.removeEventListener('touchmove', onTouchMove);
				node.removeEventListener('touchend', onTouchEnd);
			}
		};
	}

	return {
		get isOpen() {
			return isOpen;
		},
		get translateY() {
			return translateY;
		},
		get isDragging() {
			return dragging;
		},
		open,
		close,
		trigger: {
			onclick: open
		},
		overlay: {
			get hidden() {
				return !isOpen;
			},
			onclick: close
		},
		contentAttrs: {
			'data-bottom-sheet-content': ''
		},
		dragHandle: dragHandleAction
	};
}
