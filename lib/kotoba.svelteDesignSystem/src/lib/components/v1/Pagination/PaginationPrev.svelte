<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAnchorAttributes } from 'svelte/elements';
  import { paginationItemStyle } from './styles';

  interface Props extends HTMLAnchorAttributes {}

  let { class: className, 'aria-label': ariaLabel, ...rest }: Props = $props();
</script>

<a class={cn(paginationItemStyle, className)} {...rest}>
  <svg
    aria-label={ariaLabel ?? '前のページへ戻る'}
    fill='none'
    height='24'
    role='img'
    viewBox='0 0 24 24'
    width='24'
  >
    <path d='M15.33 19L16 18.33L9.67 12L16 5.67L15.33 5L8.33 12L15.33 19Z' fill='#1A3EE8' />
  </svg>
</a>
