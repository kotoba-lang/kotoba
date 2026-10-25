<script lang="ts">
	import { cn } from '../../utils.js';
	import { fly } from 'svelte/transition';
	import type { Snippet } from 'svelte';

	interface AvatarItem {
		id: string;
		src?: string | null;
		name: string;
		href?: string;
	}

	interface Props {
		items: AvatarItem[];
		size?: 'sm' | 'md' | 'lg';
		ringColor?: string;
		onItemClick?: (item: AvatarItem) => void;
		class?: string;
		itemSnippet?: Snippet<[AvatarItem, number]>;
	}

	let {
		items,
		size = 'md',
		ringColor = 'border-white/30',
		onItemClick,
		class: className,
		itemSnippet
	}: Props = $props();

	const sizeMap = {
		sm: { avatar: 'w-12 h-12', text: 'text-[10px]', gap: 'gap-3', p: 'p-0.5' },
		md: { avatar: 'w-16 h-16', text: 'text-[11px]', gap: 'gap-4', p: 'p-0.5' },
		lg: { avatar: 'w-20 h-20', text: 'text-xs', gap: 'gap-5', p: 'p-1' }
	};

	const s = $derived(sizeMap[size]);
</script>

<div
	class={cn(
		'flex overflow-x-auto scrollbar-none',
		s.gap,
		className
	)}
>
	{#each items as item, i (item.id)}
		{#if itemSnippet}
			{@render itemSnippet(item, i)}
		{:else}
			<button
				type="button"
				class="flex flex-col items-center shrink-0 touch-manipulation"
				in:fly={{ y: -10, duration: 200, delay: Math.min(i * 40, 300) }}
				onclick={() => onItemClick?.(item)}
			>
				<div class={cn('rounded-full border-2', ringColor, s.p, s.avatar)}>
					{#if item.src}
						<img
							src={item.src}
							alt={item.name}
							class="w-full h-full rounded-full object-cover"
							loading="lazy"
						/>
					{:else}
						<div
							class="w-full h-full rounded-full bg-gradient-to-br from-white/10 to-white/5 grid place-items-center"
						>
							<span class="text-sm font-bold text-white/40"
								>{item.name[0]?.toUpperCase() ?? '?'}</span
							>
						</div>
					{/if}
				</div>
				<span class={cn('mt-1 text-white/60 truncate max-w-[64px]', s.text)}>{item.name}</span>
			</button>
		{/if}
	{/each}
</div>
