<script lang="ts">
	import { cn } from '../../utils.js';
	import { spring } from 'svelte/motion';
	import { playTabSwitch, haptic } from '../../audio/ui-sounds.js';

	interface Tab {
		value: string;
		label: string;
	}

	interface Props {
		tabs: Tab[];
		activeValue: string;
		onchange?: (value: string) => void;
		class?: string;
	}

	let { tabs, activeValue = $bindable(), onchange, class: className }: Props = $props();

	const underlineLeft = spring(0, { stiffness: 0.2, damping: 0.75 });
	const underlineWidth = spring(0, { stiffness: 0.2, damping: 0.75 });
	// Glow intensity for underline
	const glowIntensity = spring(0, { stiffness: 0.15, damping: 0.8 });
	// Per-tab press scale
	const tabScale = spring(1, { stiffness: 0.35, damping: 0.55 });
	let tabRefs: HTMLButtonElement[] = [];
	let lastClickedIndex = $state(-1);

	let activeIndex = $derived(tabs.findIndex((t) => t.value === activeValue));

	$effect(() => {
		const el = tabRefs[activeIndex];
		if (el) {
			underlineLeft.set(el.offsetLeft);
			underlineWidth.set(el.offsetWidth);
			// Glow flash on change
			glowIntensity.set(1);
			setTimeout(() => glowIntensity.set(0.3), 300);
		}
	});

	function select(value: string, index: number) {
		playTabSwitch();
		haptic('light');
		lastClickedIndex = index;
		// Bounce: compress → overshoot → settle
		tabScale.set(0.85);
		setTimeout(() => tabScale.set(1.08), 70);
		setTimeout(() => tabScale.set(0.97), 150);
		setTimeout(() => tabScale.set(1), 220);
		activeValue = value;
		onchange?.(value);
	}
</script>

<div
	class={cn('relative flex overflow-x-auto scrollbar-none border-b border-gv2-border/40', className)}
	role="tablist"
>
	{#each tabs as tab, i (tab.value)}
		<button
			bind:this={tabRefs[i]}
			type="button"
			role="tab"
			aria-selected={activeValue === tab.value}
			class={cn(
				'shrink-0 px-4 py-3 text-sm font-medium transition-colors touch-manipulation tap-target-44 focus-glow',
				activeValue === tab.value ? 'text-gv2-text-primary' : 'text-gv2-text-muted'
			)}
			style={lastClickedIndex === i ? `transform: scale(${$tabScale})` : ''}
			onclick={() => select(tab.value, i)}
		>
			{tab.label}
		</button>
	{/each}

	<!-- Glow underline indicator -->
	<div
		class="absolute bottom-0 h-0.5 rounded-full transition-none"
		style="left: {$underlineLeft}px; width: {$underlineWidth}px; background: var(--gv2-accent, #fff); box-shadow: 0 0 {6 + $glowIntensity * 10}px {1 + $glowIntensity * 3}px var(--gv2-accent, #fff); opacity: {0.7 + $glowIntensity * 0.3}"
	></div>
</div>
