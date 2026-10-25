<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDetailsElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<details
  class={cn(
    "group/accordion border-b border-solid-gray-420",
    "[--icon-size:calc(20/16*1rem)] desktop:[--icon-size:calc(32/16*1rem)]",
    className
  )}
  {...(rest as any)}
>
  {@render children?.()}
</details>
