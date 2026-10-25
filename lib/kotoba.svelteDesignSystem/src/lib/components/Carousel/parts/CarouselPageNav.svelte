<script lang="ts">
  import { cn } from '$lib/utils';

  interface Props {
    currentIndex: number;
    total: number;
    unit: string;
    onPrev: () => void;
    onNext: () => void;
  }

  let { currentIndex, total, unit, onPrev, onNext }: Props = $props();
</script>

<p class='relative m-0 flex items-center justify-end gap-3 p-0'>
  <button
    type='button'
    onclick={onPrev}
    class='
      relative flex h-6 w-6 items-center justify-center rounded-full border border-blue-1000 bg-white p-0 text-blue-1000
      after:absolute after:-inset-full after:m-auto after:h-11 after:w-11
      focus-visible:outline focus-visible:outline-4 focus-visible:outline-black focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:shadow-[0_0_0_calc(2/16*1rem)_#fce16b]
    '
  >
    <svg width='16' height='16' viewBox='0 0 16 16' aria-hidden='true'>
      <path
        d='m5.27 8 5.33-5.33-.93-.94L3.4 8l6.27 6.27.93-.94L5.27 8Z'
        fill='currentColor'
      ></path>
    </svg>
    <span class='sr-only'>前の{unit}</span>
  </button>
  <span class='[text-box-edge:cap_alphabetic] [text-box-trim:trim-both]'>
    {currentIndex + 1} / {total}
  </span>
  <button
    type='button'
    onclick={onNext}
    class={cn(
      "relative flex h-6 w-6 items-center justify-center rounded-full border border-blue-1000 bg-white p-0 text-blue-1000",
      "after:absolute after:-inset-full after:m-auto after:h-11 after:w-11",
      "focus-visible:outline focus-visible:outline-4 focus-visible:outline-black focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300"
    )}
  >
    <svg width='16' height='16' viewBox='0 0 16 16' aria-hidden='true'>
      <path
        d='m6 1.73-.93.94L10.4 8l-5.33 5.33.93.94L12.27 8 6 1.73Z'
        fill='currentColor'
      ></path>
    </svg>
    <span class='sr-only'>次の{unit}</span>
  </button>
</p>
