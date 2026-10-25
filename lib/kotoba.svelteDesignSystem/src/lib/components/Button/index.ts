import type { Component, Snippet } from 'svelte';
import type { HTMLButtonAttributes } from 'svelte/elements';
import ButtonComponent from './Button.svelte';
import type { ButtonSize, ButtonVariant } from './styles';

export interface ButtonProps extends HTMLButtonAttributes {
	variant?: ButtonVariant;
	size?: ButtonSize;
	children?: Snippet;
	href?: string;
	target?: string;
	rel?: string;
}

export const Button = ButtonComponent as Component<ButtonProps>;
export * from './styles';
