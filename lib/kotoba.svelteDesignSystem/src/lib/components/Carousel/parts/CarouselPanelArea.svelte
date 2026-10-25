<script lang="ts">
  import { cn } from '$lib/utils';
  import CarouselBackgroundLayer from './CarouselBackgroundLayer.svelte';

  type CarouselSlide = {
    id: string;
    label: string;
    href: string;
    target?: string;
    image: any;
    imageSources?: any[];
  };

  interface Props {
    currentSlide: CarouselSlide;
    nextSlide: CarouselSlide;
    currentIndex: number;
    unit: string;
    isNormal: boolean;
    onNext: () => void;
  }

  let { currentSlide, nextSlide, currentIndex, unit, isNormal, onNext }: Props = $props();

  const mainLabel = $derived(currentSlide.label || `${unit}${currentIndex + 1}`);
</script>

<div
  class={cn(
    "relative grid [grid-template-areas:'main'] [grid-template-rows:auto] grid-cols-[auto]",
    "@[64rem]:-mx-12 @[64rem]:[grid-template-areas:'number_main_next_.'] @[64rem]:[grid-template-rows:auto] @[64rem]:grid-cols-[calc(48/16*1rem)_3fr_1fr_calc(48/16*1rem)]",
    "before:hidden before:[grid-area:number] before:justify-self-center before:border-r before:border-black before:h-full",
    "@[64rem]:group-has-[[open]]/carousel:before:block"
  )}
>
  <p
    class={cn(
      "hidden [grid-area:number] items-center justify-center justify-self-center size-8 pb-0.5 border border-solid-gray-800 bg-white rounded-full text-solid-gray-800 text-oln-16B-100",
      "@[64rem]:group-has-[[open]]/carousel:flex"
    )}
    aria-current={true}
    aria-hidden={true}
  >
    {currentIndex + 1}
  </p>

  <div class='[grid-area:main] relative min-w-0' aria-live='polite' aria-atomic={true}>
    <div role={isNormal ? 'tabpanel' : undefined} aria-label={isNormal ? mainLabel : undefined}>
      <a
        class={cn(
          "block relative",
          "after:absolute after:pointer-events-none",
          "hover:outline hover:outline-4 hover:outline-blue-900 hover:-outline-offset-2",
          "focus-visible:overflow-hidden focus-visible:outline focus-visible:outline-4 focus-visible:outline-black focus-visible:-outline-offset-[calc(2/16*1rem)] focus-visible:rounded-8 focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
          "hover:after:inset-[2px] hover:after:ring-[calc(2/16*1rem)] hover:after:ring-inset hover:after:ring-white",
          "focus-visible:after:inset-[2px] focus-visible:after:ring-[calc(2/16*1rem)] focus-visible:after:ring-inset focus-visible:after:ring-yellow-300 focus-visible:after:rounded-6"
        )}
        href={currentSlide.href}
        target={currentSlide.target}
      >
        <span class='sr-only'>{mainLabel}</span>
        <div class='grid place-content-center h-full rounded-[inherit] outline outline-2 outline-black -outline-offset-2'>
          <picture>
            {#if currentSlide.imageSources}
              {#each currentSlide.imageSources as source}
                <source
                  srcset={source.srcSet}
                  media={source.media}
                  width={source.width}
                  height={source.height}
                />
              {/each}
            {/if}
            <img
              class='block max-w-full size-auto'
              src={currentSlide.image.src}
              alt={currentSlide.image.alt}
              width={currentSlide.image.width}
              height={currentSlide.image.height}
            />
          </picture>
        </div>
      </a>
    </div>
  </div>

  <p
    class={cn(
      "hidden [grid-area:next] min-w-0 p-6 border border-solid-gray-420 border-l-0",
      "group-has-[[open]]/carousel:!hidden @[64rem]:block"
    )}
  >
    <button
      type='button'
      onclick={onNext}
      class={cn(
        "relative border border-solid-gray-420 bg-white p-0 text-left underline underline-offset-[calc(3/16*1rem)] decoration-[calc(1/16*1rem)] cursor-pointer touch-manipulation",
        "hover:outline hover:outline-4 hover:outline-blue-900 hover:-outline-offset-1 hover:decoration-[calc(3/16*1rem)]",
        "hover:after:absolute hover:after:inset-0 hover:after:ring-[calc(2/16*1rem)] hover:after:ring-inset hover:after:ring-white hover:after:pointer-events-none",
        "focus-visible:outline focus-visible:outline-4 focus-visible:outline-black focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:rounded-[calc(4/16*1rem)] focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300"
      )}
    >
      <picture>
        {#if nextSlide.imageSources}
          {#each nextSlide.imageSources as source}
            <source
              srcset={source.srcSet}
              media={source.media}
              width={source.width}
              height={source.height}
            />
          {/each}
        {/if}
        <img
          class='block max-w-full size-auto'
          src={nextSlide.image.src}
          alt=''
          width={nextSlide.image.width}
          height={nextSlide.image.height}
        />
      </picture>

      <span class='block border-t border-solid-gray-420 p-4 text-std-16B-170 decoration-inherit'>
        次の{unit}
      </span>
    </button>
  </p>

  <div class='[grid-area:main] relative -z-10 overflow-clip'>
    <CarouselBackgroundLayer
      image={currentSlide.image}
      imageSources={currentSlide.imageSources}
    />
  </div>

  <div
    class={cn(
      "hidden [grid-area:next] relative -z-10 overflow-clip",
      "group-has-[[open]]/carousel:!hidden @[64rem]:block"
    )}
  >
    <CarouselBackgroundLayer image={nextSlide.image} imageSources={nextSlide.imageSources} />
  </div>
</div>
