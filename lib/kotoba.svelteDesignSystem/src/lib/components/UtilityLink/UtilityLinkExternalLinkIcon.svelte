<script lang="ts">
  import { cn } from '$lib/utils';
  import type { SVGAttributes } from 'svelte/elements';

  interface Props extends SVGAttributes<SVGSVGElement> {}

  let { class: className, ...rest }: Props = $props();
</script>

<svg
  aria-label={`${rest['aria-label'] ?? '新規タブで開きます'}`}
  role='img'
  class={cn("ml-1 inline-block align-[-0.15em]", className)}
  fill='none'
  height='16'
  viewBox='0 0 48 48'
  width='16'
  {...rest}
>
  <path
    d='M22 6V9H9V39H39V26H42V42H6V6H22ZM42 6V20H39V11.2L21 29L19 27L36.8 9H28V6H42Z'
    fill='currentColor'
  />
</svg>
