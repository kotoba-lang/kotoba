<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<div
  class={cn(
    "pl-[calc(var(--icon-size)+(12/16*1rem))] pr-2 py-4",
    "desktop:pl-[calc(var(--icon-size)+(20/16*1rem))] desktop:pr-4 desktop:py-6",
    className
  )}
  {...rest}
>
  {@render children?.()}
</div>
