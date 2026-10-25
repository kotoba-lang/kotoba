<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  export type LegendSize = 'lg' | 'md' | 'sm';

  interface Props extends HTMLAttributes<HTMLLegendElement> {
    size?: LegendSize;
    children?: import('svelte').Snippet;
  }

  let { class: className, size = 'md', children, ...rest }: Props = $props();
</script>

<legend
  class={cn(
    "flex w-fit items-center gap-2 text-gv2-text-primary",
    size === 'sm' && "text-std-16B-170",
    size === 'md' && "text-std-17B-170",
    size === 'lg' && "text-std-18B-160",
    className
  )}
  data-size={size}
  {...rest}
>
  {@render children?.()}
</legend>
