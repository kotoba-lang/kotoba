<script lang="ts">
	import { cn } from '../../utils.js';
	import { fade, fly } from 'svelte/transition';
	import { spring } from 'svelte/motion';
	import type { Snippet } from 'svelte';
	import { playSheetOpen, playSheetClose, playLiquidPop, haptic } from '../../audio/ui-sounds.js';

	interface Props {
		open: boolean;
		onclose?: () => void;
		snapHeight?: string;
		class?: string;
		children: Snippet;
		handle?: boolean;
	}

	let {
		open = $bindable(false),
		onclose,
		snapHeight = '50vh',
		class: className,
		children,
		handle = true
	}: Props = $props();

	// Rubber-band spring for drag gesture
	const dragY = spring(0, { stiffness: 0.4, damping: 0.7 });
	const sheetScale = spring(1, { stiffness: 0.3, damping: 0.65 });
	let startY = 0;
	let dragging = false;

	function close() {
		playSheetClose();
		open = false;
		onclose?.();
	}

	$effect(() => {
		if (open) {
			playSheetOpen();
			haptic('medium');
			dragY.set(0, { hard: true });
			sheetScale.set(1, { hard: true });
		}
	});

	function handleTouchStart(e: TouchEvent) {
		dragging = true;
		startY = e.touches[0].clientY;
	}

	function handleTouchMove(e: TouchEvent) {
		if (!dragging) return;
		const dy = e.touches[0].clientY - startY;
		if (dy > 0) {
			// Dragging down: rubber-band resistance
			dragY.set(dy * 0.6, { hard: true });
			const progress = Math.min(dy / 300, 1);
			sheetScale.set(1 - progress * 0.03, { hard: true });
		} else {
			// Dragging up: strong rubber-band
			dragY.set(dy * 0.15, { hard: true });
		}
	}

	function handleTouchEnd() {
		dragging = false;
		if ($dragY > 80) {
			playLiquidPop();
			close();
		} else {
			dragY.set(0);
			sheetScale.set(1);
		}
	}

	// Overshoot ease for liquid entrance
	const overshootEase = (t: number) => {
		const c1 = 1.70158;
		const c3 = c1 + 1;
		return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
	};
</script>

{#if open}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 z-[79] bg-black/50"
		transition:fade={{ duration: 200 }}
		onclick={close}
		onkeydown={(e) => {
			if (e.key === 'Escape') close();
		}}
		role="button"
		tabindex={-1}
		aria-label="Close"
	></div>

	<!-- Sheet with liquid entrance + rubber-band drag -->
	<div
		class={cn(
			'fixed bottom-0 left-0 right-0 z-[80] bg-[#1a1a1a] rounded-t-2xl',
			'pb-[env(safe-area-inset-bottom,0px)]',
			className
		)}
		style="max-height: {snapHeight}; transform: translateY({$dragY}px) scale({$sheetScale}); transform-origin: bottom center"
		in:fly={{ y: 300, duration: 350, easing: overshootEase }}
		out:fly={{ y: 300, duration: 200 }}
		role="dialog"
		aria-modal="true"
	>
		{#if handle}
			<div
				class="flex justify-center pt-3 pb-2 cursor-grab active:cursor-grabbing touch-manipulation"
				ontouchstart={handleTouchStart}
				ontouchmove={handleTouchMove}
				ontouchend={handleTouchEnd}
				role="separator"
			>
				<div class="w-10 h-1.5 rounded-full bg-white/30"></div>
			</div>
		{/if}
		<div class="overflow-y-auto" style="max-height: calc({snapHeight} - 28px)">
			{@render children()}
		</div>
	</div>
{/if}
