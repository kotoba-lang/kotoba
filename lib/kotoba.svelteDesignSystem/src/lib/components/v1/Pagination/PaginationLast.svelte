<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAnchorAttributes } from 'svelte/elements';
  import { paginationItemStyle } from './styles';

  interface Props extends HTMLAnchorAttributes {}

  let { class: className, 'aria-label': ariaLabel, ...rest }: Props = $props();
</script>

<a class={cn(paginationItemStyle, className)} {...rest}>
  <svg
    aria-label={ariaLabel ?? '最後のページに移動する'}
    class='-scale-x-100'
    fill='none'
    height='24'
    role='img'
    viewBox='0 0 24 24'
    width='24'
  >
    <path
      class='fill-blue-900'
      d='M18.33 19L19 18.33L12.67 12L19 5.67L18.33 5L11.33 12L18.33 19Z'
    />
    <rect
      class='fill-blue-900'
      height='14'
      transform='matrix(1, 8.74228e-08, 8.74228e-08, -1, 6, 19)'
      width='1'
    />
  </svg>
</a>
