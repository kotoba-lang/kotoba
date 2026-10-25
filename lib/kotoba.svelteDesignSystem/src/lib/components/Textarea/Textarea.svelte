<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLTextareaAttributes } from 'svelte/elements';

  interface Props extends HTMLTextareaAttributes {
    isError?: boolean;
  }

  let { 
    class: className, 
    isError, 
    readonly: readOnlyAttr,
    value = $bindable(),
    ...rest 
  }: Props = $props();

  const actualReadOnly = $derived(rest['aria-disabled'] ? true : readOnlyAttr);
</script>

<textarea
  bind:value
  class={cn(
    "max-w-full rounded-8 border bg-gv2-bg-input p-4 border-gv2-border text-std-16N-170 text-gv2-text-primary",
    "hover:[&:read-write]:border-gv2-text-primary",
    "focus:outline focus:outline-4 focus:outline-gv2-text-primary focus:outline-offset-[calc(2/16*1rem)] focus:ring-[calc(2/16*1rem)] focus:ring-yellow-300",
    "read-only:border-dashed",
    "aria-disabled:border-solid-gray-300 read-only:aria-disabled:border-solid aria-disabled:bg-solid-gray-50 aria-disabled:text-solid-gray-420 aria-disabled:pointer-events-none aria-disabled:forced-colors:text-[GrayText] aria-disabled:forced-colors:border-[GrayText]",
    isError && "border-error-1 [&:read-write]:hover:border-red-1000",
    className
  )}
  aria-invalid={isError || undefined}
  readonly={actualReadOnly}
  {...rest}
></textarea>
