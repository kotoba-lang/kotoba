<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLAnchorAttributes } from 'svelte/elements';

  interface Props extends HTMLAnchorAttributes {
    direction: 'prev' | 'next' | 'first' | 'last';
    disabled?: boolean;
    children?: import('svelte').Snippet;
  }

  let { direction, disabled = false, class: className, children, ...rest }: Props = $props();

  const labels: Record<string, string> = {
    first: '最初のページ',
    prev: '前のページ',
    next: '次のページ',
    last: '最後のページ',
  };

  const icons: Record<string, string> = {
    first: 'M11 4 5 8l6 4M19 4l-6 4 6 4',
    prev: 'M15 4 9 8l6 4',
    next: 'M9 4l6 4-6 4',
    last: 'M9 4l6 4-6 4M5 4l6 4-6 4',
  };
</script>

<a
  aria-label={rest['aria-label'] ?? labels[direction]}
  aria-disabled={disabled || undefined}
  class={cn(
    'flex h-12 w-12 items-center justify-center rounded-full border border-solid-gray-200 text-oln-16N-100 text-blue-1000',
    !disabled && 'hover:border-blue-900 hover:bg-blue-50 active:border-blue-900 active:bg-blue-50',
    disabled && 'pointer-events-none border-solid-gray-200 text-solid-gray-300',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-yellow',
    className
  )}
  {...rest}
>
  {#if children}
    {@render children()}
  {:else}
    <svg width="16" height="16" viewBox="0 0 24 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
      <path d={icons[direction]}/>
    </svg>
  {/if}
</a>
