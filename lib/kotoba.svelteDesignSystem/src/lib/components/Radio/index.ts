import type { ComponentProps } from 'svelte';
import RadioComponent from './Radio.svelte';

export { default as Radio } from './Radio.svelte';
export type RadioSize = NonNullable<ComponentProps<typeof RadioComponent>['size']>;
