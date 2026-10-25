<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  export type DividerColor = 'gray-420' | 'gray-536' | 'black';

  interface Props extends HTMLAttributes<HTMLHRElement> {
    color?: DividerColor;
  }

  let { class: className, color = 'gray-420', ...rest }: Props = $props();
</script>

<hr
  class={cn(
    color === 'gray-420' && "border-solid-gray-420",
    color === 'gray-536' && "border-solid-gray-536",
    color === 'black' && "border-black",
    className
  )}
  data-color={color}
  {...rest}
/>
