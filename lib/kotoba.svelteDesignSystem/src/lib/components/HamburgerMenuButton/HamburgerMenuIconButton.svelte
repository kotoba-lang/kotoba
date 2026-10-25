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
    "block w-fit rounded-4 p-0 text-black touch-manipulation",
    "hover:outline-1 hover:bg-solid-gray-50",
    "focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:outline-black focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
    className
  )}
  type='button'
  {...rest}
>
  {@render children?.()}
</button>
