<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLInputAttributes } from 'svelte/elements';

  export type RadioSize = 'sm' | 'md' | 'lg';

  interface Props extends Omit<HTMLInputAttributes, 'size'> {
    size?: RadioSize;
    isError?: boolean;
    children?: import('svelte').Snippet;
  }

  let { 
    class: className, 
    size = 'sm', 
    isError, 
    children, 
    ...rest 
  }: Props = $props();

  function handleDisabled(e: MouseEvent) {
    if (rest['aria-disabled']) {
      e.preventDefault();
    }
  }
</script>

{#snippet radioSnippet()}
  <span
    class={cn(
      "flex items-center justify-center shrink-0 rounded-full",
      "has-[input:hover:not(:focus):not([aria-disabled='true'])]:bg-solid-gray-420",
      size === 'sm' && "size-6",
      size === 'md' && "size-8",
      size === 'lg' && "size-11"
    )}
    data-size={size}
  >
    <input
      class={cn(
        "appearance-none size-[calc(5/6*100%)] rounded-full border-gv2-border bg-gv2-bg-input",
        "hover:border-gv2-text-primary",
        "focus:outline focus:outline-4 focus:outline-gv2-text-primary focus:outline-offset-[calc(2/16*1rem)] focus:ring-[calc(2/16*1rem)] focus:ring-yellow-300",
        "checked:border-blue-900 checked:before:bg-blue-900 checked:hover:border-blue-1100 checked:hover:before:bg-blue-1100",
        "before:hidden before:size-full before:bg-white before:[clip-path:circle(calc(5/16*100%))]",
        "checked:before:block",
        size === 'sm' && "border-[calc(2/16*1rem)]",
        size === 'md' && "border-[calc(2/16*1rem)]",
        size === 'lg' && "border-[calc(3/16*1rem)]",
        isError && "border-error-1 hover:border-red-1000 checked:before:bg-error-1 checked:hover:before:bg-red-1000",
        "aria-disabled:!border-solid-gray-300 aria-disabled:!bg-solid-gray-50 aria-disabled:checked:before:!bg-solid-gray-300",
        "forced-colors:!border-[ButtonText] forced-colors:checked:!border-[Highlight] forced-colors:checked:before:!bg-[Highlight] forced-colors:aria-disabled:!border-[GrayText] forced-colors:aria-disabled:checked:before:!bg-[GrayText]"
      )}
      onclick={handleDisabled}
      type='radio'
      data-size={size}
      data-error={isError || null}
      {...rest}
    />
  </span>
{/snippet}

{#if children}
  <label
    class={cn(
      "flex w-fit items-start py-2",
      size === 'sm' && "gap-1",
      size === 'md' && "gap-2",
      size === 'lg' && "gap-3",
      className
    )}
    data-size={size}
  >
    {@render radioSnippet()}
    <span
      class={cn(
        "text-gv2-text-primary",
        size === 'sm' && "pt-px text-dns-16N-130",
        size === 'md' && "pt-1 text-dns-16N-130",
        size === 'lg' && "pt-2.5 text-dns-17N-130"
      )}
      data-size={size}
    >
      {@render children?.()}
    </span>
  </label>
{:else}
  {@render radioSnippet()}
{/if}
