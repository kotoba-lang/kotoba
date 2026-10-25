<script lang="ts">
  import { cn } from '../../utils.js';
  import { spring } from 'svelte/motion';
  import { playTap, haptic } from '../../audio/ui-sounds.js';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  interface Props extends HTMLButtonAttributes {}

  let { class: className, 'aria-label': ariaLabel, onclick, ...rest }: Props = $props();

  const scale = spring(1, { stiffness: 0.35, damping: 0.55 });

  function handleClick(e: MouseEvent) {
    playTap();
    haptic('light');
    scale.set(0.88);
    setTimeout(() => scale.set(1.04), 80);
    setTimeout(() => scale.set(1), 180);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    (onclick as ((e: MouseEvent) => void) | undefined)?.(e);
  }
</script>

<button
  type="button"
  aria-label={ariaLabel ?? 'ページの先頭へ戻る'}
  class={cn(
    'flex h-14 w-14 cursor-pointer items-center justify-center rounded-full border border-blue-900 bg-white text-blue-900',
    'hover:border-blue-1000 hover:bg-blue-200 hover:text-blue-1000',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus-yellow',
    'active:border-blue-1200 active:bg-blue-300 active:text-blue-1200',
    className
  )}
  style="transform: scale({$scale})"
  onclick={handleClick}
  {...rest}
>
  <svg
    aria-hidden="true"
    fill="none"
    height="16"
    viewBox="0 0 15 16"
    width="15"
  >
    <path
      d="M6.75 15.5L6.75 3.37303L1.05383 9.06918L0 7.99998L7.49997 0.5L15 7.99998L13.9461 9.06918L8.24995 3.37303L8.24995 15.5H6.75Z"
      fill="currentColor"
    />
  </svg>
</button>
