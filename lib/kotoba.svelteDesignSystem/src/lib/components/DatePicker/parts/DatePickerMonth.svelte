<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLInputAttributes } from 'svelte/elements';

  interface Props extends HTMLInputAttributes {
    bindRef?: (el: HTMLInputElement) => void;
  }

  let { class: className, 'aria-disabled': ariaDisabled, readonly: readOnlyAttr, bindRef, ...rest }: Props = $props();

  let inputEl: HTMLInputElement | undefined = $state();
  $effect(() => {
    if (inputEl && bindRef) bindRef(inputEl);
  });
</script>

<label class='relative z-0 inline-flex flex-row-reverse last:pe-4 [&:has([aria-disabled="true"])]:pointer-events-none'>
  <span class='relative z-10 self-center bg-[--bg] p-1 text-oln-16N-100'>月</span>
  <input
    bind:this={inputEl}
    class={cn(
      "-me-1 w-11 rounded-8 border border-transparent bg-transparent pe-3 text-right focus:border-gv2-border focus:outline focus:outline-4 focus:outline-offset-[calc(2/16*1rem)] focus:outline-gv2-text-primary focus:ring-[calc(2/16*1rem)] focus:ring-yellow-300 aria-disabled:pointer-events-none forced-colors:border-[Canvas] forced-colors:aria-disabled:focus:border-[GrayText]",
      className
    )}
    type='text'
    inputmode='numeric'
    pattern='\d+'
    readonly={ariaDisabled === 'true' || ariaDisabled === true || readOnlyAttr}
    aria-disabled={ariaDisabled}
    {...rest}
  />
</label>
