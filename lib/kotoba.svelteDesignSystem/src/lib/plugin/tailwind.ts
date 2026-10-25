import plugin from 'tailwindcss/plugin.js';

export const etzhayyimUIKit = plugin(
	({ addUtilities }) => {
		addUtilities({
			'.safe-area-top': { 'padding-top': 'env(safe-area-inset-top, 0px)' },
			'.safe-area-bottom': { 'padding-bottom': 'env(safe-area-inset-bottom, 0px)' },
			'.safe-area-left': { 'padding-left': 'env(safe-area-inset-left, 0px)' },
			'.safe-area-right': { 'padding-right': 'env(safe-area-inset-right, 0px)' },
			'.tap-target-44': { 'min-width': '44px', 'min-height': '44px' },
			'.scrollbar-none': {
				'-ms-overflow-style': 'none',
				'scrollbar-width': 'none',
				'&::-webkit-scrollbar': { display: 'none' }
			},
			'.snap-y-mandatory': { 'scroll-snap-type': 'y mandatory' },
			'.snap-x-mandatory': { 'scroll-snap-type': 'x mandatory' },
			'.material-blur-xs': { 'backdrop-filter': 'blur(4px)' },
			'.material-blur-sm': { 'backdrop-filter': 'blur(10px)' },
			'.material-blur': { 'backdrop-filter': 'blur(20px)' },
			'.material-blur-lg': { 'backdrop-filter': 'blur(30px)' },
			// Duolingo 3D button press effect
			'.btn-3d-green': { 'box-shadow': '0 4px 0 #3D8A00' },
			'.btn-3d-blue': { 'box-shadow': '0 4px 0 #0E87BF' },
			'.btn-3d-red': { 'box-shadow': '0 4px 0 #CC1100' },
			'.btn-3d-gray': { 'box-shadow': '0 4px 0 rgba(0,0,0,0.15)' },
			'.btn-3d-press': {
				'transform': 'translateY(4px)',
				'box-shadow': 'none',
			},
			// Apple glass morphism
			'.glass': {
				'background': 'rgba(255,255,255,0.05)',
				'border': '1px solid rgba(255,255,255,0.1)',
				'backdrop-filter': 'blur(20px)',
			},
			'.glass-strong': {
				'background': 'rgba(255,255,255,0.08)',
				'border': '1px solid rgba(255,255,255,0.15)',
				'backdrop-filter': 'blur(30px)',
			},
			// ─── Switch 2 Card Float ────────────────────────────────────
			'.card-float': {
				'transition': 'transform 0.15s ease-out, box-shadow 0.15s ease-out',
				'will-change': 'transform',
			},
			'.card-float:hover, .card-float:focus-visible': {
				'transform': 'translateY(-4px) scale(1.02)',
				'box-shadow': '0 16px 40px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.08)',
			},
			'.card-float:active': {
				'transform': 'translateY(-1px) scale(0.98)',
				'box-shadow': '0 4px 12px rgba(0,0,0,0.2)',
			},
			// ─── Switch 2 Focus Glow Ring ───────────────────────────────
			'.focus-glow': {
				'outline': 'none',
				'transition': 'box-shadow 0.2s ease-out, outline-offset 0.15s ease-out',
			},
			'.focus-glow:focus-visible': {
				'outline': '2px solid var(--gv2-accent, #2563eb)',
				'outline-offset': '3px',
				'box-shadow': '0 0 0 4px rgba(var(--gv2-accent-rgb, 37,99,235), 0.3), 0 0 20px rgba(var(--gv2-accent-rgb, 37,99,235), 0.15)',
			},
			// ─── Switch 2 Depth Transition ──────────────────────────────
			'.depth-enter': {
				'animation': 'depth-zoom-in 0.32s cubic-bezier(0.34, 1.56, 0.64, 1) both',
			},
			'.depth-exit': {
				'animation': 'depth-zoom-out 0.25s ease-out both',
			},
			// ─── Glow Indicator ─────────────────────────────────────────
			'.glow-indicator': {
				'box-shadow': '0 0 8px 2px var(--gv2-accent, #2563eb)',
				'transition': 'box-shadow 0.3s ease-out',
			},
			// ─── Pulse Badge ────────────────────────────────────────────
			'.pulse-badge': {
				'animation': 'pulse-scale 2s ease-in-out infinite',
			},
			// ─── Switch 2 Interactive Press ─────────────────────────────
			'.press-scale': {
				'transition': 'transform 0.1s ease-out',
				'touch-action': 'manipulation',
			},
			'.press-scale:active': {
				'transform': 'scale(0.95)',
			},
			// ─── Switch 2 Glow Button ───────────────────────────────────
			'.btn-glow': {
				'transition': 'box-shadow 0.2s ease-out, transform 0.1s ease-out',
				'touch-action': 'manipulation',
			},
			'.btn-glow:hover, .btn-glow:focus-visible': {
				'box-shadow': '0 4px 16px rgba(var(--gv2-accent-rgb, 37,99,235), 0.3)',
			},
			'.btn-glow:active': {
				'transform': 'scale(0.95)',
				'box-shadow': '0 2px 8px rgba(var(--gv2-accent-rgb, 37,99,235), 0.2)',
			},
			// ─── Switch 2 Glow Tab Underline ────────────────────────────
			'.tab-glow-underline': {
				'position': 'absolute',
				'bottom': '0',
				'left': '8px',
				'right': '8px',
				'height': '3px',
				'border-radius': '9999px',
				'background': 'var(--gv2-accent, #2563eb)',
				'box-shadow': '0 0 8px 1px var(--gv2-accent, #2563eb)',
			},
			// ─── Switch 2 Item Stagger Enter ────────────────────────────
			'.stagger-enter': {
				'animation': 'stagger-slide-in 0.3s ease-out both',
			},
			// ─── Switch 2 Input Focus Glow ──────────────────────────────
			'.input-glow': {
				'transition': 'box-shadow 0.2s ease-out, border-color 0.2s ease-out',
			},
			'.input-glow:focus': {
				'border-color': 'var(--gv2-accent, #2563eb)',
				'box-shadow': '0 0 0 3px rgba(var(--gv2-accent-rgb, 37,99,235), 0.15), 0 0 12px rgba(var(--gv2-accent-rgb, 37,99,235), 0.1)',
				'outline': 'none',
			},
			// ─── Switch 2 Shimmer Skeleton ──────────────────────────────
			'.shimmer': {
				'position': 'relative',
				'overflow': 'hidden',
			},
			'.shimmer::after': {
				'content': '""',
				'position': 'absolute',
				'inset': '0',
				'background': 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 40%, rgba(255,255,255,0.06) 60%, transparent 100%)',
				'animation': 'shimmer-sweep 1.8s ease-in-out infinite',
			},
			// ─── Reduced Motion Override ─────────────────────────────────
			'@media (prefers-reduced-motion: reduce)': {
				'.card-float, .card-float:hover, .card-float:focus-visible, .card-float:active': {
					'transform': 'none',
					'transition': 'none',
				},
				'.depth-enter, .depth-exit, .stagger-enter': {
					'animation': 'none',
				},
				'.pulse-badge': {
					'animation': 'none',
				},
				'.shimmer::after': {
					'animation': 'none',
					'display': 'none',
				},
				'.press-scale:active, .btn-glow:active': {
					'transform': 'none',
				},
			},
		});
	},
	{
		theme: {
			extend: {
				colors: {
					// Discord brand colors used in UI components
					'discord-accent': '#5865F2',
					'discord-accent-hover': '#4752C4',
					'discord-green': '#3BA55D',
					// gv2 design token aliases — Tailwind utility → CSS custom property
					'gv2-bg-primary': 'var(--gv2-bg-primary)',
					'gv2-bg-secondary': 'var(--gv2-bg-sidebar)',
					'gv2-bg-sidebar': 'var(--gv2-bg-sidebar)',
					'gv2-bg-card': 'var(--gv2-bg-card)',
					'gv2-bg-hover': 'var(--gv2-bg-hover)',
					'gv2-bg-input': 'var(--gv2-bg-input)',
					'gv2-text-primary': 'var(--gv2-text-primary)',
					'gv2-text-secondary': 'var(--gv2-text-secondary)',
					'gv2-text-muted': 'var(--gv2-text-muted)',
					'gv2-border': 'var(--gv2-border)',
					'gv2-accent': 'var(--gv2-accent)',
					'gv2-accent-hover': 'var(--gv2-accent-hover)'
				},
				keyframes: {
					'depth-zoom-in': {
						'0%': { transform: 'scale(1.06)', opacity: '0', filter: 'blur(0px)' },
						'100%': { transform: 'scale(1)', opacity: '1', filter: 'blur(0px)' },
					},
					'depth-zoom-out': {
						'0%': { transform: 'scale(1)', opacity: '1', filter: 'blur(0px)' },
						'100%': { transform: 'scale(0.94)', opacity: '0', filter: 'blur(4px)' },
					},
					'pulse-scale': {
						'0%, 100%': { transform: 'scale(1)' },
						'50%': { transform: 'scale(1.15)' },
					},
					'stagger-slide-in': {
						'0%': { opacity: '0', transform: 'translateY(8px)' },
						'100%': { opacity: '1', transform: 'translateY(0)' },
					},
					'shimmer-sweep': {
						'0%': { transform: 'translateX(-100%)' },
						'100%': { transform: 'translateX(100%)' },
					},
				},
				animation: {
					'depth-in': 'depth-zoom-in 0.32s cubic-bezier(0.34, 1.56, 0.64, 1) both',
					'depth-out': 'depth-zoom-out 0.25s ease-out both',
					'pulse-badge': 'pulse-scale 2s ease-in-out infinite',
					'stagger-in': 'stagger-slide-in 0.3s ease-out both',
					'shimmer': 'shimmer-sweep 1.8s ease-in-out infinite',
				},
			}
		}
	}
);
