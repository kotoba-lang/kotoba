import type { ComponentProps } from 'svelte';
import DividerComponent from './Divider.svelte';

export { default as Divider } from './Divider.svelte';
export type DividerColor = NonNullable<ComponentProps<typeof DividerComponent>['color']>;
