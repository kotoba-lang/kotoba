<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<div
  class={cn('flex items-center justify-between border-b border-solid-gray-200 px-6 py-4', className)}
  {...rest}
>
  {@render children?.()}
</div>
