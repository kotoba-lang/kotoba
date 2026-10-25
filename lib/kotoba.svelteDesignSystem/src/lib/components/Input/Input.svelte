<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLInputAttributes } from 'svelte/elements';

  export type InputBlockSize = 'lg' | 'md' | 'sm';

  interface Props extends HTMLInputAttributes {
    isError?: boolean;
    blockSize?: InputBlockSize;
  }

  let { 
    class: className, 
    readonly: readOnlyAttr,
    isError, 
    blockSize = 'lg', 
    value = $bindable(),
    ...rest 
  }: Props = $props();

  const actualReadOnly = $derived(rest['aria-disabled'] ? true : readOnlyAttr);
</script>

<input
  bind:value
  class={cn(
    "max-w-full rounded-8 border bg-gv2-bg-input px-4 py-3 border-gv2-border text-oln-16N-100 text-gv2-text-primary",
    "hover:[&:read-write]:border-gv2-text-primary",
    "focus:outline focus:outline-4 focus:outline-gv2-text-primary focus:outline-offset-[calc(2/16*1rem)] focus:ring-[calc(2/16*1rem)] focus:ring-yellow-300",
    "read-only:border-dashed",
    "aria-disabled:border-solid-gray-300 aria-disabled:!border-solid aria-disabled:bg-solid-gray-50 aria-disabled:text-solid-gray-420 aria-disabled:pointer-events-none aria-disabled:forced-colors:text-[GrayText] aria-disabled:forced-colors:border-[GrayText]",
    blockSize === 'sm' && "h-10",
    blockSize === 'md' && "h-12",
    blockSize === 'lg' && "h-14",
    isError && "border-error-1 [&:read-write]:hover:border-red-1000",
    className
  )}
  aria-invalid={isError || undefined}
  data-size={blockSize}
  readonly={actualReadOnly}
  {...rest}
/>
