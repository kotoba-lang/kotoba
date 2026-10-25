<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLSpanElement> {
    isOptional?: boolean;
    children?: import('svelte').Snippet;
  }

  let { class: className, isOptional, children, ...rest }: Props = $props();
</script>

<span
  class={cn(
    "ml-2 inline-block text-oln-16N-100 text-red-800",
    isOptional && "text-solid-gray-800",
    className
  )}
  data-is-optional={isOptional || undefined}
  {...rest}
>
  {@render children?.()}
</span>
