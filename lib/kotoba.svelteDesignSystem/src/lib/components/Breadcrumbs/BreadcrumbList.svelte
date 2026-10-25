<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLOListElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<ol class={cn("inline", className)} {...rest}>
  {@render children?.()}
</ol>
