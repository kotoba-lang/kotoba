<script lang="ts">
	import { cn } from '../../utils.js';
	import { fly, fade } from 'svelte/transition';
	import type { ToastItem } from '../../builders/toast.js';
	import { playToast, haptic } from '../../audio/ui-sounds.js';
	import { overshootEase } from '../../motion/index.js';

	interface Props {
		toasts: ToastItem[];
		onDismiss?: (id: string) => void;
		position?: 'top' | 'bottom';
		class?: string;
	}

	let { toasts, onDismiss, position = 'top', class: className }: Props = $props();

	let lastToastCount = 0;
	$effect(() => {
		if (toasts.length > lastToastCount && toasts.length > 0) {
			const newest = toasts[toasts.length - 1];
			playToast(newest.type);
			haptic('light');
		}
		lastToastCount = toasts.length;
	});

	const typeStyles = {
		info: 'bg-white/10 border-white/20 text-white',
		success: 'bg-green-500/20 border-green-500/30 text-green-200',
		warning: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-200',
		error: 'bg-red-500/20 border-red-500/30 text-red-200'
	};

	const typeGlow = {
		info: '',
		success: 'shadow-[0_0_16px_rgba(34,197,94,0.15)]',
		warning: 'shadow-[0_0_16px_rgba(234,179,8,0.15)]',
		error: 'shadow-[0_0_16px_rgba(239,68,68,0.15)]'
	};
</script>

<div
	class={cn(
		'fixed left-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none',
		position === 'top' ? 'top-4 safe-area-top' : 'bottom-20 safe-area-bottom',
		className
	)}
>
	{#each toasts as toast (toast.id)}
		<div
			class={cn(
				'pointer-events-auto rounded-xl border px-4 py-3 text-sm backdrop-blur-xl',
				typeStyles[toast.type],
				typeGlow[toast.type]
			)}
			in:fly={{ y: position === 'top' ? -30 : 30, duration: 320, easing: overshootEase }}
			out:fade={{ duration: 150 }}
			role="alert"
		>
			<div class="flex items-center justify-between gap-2">
				<span>{toast.message}</span>
				{#if onDismiss}
					<button
						type="button"
						class="shrink-0 text-white/50 hover:text-white touch-manipulation focus-glow rounded"
						onclick={() => onDismiss?.(toast.id)}
						aria-label="Dismiss"
					>
						<svg class="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M4 4l8 8M12 4l-8 8" />
						</svg>
					</button>
				{/if}
			</div>
		</div>
	{/each}
</div>
