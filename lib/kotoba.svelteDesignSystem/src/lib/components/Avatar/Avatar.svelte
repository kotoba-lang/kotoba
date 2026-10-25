<script lang="ts">
	import { cn } from '../../utils.js';
	import { spring } from 'svelte/motion';
	import { playHover, haptic } from '../../audio/ui-sounds.js';

	interface Props {
		src?: string | null;
		alt?: string;
		fallback?: string;
		size?: 'sm' | 'md' | 'lg' | 'xl';
		ring?: boolean;
		ringColor?: string;
		interactive?: boolean;
		class?: string;
	}

	let {
		src,
		alt = '',
		fallback = '?',
		size = 'md',
		ring = false,
		ringColor = 'ring-white/30',
		interactive = false,
		class: className
	}: Props = $props();

	const sizeMap = {
		sm: 'w-8 h-8 text-xs',
		md: 'w-10 h-10 text-sm',
		lg: 'w-12 h-12 text-base',
		xl: 'w-16 h-16 text-lg'
	};

	let imgError = $state(false);
	const showImage = $derived(src && !imgError);

	// Hover micro-interaction (Nintendo-style subtle scale + glow)
	const hoverScale = spring(1, { stiffness: 0.3, damping: 0.7 });
	const glowOpacity = spring(0, { stiffness: 0.2, damping: 0.8 });

	function onEnter() {
		if (!interactive) return;
		hoverScale.set(1.08);
		glowOpacity.set(0.6);
		playHover();
	}
	function onLeave() {
		hoverScale.set(1);
		glowOpacity.set(0);
	}
	function onDown() {
		if (!interactive) return;
		hoverScale.set(0.92);
		haptic('light');
	}
	function onUp() {
		hoverScale.set(interactive ? 1.08 : 1);
	}
</script>

{#if interactive}
	<button
		type="button"
		class={cn(
			'relative shrink-0 rounded-full overflow-hidden p-0 border-0 bg-transparent cursor-pointer',
			sizeMap[size],
			ring && `ring-2 ${ringColor}`,
			className
		)}
		style={`transform: scale(${$hoverScale}); box-shadow: 0 0 ${$glowOpacity * 16}px ${$glowOpacity * 4}px var(--gv2-accent, rgba(255,255,255,0.3))`}
		onpointerenter={onEnter}
		onpointerleave={onLeave}
		onpointerdown={onDown}
		onpointerup={onUp}
	>
		{#if showImage}
			<img
				{src}
				{alt}
				class="w-full h-full object-cover"
				loading="lazy"
				onerror={() => (imgError = true)}
			/>
		{:else}
			<div
				class="w-full h-full bg-gradient-to-br from-white/10 to-white/5 grid place-items-center"
			>
				<span class="font-bold text-white/40">{fallback[0]?.toUpperCase() ?? '?'}</span>
			</div>
		{/if}
	</button>
{:else}
	<div
		class={cn(
			'relative shrink-0 rounded-full overflow-hidden',
			sizeMap[size],
			ring && `ring-2 ${ringColor}`,
			className
		)}
	>
		{#if showImage}
			<img
				{src}
				{alt}
				class="w-full h-full object-cover"
				loading="lazy"
				onerror={() => (imgError = true)}
			/>
		{:else}
			<div
				class="w-full h-full bg-gradient-to-br from-white/10 to-white/5 grid place-items-center"
			>
				<span class="font-bold text-white/40">{fallback[0]?.toUpperCase() ?? '?'}</span>
			</div>
		{/if}
	</div>
{/if}
