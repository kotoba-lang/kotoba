<script lang="ts">
	import { cn } from '../../utils.js';
	import { spring } from 'svelte/motion';
	import { playTap, haptic } from '../../audio/ui-sounds.js';

	interface Props {
		label: string;
		active?: boolean;
		removable?: boolean;
		onRemove?: () => void;
		onclick?: () => void;
		class?: string;
	}

	let { label, active = false, removable = false, onRemove, onclick, class: className }: Props = $props();

	const scale = spring(1, { stiffness: 0.35, damping: 0.55 });

	function handleClick() {
		playTap();
		haptic('light');
		scale.set(0.88);
		setTimeout(() => scale.set(1.05), 80);
		setTimeout(() => scale.set(1), 170);
		onclick?.();
	}
</script>

{#if removable}
	<div
		class={cn(
			'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-150 touch-manipulation tap-target-44 card-float',
			active
				? 'bg-white text-black'
				: 'bg-white/10 text-white/70 hover:bg-white/15',
			className
		)}
		style="transform: scale({$scale})"
	>
		{#if onclick}
			<button
				type="button"
				class="min-w-0 flex-1 text-left focus-glow rounded"
				onclick={handleClick}
			>
				<span>{label}</span>
			</button>
		{:else}
			<span>{label}</span>
		{/if}
		<button
			type="button"
			class="ml-0.5 w-4 h-4 rounded-full bg-white/20 grid place-items-center hover:bg-white/30 focus-glow"
			onclick={(e) => {
				e.stopPropagation();
				playTap();
				onRemove?.();
			}}
			aria-label="Remove {label}"
		>
			<svg class="w-2.5 h-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M2 2l6 6M8 2l-6 6" />
			</svg>
		</button>
	</div>
{:else}
	<button
		type="button"
		class={cn(
			'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-150 touch-manipulation tap-target-44 focus-glow',
			active
				? 'bg-white text-black'
				: 'bg-white/10 text-white/70 hover:bg-white/15',
			className
		)}
		style="transform: scale({$scale})"
		onclick={handleClick}
	>
		<span>{label}</span>
	</button>
{/if}
