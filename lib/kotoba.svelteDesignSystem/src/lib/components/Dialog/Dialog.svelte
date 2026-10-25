<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLDialogAttributes } from 'svelte/elements';

  interface Props extends HTMLDialogAttributes {
    el?: HTMLDialogElement;
    /** モーダルを閉じる際のコールバック */
    onclose?: () => void;
    children?: import('svelte').Snippet;
  }

  let { el = $bindable(), class: className, onclose, children, ...rest }: Props = $props();

  function handleBackdropClick(e: MouseEvent) {
    if (el && e.target === el) {
      el.close();
      onclose?.();
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<dialog
  bind:this={el}
  class={cn(
    'w-full max-w-lg rounded-8 p-0 bg-white shadow-4',
    'backdrop:bg-black/45',
    'm-auto',
    className
  )}
  onclick={handleBackdropClick}
  {...rest}
>
  {@render children?.()}
</dialog>
