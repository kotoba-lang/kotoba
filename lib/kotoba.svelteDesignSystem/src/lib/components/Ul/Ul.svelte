<script lang="ts">
  import { cn } from '$lib/utils';
  import { ulStyle } from './styles';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLUListElement> {
    children?: import('svelte').Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<ul class={cn(ulStyle, className)} {...rest}>
  {@render children?.()}
</ul>
