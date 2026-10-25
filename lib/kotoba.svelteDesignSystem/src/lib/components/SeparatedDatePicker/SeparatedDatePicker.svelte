<script lang="ts">
  import { cn } from '$lib/utils';
  import type { HTMLAttributes } from 'svelte/elements';

  export type SeparatedDatePickerSize = 'lg' | 'md' | 'sm';

  interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
    size?: SeparatedDatePickerSize;
    isError?: boolean;
    isReadonly?: boolean;
    isDisabled?: boolean;
    children: import('svelte').Snippet<[{
      readOnly: boolean | undefined;
      'aria-disabled': boolean | undefined;
      'aria-invalid': boolean | undefined;
    }]>;
  }

  let { 
    class: className, 
    size = 'lg', 
    isError, 
    isReadonly, 
    isDisabled, 
    children, 
    ...rest 
  }: Props = $props();
</script>

<div class='pt-3 inline-block'>
  <div
    class={cn(
      "flex h-14 gap-x-4 text-solid-gray-900",
      size === 'md' && "h-12",
      size === 'sm' && "h-10",
      className
    )}
    data-size={size}
    {...rest}
  >
    {@render children({ 
      readOnly: isReadonly, 
      'aria-disabled': isDisabled, 
      'aria-invalid': isError 
    })}
  </div>
</div>
