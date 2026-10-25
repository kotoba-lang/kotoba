<script lang="ts">
	import { cn } from '../../utils.js';
	import type { Snippet } from 'svelte';

	interface Reaction {
		icon: Snippet;
		count?: number | string;
		active?: boolean;
		onclick?: () => void;
	}

	interface Props {
		reactions: Reaction[];
		class?: string;
	}

	let { reactions, class: className }: Props = $props();

	let bouncing = $state<number | null>(null);

	function bounce(i: number) {
		bouncing = i;
		setTimeout(() => {
			bouncing = null;
		}, 200);
	}
</script>

<div class={cn('flex flex-col items-center gap-4', className)}>
	{#each reactions as reaction, i}
		<button
			type="button"
			class={cn(
				'flex flex-col items-center gap-1 touch-manipulation transition-transform duration-200',
				reaction.active ? 'text-red-500' : 'text-white',
				bouncing === i && 'scale-125'
			)}
			onclick={() => {
				bounce(i);
				reaction.onclick?.();
			}}
		>
			<div class="w-8 h-8">
				{@render reaction.icon()}
			</div>
			{#if reaction.count != null}
				<span class="text-[11px] text-white/70">{reaction.count}</span>
			{/if}
		</button>
	{/each}
</div>
