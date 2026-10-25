<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLAnchorAttributes } from 'svelte/elements';

  interface Props extends HTMLAnchorAttributes {
    current?: boolean;
    children?: import('svelte').Snippet;
  }

  let { current = false, class: className, children, ...rest }: Props = $props();
</script>

<a
  aria-current={current ? 'page' : undefined}
  class={cn(
    'flex h-12 w-12 items-center justify-center rounded-full border text-oln-16N-100',
    current
      ? 'border-blue-900 bg-blue-900 text-white pointer-events-none'
      : 'border-solid-gray-200 text-blue-1000 hover:border-blue-900 hover:bg-blue-50 active:border-blue-900 active:bg-blue-50',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-yellow',
    className
  )}
  {...rest}
>
  {@render children?.()}
</a>
