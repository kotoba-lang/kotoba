<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLDialogAttributes } from 'svelte/elements';

  type DrawerVariant = 'full' | 'right' | 'left';

  interface Props extends HTMLDialogAttributes {
    variant?: DrawerVariant;
    el?: HTMLDialogElement;
    children?: import('svelte').Snippet;
  }

  let { variant = 'right', el = $bindable(), class: className, children, ...rest }: Props = $props();

  const variantClasses: Record<DrawerVariant, string> = {
    full: 'm-[unset] max-w-[unset] max-h-[unset] w-full h-dvh bg-white [scrollbar-gutter:stable]',
    right: 'm-[unset] max-w-full max-h-[unset] w-72 h-dvh start-auto bg-white shadow-2 border-l border-l-transparent [scrollbar-gutter:stable] backdrop:bg-opacity-gray-100 forced-colors:backdrop:bg-[#000b]',
    left: 'm-[unset] max-w-full max-h-[unset] w-72 h-dvh end-auto bg-white shadow-2 border-r border-r-transparent [scrollbar-gutter:stable] backdrop:bg-opacity-gray-100 forced-colors:backdrop:bg-[#000b]',
  };
</script>

<dialog
  bind:this={el}
  class={cn(variantClasses[variant], className)}
  {...rest}
>
  {@render children?.()}
</dialog>
