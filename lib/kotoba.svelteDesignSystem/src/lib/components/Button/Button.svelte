<script lang="ts">
  import { cn } from '$lib/utils';
  import { spring } from 'svelte/motion';
  import {
    buttonBaseStyle,
    buttonSizeStyle,
    buttonVariantStyle,
    type ButtonSize,
    type ButtonVariant
  } from './styles';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  import { playTap, haptic } from '../../audio/ui-sounds.js';

  interface Props extends HTMLButtonAttributes {
    variant?: ButtonVariant;
    size: ButtonSize;
    children?: import('svelte').Snippet;
    href?: string;
  }

  let {
    variant,
    size,
    class: className,
    children,
    href,
    ...rest
  }: Props = $props();

  // Duolingo-style spring press: compress → overshoot → settle
  const scale = spring(1, { stiffness: 0.35, damping: 0.55 });

  const classNames = $derived(cn(
    buttonBaseStyle,
    buttonSizeStyle[size],
    variant ? buttonVariantStyle[variant] : '',
    'focus-glow',
    className
  ));

  function handleClick(e: MouseEvent) {
    if (rest['aria-disabled']) {
      e.preventDefault();
      return;
    }
    playTap();
    haptic('light');
    scale.set(0.88);
    setTimeout(() => scale.set(1.04), 80);
    setTimeout(() => scale.set(1), 180);
  }

  function handlePointerDown() {
    if (rest['aria-disabled']) return;
    scale.set(0.92);
  }

  function handlePointerUp() {
    scale.set(1);
  }
</script>

{#if href}
  <a
    {href}
    class={classNames}
    style="transform: scale({$scale})"
    onclick={handleClick}
    onpointerdown={handlePointerDown}
    onpointerup={handlePointerUp}
    onpointerleave={handlePointerUp}
    {...rest as any}
  >
    {@render children?.()}
  </a>
{:else}
  <button
    class={classNames}
    style="transform: scale({$scale})"
    onclick={handleClick}
    onpointerdown={handlePointerDown}
    onpointerup={handlePointerUp}
    onpointerleave={handlePointerUp}
    {...rest}
  >
    {@render children?.()}
  </button>
{/if}
