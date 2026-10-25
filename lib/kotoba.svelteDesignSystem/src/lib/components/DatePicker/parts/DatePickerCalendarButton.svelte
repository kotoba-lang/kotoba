<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  import type { DatePickerSize } from '../DatePicker.svelte';

  interface Props extends HTMLButtonAttributes {
    size?: DatePickerSize;
  }

  let { class: className, size = 'lg', ...rest }: Props = $props();
</script>

<button
  class={cn(
    "group flex h-14 items-center justify-center gap-x-1 rounded-6 border border-blue-900 bg-gv2-bg-input px-3 text-blue-900 hover:border-[calc(3/16*1rem)] hover:px-2.5 focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:outline-gv2-text-primary focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300",
    size === 'md' && "h-12",
    size === 'sm' && "h-10",
    className
  )}
  type='button'
  data-size={size}
  {...rest}
>
  <svg width='24px' height='24px' viewBox='0 -960 960 960' role='img' aria-label='カレンダー'>
    <path
      d='M360-300q-42 0-71-29t-29-71q0-42 29-71t71-29q42 0 71 29t29 71q0 42-29 71t-71 29ZM200-80q-33 0-56.5-23.5T120-160v-560q0-33 23.5-56.5T200-800h40v-80h80v80h320v-80h80v80h40q33 0 56.5 23.5T840-720v560q0 33-23.5 56.5T760-80H200Zm0-80h560v-400H200v400Z'
      fill='currentcolor'
    />
  </svg>
  <svg class='size-4 group-aria-expanded:rotate-180' viewBox='0 0 24 24' aria-hidden={true}>
    <path d='M12 17.1L3 8L4 7L12 15L20 7L21 8L12 17.1Z' fill='currentcolor' />
  </svg>
</button>
