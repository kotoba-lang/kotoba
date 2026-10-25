import type { ComponentProps } from 'svelte';
import LabelComponent from './Label.svelte';

export { default as Label } from './Label.svelte';
export type LabelSize = NonNullable<ComponentProps<typeof LabelComponent>['size']>;
