<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  interface Props extends HTMLButtonAttributes {
    label?: string;
  }

  let { class: className, label, ...rest }: Props = $props();
</script>

<button
  class={cn(
    "-mr-3 inline-flex items-center self-start gap-1 rounded-6 px-3 pb-1.5 pt-1 text-gv2-text-primary",
    "hover:bg-gv2-bg-hover hover:underline hover:underline-offset-[calc(3/16*1rem)]",
    "focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:outline-gv2-text-primary focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
    className
  )}
  type='button'
  {...rest}
>
  <svg
    aria-hidden={true}
    class='mt-0.5 size-6'
    fill='none'
    height='24'
    viewBox='0 0 24 24'
    width='24'
  >
    <g>
      <path
        d='m6.4 18.6-1-1 5.5-5.6-5.6-5.6 1.1-1 5.6 5.5 5.6-5.6 1 1.1L13 12l5.6 5.6-1 1L12 13l-5.6 5.6Z'
        fill='currentColor'
      />
    </g>
  </svg>
  <span class='text-oln-16N-100'>{label ?? '閉じる'}</span>
</button>
