<script lang="ts">
	import { cn } from '../../utils.js';

	interface Props {
		variant?: 'text' | 'circular' | 'rectangular';
		width?: string;
		height?: string;
		class?: string;
	}

	let { variant = 'text', width, height, class: className }: Props = $props();

	const variantMap = {
		text: 'h-4 rounded',
		circular: 'rounded-full',
		rectangular: 'rounded-xl'
	};
</script>

<div
	class={cn('relative overflow-hidden bg-white/10', variantMap[variant], className)}
	style:width={width}
	style:height={height}
	aria-hidden="true"
>
	<div class="absolute inset-0 skeleton-shimmer"></div>
</div>

<style>
	.skeleton-shimmer {
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(255, 255, 255, 0.06) 40%,
			rgba(255, 255, 255, 0.06) 60%,
			transparent 100%
		);
		animation: shimmer 1.8s ease-in-out infinite;
	}
	@keyframes shimmer {
		0% { transform: translateX(-100%); }
		100% { transform: translateX(100%); }
	}
	@media (prefers-reduced-motion: reduce) {
		.skeleton-shimmer { animation: none; opacity: 0; }
	}
</style>
