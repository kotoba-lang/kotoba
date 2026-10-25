<script lang="ts">
	import { cn } from '../../utils.js';
	import { playSnap, haptic } from '../../audio/ui-sounds.js';
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		headerHeight?: number;
		bottomNavHeight?: number;
		clickToAdvance?: boolean;
		class?: string;
		children: Snippet;
	}

	let {
		headerHeight = 56,
		bottomNavHeight = 52,
		clickToAdvance = false,
		class: className,
		children
	}: Props = $props();

	let containerEl: HTMLDivElement;
	let lastSnapIndex = -1;

	onMount(() => {
		if (!containerEl) return;
		let ticking = false;
		function onScroll() {
			if (ticking) return;
			ticking = true;
			requestAnimationFrame(() => {
				ticking = false;
				const items = containerEl.querySelectorAll(':scope > [class*="snap-start"]');
				const scrollTop = containerEl.scrollTop;
				const h = containerEl.clientHeight;
				let idx = 0;
				for (let i = 0; i < items.length; i++) {
					if ((items[i] as HTMLElement).offsetTop <= scrollTop + h / 2) idx = i;
				}
				if (idx !== lastSnapIndex) {
					lastSnapIndex = idx;
					playSnap();
					haptic('light');
				}
			});
		}
		containerEl.addEventListener('scroll', onScroll, { passive: true });
		return () => containerEl.removeEventListener('scroll', onScroll);
	});

	function handleClick(e: MouseEvent) {
		if (!clickToAdvance || !containerEl) return;
		// Don't advance if clicking interactive elements
		const target = e.target as HTMLElement;
		if (target.closest('a, button, input, select, textarea, [role="button"]')) return;

		const items = containerEl.querySelectorAll(':scope > [class*="snap-start"]');
		if (items.length === 0) return;

		// Find current snap item based on scroll position
		const scrollTop = containerEl.scrollTop;
		const containerHeight = containerEl.clientHeight;
		let currentIndex = 0;
		for (let i = 0; i < items.length; i++) {
			const item = items[i] as HTMLElement;
			if (item.offsetTop <= scrollTop + containerHeight / 2) {
				currentIndex = i;
			}
		}

		// Scroll to next item (or first if at the end)
		const nextIndex = currentIndex + 1 < items.length ? currentIndex + 1 : 0;
		items[nextIndex]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
	bind:this={containerEl}
	class={cn(
		'overflow-y-auto overscroll-y-contain snap-y snap-mandatory scrollbar-none',
		clickToAdvance && 'cursor-pointer',
		className
	)}
	style="height: calc(100dvh - {headerHeight}px - {bottomNavHeight}px - env(safe-area-inset-bottom, 0px))"
	onclick={clickToAdvance ? handleClick : undefined}
>
	{@render children()}
</div>
