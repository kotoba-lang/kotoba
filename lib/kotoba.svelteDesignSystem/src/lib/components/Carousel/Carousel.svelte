<script lang="ts">
  import { cn } from '$lib/utils';
  import CarouselPanelArea from './parts/CarouselPanelArea.svelte';
  import CarouselPageNav from './parts/CarouselPageNav.svelte';
  import CarouselStepNav from './parts/CarouselStepNav.svelte';
  import CarouselExpandList from './parts/CarouselExpandList.svelte';
  import type { HTMLAttributes } from 'svelte/elements';

  type CarouselImage = {
    src: string;
    alt: string;
    width: number;
    height: number;
  };

  type CarouselImageSource = {
    srcSet: string;
    width?: number;
    height?: number;
    media: string;
  };

  export type CarouselSlide = {
    id: string;
    label: string;
    href: string;
    target?: string;
    image: CarouselImage;
    imageSources?: CarouselImageSource[];
  };

  interface Props extends HTMLAttributes<HTMLElement> {
    slides: CarouselSlide[];
    currentIndex: number;
    unit?: string;
    isNormal: boolean;
    onPrev: () => void;
    onNext: () => void;
    onStepSelect: (index: number) => void;
  }

  let { 
    class: className, 
    slides, 
    currentIndex, 
    unit = 'スライド', 
    isNormal, 
    onPrev, 
    onNext, 
    onStepSelect, 
    ...rest 
  }: Props = $props();

  const total = $derived(slides.length);
  const normalizedIndex = $derived(((currentIndex % total) + total) % total);
  const currentSlide = $derived(slides[normalizedIndex]);
  const nextSlide = $derived(slides[(normalizedIndex + 1) % total]);
  const otherSlides = $derived(
    total > 1 ? [...slides.slice(normalizedIndex + 1), ...slides.slice(0, normalizedIndex)] : []
  );
</script>

{#if slides.length > 0}
  <section class={cn("@container group/carousel block", className)} {...rest}>
    <div
      class='relative z-0 max-w-[calc(1440/16*1rem)] text-solid-gray-800 text-std-16N-170 @[64rem]:px-12'
    >
      <CarouselPanelArea
        {currentSlide}
        {nextSlide}
        currentIndex={normalizedIndex}
        {unit}
        {isNormal}
        {onNext}
      />

      <div class='flex items-center gap-5 py-3 group-has-[[open]]/carousel:pb-14 @[64rem]:gap-8'>
        <div class='shrink-0 group-has-[[open]]/carousel:!hidden @[64rem]:hidden'>
          <CarouselPageNav
            currentIndex={normalizedIndex}
            {total}
            {unit}
            {onPrev}
            {onNext}
          />
        </div>

        <div class='hidden group-has-[[open]]/carousel:!hidden @[64rem]:flex'>
          <CarouselStepNav
            {slides}
            selectedIndex={normalizedIndex}
            {unit}
            {onStepSelect}
          />
        </div>

        <CarouselExpandList
          class='-order-1 open:flex-1'
          {slides}
          {otherSlides}
          {unit}
        />
      </div>
    </div>
  </section>
{/if}
