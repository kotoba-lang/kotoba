<script lang="ts">
	import { cn } from '../../utils.js';
	import { onDestroy } from 'svelte';
	import { spring } from 'svelte/motion';
	import type { Snippet } from 'svelte';
	import { playTabSwitch, haptic } from '../../audio/ui-sounds.js';

	interface NavItem {
		href?: string;
		value?: string;
		label: string;
		icon: Snippet;
		isCenter?: boolean;
	}

	interface Props {
		items: NavItem[];
		activePath?: string;
		activeValue?: string;
		onchange?: (value: string) => void;
		accentClass?: string;
		inactiveClass?: string;
		centerGradient?: string;
		class?: string;
		style?: string;
	}

	let {
		items,
		activePath,
		activeValue,
		onchange,
		accentClass = 'text-white',
		inactiveClass = 'text-white/50',
		centerGradient = 'from-orange-500 to-red-600',
		class: className,
		style = ''
	}: Props = $props();

	// Liquid morphing indicator: position + width morph during transition
	const indicatorLeft = spring(0, { stiffness: 0.12, damping: 0.85 });
	const indicatorWidth = spring(4, { stiffness: 0.12, damping: 0.85 });
	// Glow intensity for active indicator
	const glowIntensity = spring(0, { stiffness: 0.15, damping: 0.8 });
	const itemWidth = $derived(items.length > 0 ? 100 / items.length : 0);
	let prevIndex = -1;
	const timeoutIds = new Set<ReturnType<typeof setTimeout>>();

	function scheduleTimeout(fn: () => void, delayMs: number) {
		const id = setTimeout(() => {
			timeoutIds.delete(id);
			fn();
		}, delayMs);
		timeoutIds.add(id);
	}

	onDestroy(() => {
		for (const id of timeoutIds) {
			clearTimeout(id);
		}
		timeoutIds.clear();
	});

	let activeIndex = $derived.by(() => {
		if (activeValue != null) {
			return items.findIndex((item) => (item.value ?? item.href) === activeValue);
		}
		if (activePath != null) {
			return items.findIndex(
				(item) => {
					const href = item.href ?? '';
					return activePath === href || (href !== '/' && activePath.startsWith(href));
				}
			);
		}
		return -1;
	});

	$effect(() => {
		if (activeIndex >= 0) {
			const targetLeft = activeIndex * itemWidth + itemWidth / 2;
			if (prevIndex >= 0 && prevIndex !== activeIndex) {
				const dist = Math.abs(activeIndex - prevIndex);
				indicatorWidth.set(4 + dist * 12);
				scheduleTimeout(() => indicatorWidth.set(4), 150);
				glowIntensity.set(1);
				scheduleTimeout(() => glowIntensity.set(0.4), 300);
			} else {
				glowIntensity.set(0.4);
			}
			indicatorLeft.set(targetLeft);
			prevIndex = activeIndex;
		}
	});

	const iconScale = spring(1, { stiffness: 0.35, damping: 0.55 });
	let lastClickedIndex = $state(-1);

	let ripple = $state<{ x: number; y: number; active: boolean }>({ x: 0, y: 0, active: false });

	function handleClick(item: NavItem, index: number, e: MouseEvent | PointerEvent) {
		playTabSwitch();
		haptic('light');
		lastClickedIndex = index;

		const btn = (e.currentTarget as HTMLElement);
		const rect = btn.getBoundingClientRect();
		ripple = { x: e.clientX - rect.left, y: e.clientY - rect.top, active: true };
		scheduleTimeout(() => {
			ripple = { ...ripple, active: false };
		}, 400);

		iconScale.set(0.7);
		scheduleTimeout(() => iconScale.set(1.15), 60);
		scheduleTimeout(() => iconScale.set(0.92), 150);
		scheduleTimeout(() => iconScale.set(1), 230);

		if (onchange) {
			onchange(item.value ?? item.href ?? '');
		}
	}
</script>

