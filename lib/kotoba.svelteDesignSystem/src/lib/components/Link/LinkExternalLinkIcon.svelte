<script lang="ts">
  import { cn } from '$lib/utils';
  import type { SVGAttributes } from 'svelte/elements';

  interface Props extends SVGAttributes<SVGSVGElement> {}

  let { class: className, ...rest }: Props = $props();
</script>

<svg
  aria-label={`${rest['aria-label'] ?? '新規タブで開きます'}`}
  class={cn("mb-[calc(3/16*1rem)] ml-[calc(3/16*1rem)] inline", className)}
  fill='none'
  height='17'
  role='img'
  viewBox='0 0 16 17'
  width='16'
  {...rest}
>
  <g>
    <path
      clip-rule='evenodd'
      d='M3 13.5H13V9.16667H14V14.5H2V2.5H7.33333V3.5H3V13.5ZM9.33333 3.5V2.5H14V7.16667H13V4.23333L7 10.1667L6.33333 9.5L12.2667 3.5H9.33333Z'
      fill-rule='evenodd'
      fill='currentColor'
    />
  </g>
</svg>
