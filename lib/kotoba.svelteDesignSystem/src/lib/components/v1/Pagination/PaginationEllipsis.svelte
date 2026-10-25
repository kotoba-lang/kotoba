<script lang="ts">
  import { cn } from '$lib/utils';
  import type { SVGAttributes } from 'svelte/elements';

  interface Props extends SVGAttributes<SVGSVGElement> {}

  let { class: className, ...rest }: Props = $props();
</script>

<svg
  aria-hidden={true}
  class={className}
  fill='none'
  height='24'
  role='img'
  viewBox='0 0 24 24'
  width='24'
  {...rest}
>
  <circle class='fill-blue-900' cx='6' cy='12' r='1' />
  <circle class='fill-blue-900' cx='12' cy='12' r='1' />
  <circle class='fill-blue-900' cx='18' cy='12' r='1' />
</svg>
