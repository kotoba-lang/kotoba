<script lang="ts">
	/**
	 * EmptyState — Game-style empty/loading screen with animated floating shapes.
	 * Used when a list has no items, a tab has no content, or data is loading.
	 */
	import { cn } from '../../utils.js';
	import { onMount } from 'svelte';
	import { fade, scale } from 'svelte/transition';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Title text. */
		title?: string;
		/** Description text below title. */
		description?: string;
		/** Emoji or icon character for the floating center element. */
		icon?: string;
		/** Accent color for shapes (default: uses --gv2-accent). */
		accent?: string;
		/** Show animated background shapes (default: true). */
		animated?: boolean;
		/** Custom action button or content below description. */
		action?: Snippet;
		class?: string;
	}

	let {
		title = 'Nothing here yet',
		description = '',
		icon = '✨',
		accent,
		animated = true,
		action,
		class: className,
	}: Props = $props();

	let canvasEl: HTMLCanvasElement | undefined = $state();
	let animId = 0;
	let mounted = $state(false);

	function getAccentRgb(): [number, number, number] {
		if (accent) {
			const h = accent.replace('#', '');
			return [
				parseInt(h.substring(0, 2), 16),
				parseInt(h.substring(2, 4), 16),
				parseInt(h.substring(4, 6), 16),
			];
		}
		return [37, 99, 235]; // default blue
	}

	type FloatingObj = {
		x: number;
		y: number;
		vx: number;
		vy: number;
		size: number;
		rotation: number;
		rotSpeed: number;
		shape: number;
		alpha: number;
		pulsePhase: number;
	};

	onMount(() => {
		mounted = true;
		if (!animated || !canvasEl) return;

		const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (prefersReducedMotion) return;

		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;

		const dpr = window.devicePixelRatio > 1 ? 1.5 : 1;
		function resize() {
			if (!canvasEl) return;
			canvasEl.width = canvasEl.offsetWidth * dpr;
			canvasEl.height = canvasEl.offsetHeight * dpr;
		}
		resize();
		window.addEventListener('resize', resize);

		const objs: FloatingObj[] = [];
		for (let i = 0; i < 15; i++) {
			objs.push({
				x: Math.random() * canvasEl.width,
				y: Math.random() * canvasEl.height,
				vx: (Math.random() - 0.5) * 0.4,
				vy: (Math.random() - 0.5) * 0.4,
				size: Math.random() * 16 + 6,
				rotation: Math.random() * Math.PI * 2,
				rotSpeed: (Math.random() - 0.5) * 0.015,
				shape: Math.floor(Math.random() * 4),
				alpha: Math.random() * 0.12 + 0.03,
				pulsePhase: Math.random() * Math.PI * 2,
			});
		}

		let lastTime = 0;
		const FPS = 1000 / 24; // 24fps

		function draw(now: number) {
			animId = requestAnimationFrame(draw);
			if (!ctx || !canvasEl) return;
			if (now - lastTime < FPS) return;
			lastTime = now;

			const w = canvasEl.width;
			const h = canvasEl.height;
			const [r, g, b] = getAccentRgb();
			ctx.clearRect(0, 0, w, h);

			for (const o of objs) {
				o.x += o.vx;
				o.y += o.vy;
				o.rotation += o.rotSpeed;
				if (o.x < -30) o.x = w + 30;
				if (o.x > w + 30) o.x = -30;
				if (o.y < -30) o.y = h + 30;
				if (o.y > h + 30) o.y = -30;

				const pulse = Math.sin(now * 0.002 + o.pulsePhase) * 0.3 + 0.7;
				const alpha = o.alpha * pulse;

				ctx.save();
				ctx.translate(o.x, o.y);
				ctx.rotate(o.rotation);
				ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
				ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.6})`;
				ctx.lineWidth = 1.5;

				const sz = o.size * (0.9 + pulse * 0.1);

				if (o.shape === 0) {
					// Rounded square
					const hs = sz / 2;
					ctx.beginPath();
					ctx.roundRect(-hs, -hs, sz, sz, sz * 0.25);
					ctx.stroke();
				} else if (o.shape === 1) {
					// Triangle
					ctx.beginPath();
					ctx.moveTo(0, -sz * 0.6);
					ctx.lineTo(sz * 0.5, sz * 0.4);
					ctx.lineTo(-sz * 0.5, sz * 0.4);
					ctx.closePath();
					ctx.fill();
				} else if (o.shape === 2) {
					// Circle
					ctx.beginPath();
					ctx.arc(0, 0, sz * 0.4, 0, Math.PI * 2);
					ctx.fill();
				} else {
					// Cross / plus
					const arm = sz * 0.15;
					const len = sz * 0.5;
					ctx.fillRect(-arm, -len, arm * 2, len * 2);
					ctx.fillRect(-len, -arm, len * 2, arm * 2);
				}
				ctx.restore();
			}
		}
		animId = requestAnimationFrame(draw);

		return () => {
			cancelAnimationFrame(animId);
			window.removeEventListener('resize', resize);
		};
	});
</script>

<div
	class={cn(
		'relative flex flex-col items-center justify-center py-16 px-6 text-center min-h-[300px]',
		className
	)}
>
	<!-- Animated background -->
	{#if animated}
		<canvas
			bind:this={canvasEl}
			class="absolute inset-0 h-full w-full pointer-events-none"
			aria-hidden="true"
		></canvas>
	{/if}

	{#if mounted}
		<div class="relative z-10 flex flex-col items-center gap-3">
			<!-- Floating icon -->
			<div
				class="text-4xl empty-float"
				in:scale={{ start: 0.5, duration: 500 }}
			>
				{icon}
			</div>

			<!-- Title -->
			<h3
				class="text-lg font-semibold text-white/80"
				in:fade={{ delay: 150, duration: 300 }}
			>
				{title}
			</h3>

			<!-- Description -->
			{#if description}
				<p
					class="text-sm text-white/40 max-w-[280px]"
					in:fade={{ delay: 300, duration: 300 }}
				>
					{description}
				</p>
			{/if}

			<!-- Action slot -->
			{#if action}
				<div class="mt-3" in:fade={{ delay: 450, duration: 300 }}>
					{@render action()}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.empty-float {
		animation: empty-bob 3s ease-in-out infinite;
	}
	@keyframes empty-bob {
		0%, 100% { transform: translateY(0); }
		50% { transform: translateY(-8px); }
	}
	@media (prefers-reduced-motion: reduce) {
		.empty-float { animation: none; }
	}
</style>
