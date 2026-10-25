<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAnchorAttributes } from 'svelte/elements';
  import { paginationItemStyle } from './styles';

  interface Props extends HTMLAnchorAttributes {}

  let { class: className, 'aria-label': ariaLabel, ...rest }: Props = $props();
</script>

<a class={cn(paginationItemStyle, className)} {...rest}>
  <svg
    aria-label={ariaLabel ?? '次のページへ進む'}
    fill='none'
    height='24'
    role='img'
    viewBox='0 0 24 24'
    width='24'
  >
    <path
      class='fill-blue-900'
      d='M8.67 19L8 18.33L14.33 12L8 5.67L8.67 5L15.67 12L8.67 19Z'
    />
  </svg>
</a>
