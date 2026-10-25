<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<dt
  class={cn(
    "font-bold group-data-[marker=bullet]/dl:ml-8 group-data-[marker=bullet]/dl:list-item group-data-[marker=bullet]/dl:list-disc",
    className
  )}
  {...rest}
>
  {@render children?.()}
</dt>
