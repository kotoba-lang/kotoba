<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<blockquote
  class={cn(
    "border-l-8 border-solid-gray-536 py-2 pl-6 pr-4 mx-10 [&>*:first-child]:!mt-0 [&>*:last-child]:!mb-0",
    className
  )}
  {...rest}
>
  {@render children?.()}
</blockquote>
