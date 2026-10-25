<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  export type EmergencyBannerHeadingLevel = 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

  interface Props extends HTMLAttributes<HTMLHeadingElement> {
    level: EmergencyBannerHeadingLevel;
    children?: import('svelte').Snippet;
  }

  let { level, class: className, children, ...rest }: Props = $props();
</script>

<svelte:element
  this={level}
  class={cn(
    "text-std-20B-150 text-black desktop:text-std-24B-150",
    className
  )}
  {...rest}
>
  【緊急】
  {@render children?.()}
</svelte:element>
