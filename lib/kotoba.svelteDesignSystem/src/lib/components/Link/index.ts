import type { Component, Snippet } from 'svelte';
import type { HTMLAnchorAttributes, SVGAttributes } from 'svelte/elements';
import LinkComponent from './Link.svelte';

export interface LinkProps extends HTMLAnchorAttributes {
	children?: Snippet;
	icon?: SVGAttributes<SVGSVGElement>;
}

export const Link = LinkComponent as Component<LinkProps>;
export { default as LinkExternalLinkIcon } from './LinkExternalLinkIcon.svelte';
export * from './styles';
