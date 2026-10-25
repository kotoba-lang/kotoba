<script lang="ts">
  import { cn } from '$lib/utils';
  import UtilityLinkExternalLinkIcon from './UtilityLinkExternalLinkIcon.svelte';
  import { utilityLinkStyle } from './styles';
  import type { HTMLAnchorAttributes, SVGAttributes } from 'svelte/elements';

  interface Props extends HTMLAnchorAttributes {
    children?: import('svelte').Snippet;
    icon?: SVGAttributes<SVGSVGElement>;
  }

  let { children, class: className, icon, ...rest }: Props = $props();
</script>

<a class={cn(utilityLinkStyle, className)} {...rest}>
  {@render children?.()}

  {#if rest.target === '_blank'}
    <UtilityLinkExternalLinkIcon {...icon} />
  {/if}
</a>
