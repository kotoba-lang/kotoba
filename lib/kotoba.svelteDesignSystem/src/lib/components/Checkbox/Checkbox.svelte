<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLInputAttributes } from 'svelte/elements';

  export type CheckboxSize = 'sm' | 'md' | 'lg';

  interface Props extends Omit<HTMLInputAttributes, 'size'> {
    size?: CheckboxSize;
    isError?: boolean;
    children?: import('svelte').Snippet;
    indeterminate?: boolean;
  }

  let { 
    class: className, 
    size = 'sm', 
    isError, 
    children, 
    indeterminate = false,
    ...rest 
  }: Props = $props();

  let inputRef: HTMLInputElement | undefined = $state();

  $effect(() => {
    if (inputRef) {
      inputRef.indeterminate = indeterminate;
    }
  });

  function handleDisabled(e: MouseEvent) {
    if (rest['aria-disabled']) {
      e.preventDefault();
    }
  }
</script>

{#snippet checkboxSnippet()}
  <span
    class={cn(
      "flex items-center justify-center shrink-0 rounded-[calc(1/8*100%)]",
      "has-[input:hover:not(:focus):not([aria-disabled='true'])]:bg-solid-gray-420",
      size === 'sm' && "size-6",
      size === 'md' && "size-8",
      size === 'lg' && "size-11"
    )}
    data-size={size}
  >
    <input
      bind:this={inputRef}
      class={cn(
        "appearance-none size-3/4 rounded-[calc(2/18*100%)] border-gv2-border bg-gv2-bg-input bg-clip-padding",
        "hover:border-gv2-text-primary",
        "focus:outline focus:outline-4 focus:outline-gv2-text-primary focus:outline-offset-[calc(2/16*1rem)] focus:ring-[calc(2/16*1rem)] focus:ring-yellow-300",
        "checked:border-blue-900 checked:bg-blue-900 checked:hover:border-blue-1100 checked:hover:bg-blue-1100",
        "indeterminate:border-blue-900 indeterminate:bg-blue-900 indeterminate:hover:border-blue-1100 indeterminate:hover:bg-blue-1100",
        "before:hidden before:size-3.5 before:bg-white",
        "checked:before:block checked:before:[clip-path:path('M5.6,11.2L12.65,4.15L11.25,2.75L5.6,8.4L2.75,5.55L1.35,6.95L5.6,11.2Z')]",
        "indeterminate:before:block indeterminate:before:[clip-path:path('M3.25,7.75H10.75V6.25H3.25V7.75Z')]",
        size === 'sm' && "border-[calc(2/16*1rem)]",
        size === 'md' && "border-[calc(2/16*1rem)] before:origin-top-left before:scale-[calc(20/14)]",
        size === 'lg' && "border-[calc(3/16*1rem)] before:origin-top-left before:scale-[calc(27/14)]",
        isError && "border-error-1 hover:border-red-1000 checked:bg-error-1 checked:hover:bg-red-1000 indeterminate:bg-error-1 indeterminate:hover:bg-red-1000",
        "aria-disabled:!border-solid-gray-300 aria-disabled:!bg-solid-gray-50 aria-disabled:checked:!bg-solid-gray-300 aria-disabled:indeterminate:!bg-solid-gray-300 aria-disabled:before:border-solid-gray-50",
        "forced-colors:!border-[ButtonText] forced-colors:checked:!bg-[Highlight] forced-colors:checked:!border-[Highlight] forced-colors:indeterminate:!bg-[Highlight] forced-colors:indeterminate:!border-[Highlight] forced-colors:before:!bg-[HighlightText] forced-colors:aria-disabled:!border-[GrayText] forced-colors:aria-disabled:checked:!bg-[GrayText]"
      )}
      onclick={handleDisabled}
      type='checkbox'
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
      size === 'lg' && "gap-2",
      className
    )}
    data-size={size}
  >
    {@render checkboxSnippet()}
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
  {@render checkboxSnippet()}
{/if}
