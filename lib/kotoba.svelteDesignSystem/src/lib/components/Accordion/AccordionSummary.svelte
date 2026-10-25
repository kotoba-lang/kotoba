<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<summary
  class={cn(
    "group/summary relative block cursor-default py-2 pl-[calc(var(--icon-size)+(12/16*1rem))] pr-2",
    "marker:[content:'']",
    "hover:bg-gv2-bg-hover focus-visible:rounded-4 focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:outline-gv2-text-primary focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
    "desktop:py-3.5 desktop:pl-[calc(var(--icon-size)+(20/16*1rem))] desktop:pr-4",
    "[&::-webkit-details-marker]:hidden",
    className
  )}
  {...rest}
>
  <span
    class={cn(
      "absolute top-2 left-0.5 inline-flex items-center justify-center size-[var(--icon-size)] mt-[calc((1lh-var(--icon-size))/2)] border border-current bg-gv2-bg-input text-blue-1000 rounded-full",
      "desktop:top-3.5 desktop:left-1.5",
      "group-hover/summary:outline group-hover/summary:outline-2 group-hover/summary:outline-current",
      "group-open/accordion:rotate-180"
    )}
  >
    <svg
      aria-hidden={true}
      class='pointer-events-none mt-0.5 size-4 desktop:size-auto'
      width='20'
      height='20'
      viewBox='0 0 20 20'
      fill='none'
    >
      <g>
        <path
          d='M16.668 5.5L10.0013 12.1667L3.33464 5.5L2.16797 6.66667L10.0013 14.5L17.8346 6.66667L16.668 5.5Z'
          fill='currentColor'
        />
      </g>
    </svg>
  </span>
  {@render children?.()}
</summary>
