<script lang="ts">
  import { cn } from '$lib/utils';
  import { bannerBodyStyle } from './styles';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<div class={cn(bannerBodyStyle, className)} {...rest}>
  {@render children?.()}
</div>
