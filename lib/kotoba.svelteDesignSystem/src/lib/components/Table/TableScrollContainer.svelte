<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();

  let containerEl: HTMLDivElement | undefined = $state();
  let hasLeftShadow = $state(false);
  let hasRightShadow = $state(false);

  function updateShadow() {
    if (!containerEl) return;
    const { scrollLeft, scrollWidth, clientWidth } = containerEl;
    hasLeftShadow = scrollLeft > 0;
    hasRightShadow = scrollLeft + clientWidth < scrollWidth - 1;
  }

  $effect(() => {
    if (!containerEl) return;
    updateShadow();
    containerEl.addEventListener('scroll', updateShadow);
    const ro = new ResizeObserver(updateShadow);
    ro.observe(containerEl);
    return () => {
      containerEl?.removeEventListener('scroll', updateShadow);
      ro.disconnect();
    };
  });
</script>

<div class="relative" {...rest}>
  {#if hasLeftShadow}
    <div
      class="pointer-events-none absolute left-0 top-0 z-10 h-full w-6 bg-gradient-to-r from-black/25 to-transparent transition-opacity duration-300"
      aria-hidden="true"
    ></div>
  {/if}
  {#if hasRightShadow}
    <div
      class="pointer-events-none absolute right-0 top-0 z-10 h-full w-6 bg-gradient-to-l from-black/25 to-transparent transition-opacity duration-300"
      aria-hidden="true"
    ></div>
  {/if}
  <div
    bind:this={containerEl}
    class={cn('overflow-x-auto', className)}
  >
    {@render children?.()}
  </div>
</div>
