<script lang="ts">
  import { cn } from '$lib/utils';
  import { Disclosure, DisclosureSummary } from '../../Disclosure';
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
    class?: string;
    slides: CarouselSlide[];
    otherSlides: CarouselSlide[];
    unit: string;
  }

  let { class: className, slides, otherSlides, unit }: Props = $props();
</script>

<Disclosure class={cn(className)}>
  <DisclosureSummary class='cursor-pointer rounded-8 border border-solid-gray-600 !bg-white px-3 py-2'>
    すべての{unit}
  </DisclosureSummary>
  <div class='mt-3 pl-0'>
    <ul class='grid list-none gap-y-6 p-0'>
      {#each otherSlides as slide (slide.id)}
        {@const slideIndex = slides.findIndex((item) => item.id === slide.id)}
        <li
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
            aria-hidden='true'
          >
            {slideIndex + 1}
          </p>
          <div class='[grid-area:main] relative min-w-0'>
            <a
              class={cn(
                "block relative",
                "hover:outline hover:outline-4 hover:outline-blue-900 hover:-outline-offset-1",
                "focus-visible:outline focus-visible:outline-4 focus-visible:outline-black focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:rounded-4 focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
                "hover:after:absolute hover:after:inset-[1px] hover:after:ring-[calc(2/16*1rem)] hover:after:ring-inset hover:after:ring-white hover:after:pointer-events-none"
              )}
              href={slide.href}
              target={slide.target}
            >
              <span class='sr-only'>{slide.label}</span>
              <div class='grid place-content-center h-full rounded-[inherit] outline outline-2 outline-black -outline-offset-2'>
                <picture>
                  {#if slide.imageSources}
                    {#each slide.imageSources as source}
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
                    src={slide.image.src}
                    alt={slide.image.alt}
                    width={slide.image.width}
                    height={slide.image.height}
                  />
                </picture>
              </div>
            </a>
          </div>
          <div class='[grid-area:main] relative -z-10 overflow-clip'>
            <CarouselBackgroundLayer image={slide.image} imageSources={slide.imageSources} />
          </div>
        </li>
      {/each}
    </ul>
  </div>
</Disclosure>
