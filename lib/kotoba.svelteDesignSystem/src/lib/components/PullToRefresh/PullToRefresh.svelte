<script lang="ts">
	import { cn } from '../../utils.js';
	import { spring } from 'svelte/motion';
	import { playSnap, playSuccess, haptic } from '../../audio/ui-sounds.js';
	import type { Snippet } from 'svelte';

	interface Props {
		onrefresh?: () => Promise<void>;
		threshold?: number;
		class?: string;
		children: Snippet;
	}

	let { onrefresh, threshold = 80, class: className, children }: Props = $props();

	const pullY = spring(0, { stiffness: 0.15, damping: 0.8 });
	let startY = 0;
	let pulling = $state(false);
	let refreshing = $state(false);
	let containerEl: HTMLDivElement;

	function handleTouchStart(e: TouchEvent) {
		if (containerEl.scrollTop > 0) return;
		pulling = true;
		startY = e.touches[0].clientY;
	}

	function handleTouchMove(e: TouchEvent) {
		if (!pulling) return;
		const dy = Math.max(0, e.touches[0].clientY - startY);
		pullY.set(Math.min(dy * 0.5, threshold * 1.5));
	}

	async function handleTouchEnd() {
		if (!pulling) return;
		pulling = false;

		if ($pullY >= threshold && onrefresh) {
			playSnap();
			haptic('medium');
			refreshing = true;
			try {
				await onrefresh();
				playSuccess();
			} finally {
				refreshing = false;
			}
		}
		pullY.set(0);
	}

	const ready = $derived($pullY >= threshold);
</script>

<div
	bind:this={containerEl}
	class={cn('relative overflow-y-auto', className)}
	ontouchstart={handleTouchStart}
	ontouchmove={handleTouchMove}
	ontouchend={handleTouchEnd}
	role="region"
	aria-label="Pull to refresh"
>
	<!-- Pull indicator -->
	<div
		class="flex justify-center items-center overflow-hidden"
		style="height: {$pullY}px"
	>
		{#if refreshing}
			<div class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
		{:else}
			<svg
				class={cn('w-5 h-5 text-white/50 transition-transform', ready && 'rotate-180')}
				viewBox="0 0 20 20"
				fill="currentColor"
			>
				<path
					fill-rule="evenodd"
					d="M10 3a.75.75 0 01.75.75v10.19l2.72-2.72a.75.75 0 111.06 1.06l-4 4a.75.75 0 01-1.06 0l-4-4a.75.75 0 111.06-1.06l2.72 2.72V3.75A.75.75 0 0110 3z"
					clip-rule="evenodd"
				/>
			</svg>
		{/if}
	</div>

	{@render children()}
</div>
