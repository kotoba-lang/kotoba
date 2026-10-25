<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<nav
  aria-label={`${rest['aria-label'] ?? 'ページナビゲーション'}`}
  class={cn("flex flex-wrap items-center gap-3", className)}
  {...rest}
>
  {@render children?.()}
</nav>
