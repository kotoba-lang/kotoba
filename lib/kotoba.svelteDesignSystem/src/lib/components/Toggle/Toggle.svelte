<script lang="ts">
	import { cn } from '../../utils.js';
	import { spring } from 'svelte/motion';
	import { playToggle, playLiquidPop, haptic } from '../../audio/ui-sounds.js';

	interface Props {
		checked?: boolean;
		onchange?: (checked: boolean) => void;
		disabled?: boolean;
		label?: string;
		class?: string;
	}

	let { checked = $bindable(false), onchange, disabled = false, label, class: className }: Props =
		$props();

	// Liquid morph: thumb stretches horizontally during transition
	const thumbX = spring(0, { stiffness: 0.12, damping: 0.85 });
	const thumbScaleX = spring(1, { stiffness: 0.25, damping: 0.6 });
	const thumbScaleY = spring(1, { stiffness: 0.3, damping: 0.55 });
	// Track background color interpolation
	const trackProgress = spring(0, { stiffness: 0.12, damping: 0.85 });

	$effect(() => {
		thumbX.set(checked ? 20 : 0);
		trackProgress.set(checked ? 1 : 0);
	});

	function toggle() {
		if (disabled) return;
		checked = !checked;
		playToggle(checked);
		playLiquidPop();
		haptic('medium');
		// Liquid stretch: expand horizontally, compress vertically during transition
		thumbScaleX.set(1.3);
		thumbScaleY.set(0.85);
		setTimeout(() => {
			thumbScaleX.set(0.9);
			thumbScaleY.set(1.1);
		}, 100);
		setTimeout(() => {
			thumbScaleX.set(1);
			thumbScaleY.set(1);
		}, 200);
		onchange?.(checked);
	}
</script>

<button
	type="button"
	role="switch"
	aria-checked={checked}
	aria-label={label}
	{disabled}
	class={cn(
		'relative inline-flex w-[51px] h-[31px] rounded-full touch-manipulation tap-target-44 focus-glow',
		disabled && 'opacity-50 cursor-not-allowed',
		className
	)}
	style="background: color-mix(in srgb, rgb(34,197,94) {$trackProgress * 100}%, rgba(255,255,255,0.2) {(1 - $trackProgress) * 100}%)"
	onclick={toggle}
>
	<!-- Liquid thumb -->
	<span
		class="absolute top-[2px] left-[2px] w-[27px] h-[27px] rounded-full bg-white"
		style="transform: translateX({$thumbX}px) scaleX({$thumbScaleX}) scaleY({$thumbScaleY}); box-shadow: 0 2px 8px rgba(0,0,0,0.15){checked ? ', 0 0 12px rgba(34,197,94,0.3)' : ''}"
	></span>
</button>
