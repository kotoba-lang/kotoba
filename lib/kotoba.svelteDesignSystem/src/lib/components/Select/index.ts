import type { ComponentProps } from 'svelte';
import SelectComponent from './Select.svelte';

export { default as Select } from './Select.svelte';
export type SelectBlockSize = NonNullable<ComponentProps<typeof SelectComponent>['blockSize']>;
