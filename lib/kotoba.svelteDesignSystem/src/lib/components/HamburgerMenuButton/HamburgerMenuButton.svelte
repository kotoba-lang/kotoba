<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  interface Props extends HTMLButtonAttributes {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<button
  class={cn(
    "flex w-fit touch-manipulation items-center gap-x-1 rounded-6 px-3 pb-1.5 pt-1 text-oln-16N-100",
    "hover:bg-solid-gray-50 hover:underline hover:underline-offset-[calc(3/16*1rem)]",
    "focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:outline-black focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
    className
  )}
  type='button'
  {...rest}
>
  {@render children?.()}
</button>
