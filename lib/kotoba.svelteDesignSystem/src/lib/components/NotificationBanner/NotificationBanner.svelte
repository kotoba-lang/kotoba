<script lang="ts">
  import { cn } from '$lib/utils';
  import NotificationBannerIcon from './parts/NotificationBannerIcon.svelte';
  import { bannerStyleClasses, bannerTypeClasses } from './styles';
  import type { 
    NotificationBannerHeadingLevel, 
    NotificationBannerStyle, 
    NotificationBannerType 
  } from './types';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    bannerStyle: NotificationBannerStyle;
    type: NotificationBannerType;
    title: string;
    headingLevel?: NotificationBannerHeadingLevel;
    children?: import('svelte').Snippet;
  }

  let { 
    class: className, 
    bannerStyle, 
    type, 
    title, 
    headingLevel = 'h2',
    children,
    ...rest 
  }: Props = $props();
</script>

<div
  class={cn(
    "grid grid-cols-[var(--icon-size)_1fr_minmax(0,auto)] grid-rows-[minmax(calc(36/16*1rem),auto)] border-current px-4 pt-2 pb-6 [--icon-size:calc(24/16*1rem)] gap-4",
    "desktop:gap-x-6 desktop:px-6 desktop:pt-6 desktop:pb-8 desktop:[--icon-size:calc(36/16*1rem)]",
    bannerStyleClasses,
    bannerTypeClasses,
    className
  )}
  data-type={type}
  data-style={bannerStyle}
  {...rest}
>
  <svelte:element
    this={headingLevel}
    class='col-span-2 grid grid-cols-[inherit] gap-[inherit]'
  >
    <NotificationBannerIcon
      class='justify-self-center mt-[calc(3/16*1rem)] size-7 max-w-none max-h-none desktop:size-11 desktop:-my-1'
      {type}
    />
    <span class='pt-[calc(3/16*1rem)] text-std-17B-170 text-solid-gray-900 desktop:text-std-20B-150 desktop:pt-0.5'>
      {title}
    </span>
  </svelte:element>
  {@render children?.()}
</div>
