<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLSelectAttributes } from 'svelte/elements';

  export type SelectBlockSize = 'lg' | 'md' | 'sm';

  interface Props extends HTMLSelectAttributes {
    isError?: boolean;
    blockSize?: SelectBlockSize;
    value?: HTMLSelectAttributes['value'];
    children?: import('svelte').Snippet;
  }

  let { 
    class: className, 
    isError, 
    blockSize = 'lg', 
    value = $bindable(),
    children, 
    ...rest 
  }: Props = $props();

  function handleDisabledKeyDown(e: KeyboardEvent) {
    if (rest['aria-disabled'] && e.code !== 'Tab') {
      e.preventDefault();
    }
  }

  function handleDisabledMouseDown(e: MouseEvent) {
    if (rest['aria-disabled']) {
      e.preventDefault();
    }
  }
</script>

<span class='relative'>
  <select
    class={cn(
      "w-full appearance-none border border-gv2-border rounded-8 bg-gv2-bg-input pl-4 pr-10 py-[calc(11/16*1rem)] text-oln-16N-100 text-gv2-text-primary",
      "hover:border-gv2-text-primary",
      "focus:outline focus:outline-4 focus:outline-gv2-text-primary focus:outline-offset-[calc(2/16*1rem)] focus:ring-[calc(2/16*1rem)] focus:ring-yellow-300",
      "aria-disabled:border-solid-gray-300 aria-disabled:bg-solid-gray-50 aria-disabled:text-solid-gray-420 aria-disabled:pointer-events-none aria-disabled:forced-colors:text-[GrayText] aria-disabled:forced-colors:border-[GrayText]",
      blockSize === 'sm' && "h-10",
      blockSize === 'md' && "h-12",
      blockSize === 'lg' && "h-14",
      isError && "border-error-1 hover:border-red-1000",
      className
    )}
    aria-invalid={isError || undefined}
    data-size={blockSize}
    onmousedown={handleDisabledMouseDown}
    onkeydown={handleDisabledKeyDown}
    bind:value
    {...rest}
  >
    {@render children?.()}
  </select>
  <svg
    aria-hidden={true}
    class={cn(
      "pointer-events-none absolute right-4 top-1/2 -translate-y-1/2",
      rest['aria-disabled'] ? 'text-solid-gray-420 forced-colors:text-[GrayText]' : 'text-gv2-text-primary forced-colors:text-[CanvasText]'
    )}
    fill='none'
    height='16'
    viewBox='0 0 16 16'
    width='16'
  >
    <path
      d='M13.3344 4.40002L8.00104 9.73336L2.66771 4.40002L1.73438 5.33336L8.00104 11.6L14.2677 5.33336L13.3344 4.40002Z'
      fill='currentColor'
    />
  </svg>
</span>
