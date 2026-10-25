<script lang="ts">
  import { cn } from '$lib/utils';
  import { breadcrumbLinkStyle } from './styles';
  import type { HTMLAnchorAttributes } from 'svelte/elements';

  interface Props extends HTMLAnchorAttributes {
    children?: import('svelte').Snippet;
  }

  let { children, class: className, ...rest }: Props = $props();
</script>

<a class={cn(breadcrumbLinkStyle, className)} {...rest}>
  {@render children?.()}
</a>
