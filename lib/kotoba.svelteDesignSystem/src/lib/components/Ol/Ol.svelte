<script lang="ts">
  import { cn } from '$lib/utils';
  import { olStyle } from './styles';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLOListElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<ol class={cn(olStyle, className)} {...rest}>
  {@render children?.()}
</ol>
