import type { ComponentProps } from 'svelte';
import LegendComponent from './Legend.svelte';

export { default as Legend } from './Legend.svelte';
export type LegendSize = NonNullable<ComponentProps<typeof LegendComponent>['size']>;
