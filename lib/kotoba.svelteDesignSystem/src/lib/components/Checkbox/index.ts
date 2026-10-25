import type { ComponentProps } from 'svelte';
import CheckboxComponent from './Checkbox.svelte';

export { default as Checkbox } from './Checkbox.svelte';
export type CheckboxSize = NonNullable<ComponentProps<typeof CheckboxComponent>['size']>;
