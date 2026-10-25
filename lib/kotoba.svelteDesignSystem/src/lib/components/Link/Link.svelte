<script lang="ts">
  import { cn } from '$lib/utils';
  import { linkStyle } from './styles';
  import LinkExternalLinkIcon from './LinkExternalLinkIcon.svelte';
  import type { HTMLAnchorAttributes, SVGAttributes } from 'svelte/elements';

  interface Props extends HTMLAnchorAttributes {
    children?: import('svelte').Snippet;
    icon?: SVGAttributes<SVGSVGElement>;
  }

  let { 
    class: className, 
    children, 
    icon, 
    ...rest 
  }: Props = $props();
</script>

<a class={cn(linkStyle, className)} {...rest}>
  {@render children?.()}

  {#if rest.target === '_blank'}
    <LinkExternalLinkIcon {...icon} />
  {/if}
</a>
