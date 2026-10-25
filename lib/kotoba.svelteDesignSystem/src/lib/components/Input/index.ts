import type { Component } from 'svelte';
import type { ComponentProps } from 'svelte';
import type { HTMLInputAttributes } from 'svelte/elements';
import InputComponent from './Input.svelte';

export type InputBlockSize = NonNullable<ComponentProps<typeof InputComponent>['blockSize']>;

export interface InputProps extends HTMLInputAttributes {
	isError?: boolean;
	blockSize?: InputBlockSize;
}

export const Input = InputComponent as Component<InputProps, {}, 'value'>;
