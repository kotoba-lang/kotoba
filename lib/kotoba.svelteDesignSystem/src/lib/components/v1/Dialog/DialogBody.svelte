<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();

  function handleClick(e: MouseEvent) {
    e.stopPropagation();
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
  class={cn(
    "flex flex-col items-center gap-4 rounded-12 border border-solid-gray-200 bg-white p-6 desktop:p-10",
    className
  )}
  onclick={handleClick}
  {...rest}
>
  {@render children?.()}
</div>
