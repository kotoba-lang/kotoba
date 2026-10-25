<script lang="ts">
	import { cn } from '../../utils.js';
	import { spring } from 'svelte/motion';
	import type { Snippet } from 'svelte';
	import { playTap, haptic } from '../../audio/ui-sounds.js';

	interface Props {
		onclick?: () => void;
		size?: 'sm' | 'md' | 'lg';
		position?: 'bottom-right' | 'bottom-center' | 'bottom-left';
		class?: string;
		children: Snippet;
		label?: string;
	}

	let {
		onclick,
		size = 'md',
		position = 'bottom-right',
		class: className,
		children,
		label
	}: Props = $props();

	const scale = spring(1, { stiffness: 0.3, damping: 0.6 });

	const sizeMap = {
		sm: 'w-10 h-10',
		md: 'w-14 h-14',
		lg: 'w-16 h-16'
	};

	const positionMap = {
		'bottom-right': 'fixed bottom-6 right-6',
		'bottom-center': 'fixed bottom-6 left-1/2 -translate-x-1/2',
		'bottom-left': 'fixed bottom-6 left-6'
	};
</script>

<button
	type="button"
	aria-label={label}
	class={cn(
		'rounded-full shadow-lg grid place-items-center touch-manipulation z-50 focus-glow',
		'bg-gradient-to-br from-orange-500 to-red-600 text-white',
		sizeMap[size],
		positionMap[position],
		'safe-area-bottom',
		className
	)}
	style="transform: scale({$scale})"
	onclick={() => {
		playTap();
		haptic('medium');
		scale.set(0.85);
		setTimeout(() => scale.set(1.08), 80);
		setTimeout(() => scale.set(1), 170);
		onclick?.();
	}}
	onpointerdown={() => scale.set(0.9)}
	onpointerup={() => scale.set(1)}
	onpointerleave={() => scale.set(1)}
>
	{@render children()}
</button>
