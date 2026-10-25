<script lang="ts">
	import { cn } from '../../utils.js';
	import { fade, fly, scale } from 'svelte/transition';
	import { playSheetOpen, playSheetClose, playTap, playLiquidPop, haptic } from '../../audio/ui-sounds.js';

	interface ActionItem {
		label: string;
		destructive?: boolean;
		onclick: () => void;
	}

	interface Props {
		open: boolean;
		onclose?: () => void;
		actions: ActionItem[];
		cancelLabel?: string;
		class?: string;
	}

	let {
		open = $bindable(false),
		onclose,
		actions,
		cancelLabel = 'Cancel',
		class: className
	}: Props = $props();

	function close() {
		playSheetClose();
		open = false;
		onclose?.();
	}

	$effect(() => {
		if (open) { playSheetOpen(); haptic('medium'); }
	});
</script>

{#if open}
	<!-- Backdrop with blur -->
	<div
		class="fixed inset-0 z-[79] bg-black/50 backdrop-blur-[2px]"
		transition:fade={{ duration: 200 }}
		onclick={close}
		onkeydown={(e) => {
			if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') {
				e.preventDefault();
				close();
			}
		}}
		role="button"
		tabindex={0}
		aria-label="Close"
	></div>

	<!-- Sheet with liquid slide-up -->
	<div
		class={cn(
			'fixed bottom-0 left-0 right-0 z-[80] px-2',
			'pb-[env(safe-area-inset-bottom,8px)]',
			className
		)}
		in:fly={{ y: 200, duration: 350, easing: (t) => {
			const c1 = 1.70158;
			const c3 = c1 + 1;
			return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
		}}}
		out:fly={{ y: 200, duration: 200 }}
		role="dialog"
		aria-modal="true"
	>
		<div class="bg-[#2a2a2a] rounded-2xl overflow-hidden mb-2">
			{#each actions as action, i}
				{#if i > 0}
					<div class="h-px bg-white/10"></div>
				{/if}
				<!-- Staggered entrance per action item -->
				<div
					in:scale={{ start: 0.92, duration: 250, delay: 60 + i * 40 }}
				>
					<button
						type="button"
						class={cn(
							'w-full py-4 text-center text-[17px] touch-manipulation transition-all duration-100 active:bg-white/10 active:scale-[0.97] focus-glow',
							action.destructive ? 'text-red-500 font-medium' : 'text-white'
						)}
						onclick={() => {
							playTap();
							haptic('light');
							action.onclick();
							close();
						}}
					>
						{action.label}
					</button>
				</div>
			{/each}
		</div>

		<!-- Cancel button with separate spring entrance -->
		<div in:scale={{ start: 0.9, duration: 250, delay: 60 + actions.length * 40 }}>
			<button
				type="button"
				class="w-full py-4 bg-[#2a2a2a] rounded-2xl text-center text-[17px] font-semibold text-white touch-manipulation transition-all duration-100 active:bg-white/10 active:scale-[0.97]"
				onclick={close}
			>
				{cancelLabel}
			</button>
		</div>
	</div>
{/if}
