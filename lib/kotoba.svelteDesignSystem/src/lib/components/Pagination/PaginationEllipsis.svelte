<script lang="ts">
  import { cn } from '../../utils.js';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends HTMLAttributes<HTMLSpanElement> {}

  let { class: className, ...rest }: Props = $props();
</script>

<span
  aria-hidden="true"
  class={cn('flex h-12 w-12 items-center justify-center text-solid-gray-600 text-oln-16N-100', className)}
  {...rest}
>
  …
</span>
