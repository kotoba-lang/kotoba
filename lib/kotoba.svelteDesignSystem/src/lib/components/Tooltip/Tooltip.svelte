<script lang="ts">
  import { cn } from '../../utils.js';
  import type { Snippet } from 'svelte';

  type TooltipPlacement = 'top' | 'bottom' | 'left' | 'right';

  interface Props {
    label: string;
    placement?: TooltipPlacement;
    class?: string;
    triggerClass?: string;
    children?: Snippet;
  }

  let { label, placement = 'top', class: className, triggerClass, children }: Props = $props();

  let visible = $state(false);
  let tooltipId = $state(`tooltip-${Math.random().toString(36).slice(2, 9)}`);

  const placementClasses: Record<TooltipPlacement, string> = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<span
  class={cn('relative inline-flex', triggerClass)}
  onmouseenter={() => (visible = true)}
  onmouseleave={() => (visible = false)}
  onfocusin={() => (visible = true)}
  onfocusout={() => (visible = false)}
>
  <span aria-describedby={tooltipId}>
    {@render children?.()}
  </span>

  {#if visible}
    <span
      id={tooltipId}
      role="tooltip"
      class={cn(
        'pointer-events-none absolute z-50 whitespace-nowrap rounded-4 bg-solid-gray-900 px-3 py-1.5',
        'text-white text-oln-14N-100 shadow-2',
        placementClasses[placement],
        className
      )}
    >
      {label}
    </span>
  {/if}
</span>
