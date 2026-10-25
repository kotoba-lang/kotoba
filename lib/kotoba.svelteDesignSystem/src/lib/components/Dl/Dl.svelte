<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDListElement> {
    marker?: 'none' | 'bullet';
    children?: import('svelte').Snippet;
  }

  let { class: className, marker, children, ...rest }: Props = $props();
</script>

<dl 
  class={cn("group/dl grid gap-y-2", className)} 
  data-marker={marker} 
  {...rest}
>
  {@render children?.()}
</dl>
