<script lang="ts">
  import { cn } from '$lib/utils';

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

  interface Props {
    class?: string;
    image: CarouselImage;
    imageSources?: CarouselImageSource[];
  }

  let { class: className, image, imageSources }: Props = $props();
</script>

<div
  aria-hidden={true}
  class={cn("absolute -inset-1/2 blur-[25px] transform-gpu pointer-events-none", className)}
>
  <picture>
    {#if imageSources}
      {#each imageSources as source}
        <source
          srcset={source.srcSet}
          media={source.media}
          width={source.width}
          height={source.height}
        />
      {/each}
    {/if}
    <img
      class='h-full w-full object-cover'
      src={image.src}
      alt=''
      width={image.width}
      height={image.height}
    />
  </picture>
  <div class='absolute inset-0 bg-white mix-blend-soft-light'></div>
</div>
