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
    "col-start-1 -col-end-1 desktop:col-start-2 text-std-16N-170 text-gv2-text-primary grid gap-y-2",
    className
  )}
  {...rest}
>
  {@render children?.()}
</div>
