<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLLIElement> {
    isCurrent?: boolean;
    children?: import('svelte').Snippet;
  }

  let { isCurrent = false, children, class: className, ...rest }: Props = $props();
</script>

{#if isCurrent}
  <li
    aria-current='page'
    class={cn("inline break-words text-oln-16N-100", className)}
    {...rest}
  >
    {@render children?.()}
  </li>
{:else}
  <li class={cn("inline break-words", className)} {...rest}>
    {@render children?.()}
    <svg
      aria-hidden={true}
      class='mx-2 inline'
      fill='none'
      height='12'
      viewBox='0 0 12 12'
      width='12'
    >
      <path
        d='M4.50078 1.2998L3.80078 1.9998L7.80078 5.9998L3.80078 9.9998L4.50078 10.6998L9.20078 5.9998L4.50078 1.2998Z'
        fill='currentColor'
      />
    </svg>
  </li>
{/if}
