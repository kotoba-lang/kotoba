<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLDialogAttributes } from 'svelte/elements';

  interface Props extends HTMLDialogAttributes {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();

  let dialogRef: HTMLDialogElement | undefined = $state();

  function handleClick(e: MouseEvent) {
    if (dialogRef) {
      dialogRef.close();
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<dialog
  bind:this={dialogRef}
  class={cn("bg-transparent p-6 backdrop:bg-black/45", className)}
  onclick={handleClick}
  {...rest}
>
  {@render children?.()}
</dialog>
