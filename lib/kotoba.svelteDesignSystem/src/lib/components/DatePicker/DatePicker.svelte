<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  export type DatePickerSize = 'lg' | 'md' | 'sm';

  interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
    size?: DatePickerSize;
    isError?: boolean;
    isReadonly?: boolean;
    isDisabled?: boolean;
    children: import('svelte').Snippet<[{
      readOnly: boolean | undefined;
      'aria-disabled': boolean | undefined;
      'aria-invalid': boolean | undefined;
      onkeydown: (e: KeyboardEvent) => void;
      bindYear: (node: HTMLInputElement) => void;
      bindMonth: (node: HTMLInputElement) => void;
      bindDate: (node: HTMLInputElement) => void;
    }]>;
  }

  let { 
    class: className, 
    size = 'lg', 
    isError, 
    isReadonly, 
    isDisabled, 
    children, 
    ...rest 
  }: Props = $props();

  let yearRef: HTMLInputElement | undefined = $state();
  let monthRef: HTMLInputElement | undefined = $state();
  let dateRef: HTMLInputElement | undefined = $state();

  function handleKeyDown(event: KeyboardEvent) {
    const input = event.target as HTMLInputElement;
    if (event.key === 'ArrowRight') {
      moveRight(event, input);
    } else if (event.key === 'ArrowLeft') {
      moveLeft(event, input);
    } else if (event.key.match(/^[^0-9]$/)) {
      if (!event.ctrlKey && !event.metaKey) {
        event.preventDefault();
      }
    }
  }

  function moveRight(event: KeyboardEvent, input: HTMLInputElement) {
    if (input.selectionStart !== input.selectionEnd) {
      return;
    }
    if (input.selectionEnd === input.value.length) {
      event.preventDefault();
      if (input === yearRef) {
        monthRef?.focus();
      } else if (input === monthRef) {
        dateRef?.focus();
      }
    }
  }

  function moveLeft(event: KeyboardEvent, input: HTMLInputElement) {
    if (input.selectionStart !== input.selectionEnd) {
      return;
    }
    if (input.selectionStart === 0) {
      event.preventDefault();
      if (input === monthRef) {
        yearRef?.focus();
      } else if (input === dateRef) {
        monthRef?.focus();
      }
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class={cn(
    "inline-flex h-14 -space-x-1 rounded-8 border border-gv2-border bg-gv2-bg-input p-0.5 pe-0 text-gv2-text-primary focus-within:border-gv2-text-primary hover:border-gv2-text-secondary",
    size === 'md' && "h-12",
    size === 'sm' && "h-10",
    isReadonly && "border-dashed hover:border-solid-gray-600",
    isDisabled && "border-solid-gray-300 bg-solid-gray-50 text-solid-gray-420 forced-colors:border-[GrayText] forced-colors:text-[GrayText]",
    isError && "border-error-1 focus-within:border-red-1000 hover:border-red-1000",
    isError && isReadonly && "hover:border-error-1",
    className
  )}
  data-size={size}
  data-error={isError || null}
  data-readonly={isReadonly || null}
  data-disabled={isDisabled || null}
  onkeydown={handleKeyDown}
  {...rest}
>
  {@render children({
    readOnly: isReadonly,
    'aria-disabled': isDisabled,
    'aria-invalid': isError,
    onkeydown: handleKeyDown,
    bindYear: (el) => yearRef = el,
    bindMonth: (el) => monthRef = el,
    bindDate: (el) => dateRef = el
  })}
</div>
