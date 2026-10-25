import type { ComponentProps } from 'svelte';
import CarouselComponent from './Carousel.svelte';

export { default as Carousel } from './Carousel.svelte';
export type CarouselSlide = ComponentProps<typeof CarouselComponent>['slides'][number];
