<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLSpanElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<span
  class={cn(
    "ml-2 inline-block rounded-lg bg-solid-gray-536 p-2 text-oln-16N-100 text-white outline-1 outline-transparent",
    className
  )}
  {...rest}
>
  {@render children?.()}
</span>
