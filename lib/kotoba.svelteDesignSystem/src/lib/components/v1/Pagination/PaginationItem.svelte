<script lang="ts">
  import { cn } from '$lib/utils';
  import { paginationItemStyle } from './styles';
  import type { HTMLAnchorAttributes } from 'svelte/elements';

  interface Props extends HTMLAnchorAttributes {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<a class={cn(paginationItemStyle, className)} {...rest}>
  {@render children?.()}
</a>
