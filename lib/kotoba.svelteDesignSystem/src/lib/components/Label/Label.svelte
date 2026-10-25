<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLLabelAttributes } from 'svelte/elements';

  export type LabelSize = 'lg' | 'md' | 'sm';

  interface Props extends HTMLLabelAttributes {
    size?: LabelSize;
    children?: import('svelte').Snippet;
  }

  let { class: className, size = 'md', children, ...rest }: Props = $props();
</script>

<label
  class={cn(
    "text-gv2-text-primary",
    size === 'sm' && "text-std-16B-170",
    size === 'md' && "text-std-17B-170",
    size === 'lg' && "text-std-18B-160",
    className
  )}
  data-size={size}
  {...rest}
>
  {@render children?.()}
</label>