<nav
	class={cn(
		'w-full shrink-0',
		'bg-[var(--gv2-bg-primary,#0a0a0a)] border-t border-[var(--gv2-border,#2f2f2f)]',
		'pb-[env(safe-area-inset-bottom,0px)]',
		className
	)}
	style={style}
>
	<div class="relative flex items-center h-[64px]" role="tablist">
		<!-- Glow indicator with liquid morph -->
		<div
			class="absolute top-0.5 h-1 rounded-full"
			style="left: calc({$indicatorLeft}% - {$indicatorWidth / 2}px); width: {$indicatorWidth}px; background: var(--gv2-accent, #2563eb); box-shadow: 0 0 {8 + $glowIntensity * 12}px {2 + $glowIntensity * 4}px var(--gv2-accent, #2563eb); opacity: {0.6 + $glowIntensity * 0.4}"
		></div>

		{#each items as item, i (item.value ?? item.href ?? i)}
			{@const isActive = activeIndex === i}
			{#if item.href && !onchange}
				<a
					href={item.href}
					class={cn(
						'flex-1 flex flex-col items-center justify-center gap-0.5 h-full touch-manipulation tap-target-44 no-underline relative overflow-hidden',
						item.isCenter ? '' : isActive ? accentClass : inactiveClass
					)}
					style={lastClickedIndex === i ? `transform: scale(${$iconScale})` : ''}
					onclick={(e) => handleClick(item, i, e)}
					role="tab"
					aria-selected={isActive}
					aria-label={item.label}
				>
					{#if ripple.active && lastClickedIndex === i}
						<span
							class="absolute rounded-full bg-white/10 pointer-events-none"
							style="left: {ripple.x}px; top: {ripple.y}px; width: 0; height: 0; transform: translate(-50%, -50%); animation: ripple-expand 0.4s ease-out forwards"
						></span>
					{/if}
					{#if item.isCenter}
						<div class={cn('w-12 h-12 -mt-3 rounded-full bg-gradient-to-br grid place-items-center shadow-lg transition-transform duration-150 active:scale-90', centerGradient)}>
							<div class="text-white">{@render item.icon()}</div>
						</div>
					{:else}
						<div class="w-7 h-7 transition-transform duration-150">{@render item.icon()}</div>
						<span class={cn('text-[10px] leading-none transition-all duration-200', isActive ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1')}>{item.label}</span>
					{/if}
				</a>
			{:else}
				<button
					class={cn(
						'flex-1 flex flex-col items-center justify-center gap-0.5 h-full touch-manipulation tap-target-44 relative overflow-hidden',
						item.isCenter ? '' : isActive ? accentClass : inactiveClass
					)}
					style={lastClickedIndex === i ? `transform: scale(${$iconScale})` : ''}
					onclick={(e) => handleClick(item, i, e)}
					role="tab"
					aria-selected={isActive}
					aria-label={item.label}
					aria-current={isActive ? 'page' : undefined}
				>
					{#if ripple.active && lastClickedIndex === i}
						<span
							class="absolute rounded-full bg-white/10 pointer-events-none"
							style="left: {ripple.x}px; top: {ripple.y}px; width: 0; height: 0; transform: translate(-50%, -50%); animation: ripple-expand 0.4s ease-out forwards"
						></span>
					{/if}
					{#if item.isCenter}
						<div class={cn('w-12 h-12 -mt-3 rounded-full bg-gradient-to-br grid place-items-center shadow-lg transition-transform duration-150 active:scale-90', centerGradient)}>
							<div class="text-white">{@render item.icon()}</div>
						</div>
					{:else}
						<div class="w-7 h-7 transition-transform duration-150">{@render item.icon()}</div>
						<span class={cn('text-[10px] leading-none transition-all duration-200', isActive ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1')}>{item.label}</span>
					{/if}
				</button>
			{/if}
		{/each}
	</div>
</nav>

<style>
	@keyframes ripple-expand {
		to {
			width: 120px;
			height: 120px;
			opacity: 0;
		}
	}
</style>
