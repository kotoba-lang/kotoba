<script lang="ts">
	import { cn } from '../../utils.js';
	import type { Snippet } from 'svelte';

	interface Props {
		class?: string;
		children: Snippet;
	}

	let { class: className, children }: Props = $props();
</script>

<div class={cn('snap-start snap-always h-full w-full relative shrink-0', className)}>
	{@render children()}
</div>
