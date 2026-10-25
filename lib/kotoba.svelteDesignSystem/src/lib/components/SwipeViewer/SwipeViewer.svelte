<script lang="ts">
	import { cn } from '../../utils.js';
	import type { Snippet } from 'svelte';

	interface Props {
		items: unknown[];
		currentIndex?: number;
		onchange?: (index: number) => void;
		class?: string;
		itemSnippet: Snippet<[unknown, number]>;
		threshold?: number;
		velocityThreshold?: number;
	}

	let {
		items,
		currentIndex = $bindable(0),
		onchange,
		class: className,
		itemSnippet,
		threshold = 50,
		velocityThreshold = 0.3
	}: Props = $props();

	let startX = 0;
	let startTime = 0;
	let translateX = $state(0);
	let swiping = $state(false);
	let containerWidth = $state(0);

	function handleTouchStart(e: TouchEvent) {
		swiping = true;
		startX = e.touches[0].clientX;
		startTime = Date.now();
		translateX = 0;
	}

	function handleTouchMove(e: TouchEvent) {
		if (!swiping) return;
		translateX = e.touches[0].clientX - startX;
	}

	function handleTouchEnd() {
		if (!swiping) return;
		swiping = false;

		const dt = Date.now() - startTime;
		const velocity = Math.abs(translateX) / dt;

		if (Math.abs(translateX) > threshold || velocity > velocityThreshold) {
			if (translateX > 0 && currentIndex > 0) {
				currentIndex--;
				onchange?.(currentIndex);
			} else if (translateX < 0 && currentIndex < items.length - 1) {
				currentIndex++;
				onchange?.(currentIndex);
			}
		}
		translateX = 0;
	}

	const offset = $derived(-currentIndex * 100 + (containerWidth > 0 ? (translateX / containerWidth) * 100 : 0));
</script>

<div
	class={cn('relative overflow-hidden touch-manipulation', className)}
	bind:clientWidth={containerWidth}
	ontouchstart={handleTouchStart}
	ontouchmove={handleTouchMove}
	ontouchend={handleTouchEnd}
	role="region"
	aria-roledescription="carousel"
>
	<div
		class={cn('flex h-full', swiping ? '' : 'transition-transform duration-300 ease-out')}
		style="transform: translateX({offset}%); width: {items.length * 100}%"
	>
		{#each items as item, i (i)}
			<div class="w-full h-full shrink-0" style="width: {100 / items.length}%">
				{@render itemSnippet(item, i)}
			</div>
		{/each}
	</div>
</div>
