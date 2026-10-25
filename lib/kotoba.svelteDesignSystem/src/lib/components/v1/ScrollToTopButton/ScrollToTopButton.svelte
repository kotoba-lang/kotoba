<script lang="ts">
  import { cn } from '$lib/utils';
  import { scrollToTopButtonStyle } from './styles';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  interface Props extends HTMLButtonAttributes {}

  let { class: className, 'aria-label': ariaLabel, ...rest }: Props = $props();
</script>

<button type='button' class={cn(scrollToTopButtonStyle, className)} {...rest}>
  <svg
    aria-label={ariaLabel ?? 'ページの先頭へ戻る'}
    fill='none'
    height='16'
    role='img'
    viewBox='0 0 15 16'
    width='15'
  >
    <path
      d='M6.75 15.5L6.75 3.37303L1.05383 9.06918L0 7.99998L7.49997 0.5L15 7.99998L13.9461 9.06918L8.24995 3.37303L8.24995 15.5H6.75Z'
      fill='currentColor'
    />
  </svg>
</button>
