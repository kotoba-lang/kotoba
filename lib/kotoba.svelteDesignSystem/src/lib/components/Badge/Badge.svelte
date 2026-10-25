<script lang="ts">
	import { cn } from '../../utils.js';

	interface Props {
		value?: string | number;
		variant?: 'default' | 'success' | 'warning' | 'error' | 'accent';
		dot?: boolean;
		class?: string;
	}

	let { value, variant = 'default', dot = false, class: className }: Props = $props();

	const variantMap = {
		default: 'bg-white/20 text-white',
		success: 'bg-green-500 text-white',
		warning: 'bg-yellow-500 text-black',
		error: 'bg-red-500 text-white',
		accent: 'bg-orange-500 text-white'
	};
</script>

{#if dot}
	<span class={cn('inline-block w-2 h-2 rounded-full', variantMap[variant], className)}></span>
{:else}
	<span
		class={cn(
			'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[11px] font-semibold leading-none',
			variantMap[variant],
			className
		)}
	>
		{value ?? ''}
	</span>
{/if}
