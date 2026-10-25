<script lang="ts">
  import { cn } from '$lib/utils';

  type CarouselSlide = {
    id: string;
    label: string;
    href: string;
    target?: string;
    image: any;
    imageSources?: any[];
  };

  interface Props {
    slides: CarouselSlide[];
    selectedIndex: number;
    unit: string;
    onStepSelect: (index: number) => void;
  }

  let { slides, selectedIndex, unit, onStepSelect }: Props = $props();

  function handleKeyDown(event: KeyboardEvent, index: number) {
    const isNext = event.key === 'ArrowRight' || event.key === 'ArrowDown';
    const isPrev = event.key === 'ArrowLeft' || event.key === 'ArrowUp';

    if (!isNext && !isPrev) return;

    event.preventDefault();

    const direction = isNext ? 1 : -1;
    const nextIndex = (index + direction + slides.length) % slides.length;

    onStepSelect(nextIndex);

    const target = (event.currentTarget as HTMLElement).closest('[role="tablist"]')?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[nextIndex];
    target?.focus();
  }
</script>

<ul
  class='relative flex justify-end gap-4'
  role='tablist'
  aria-label={`${unit}選択`}
>
  {#each slides as slide, index (slide.id)}
    {@const isSelected = index === selectedIndex}
    <li
      class={cn(
        "relative shrink-0",
        "before:absolute before:left-full before:top-1/2 before:w-4 before:border-b before:border-solid-gray-800 last:before:hidden"
      )}
      role='presentation'
    >
      <button
        role='tab'
        aria-selected={isSelected}
        tabindex={isSelected ? 0 : -1}
        type='button'
        onkeydown={(event) => handleKeyDown(event, index)}
        class={cn(
          "relative flex size-8 rounded-full cursor-default justify-center items-center border border-solid-gray-800 bg-white pb-0.5 text-solid-gray-800 font-inherit text-oln-16B-100",
          "after:absolute after:-inset-[calc(7/16*1rem)]",
          !isSelected && "underline decoration-1 underline-offset-[calc(3/16*1rem)] hover:decoration-[calc(3/16*1rem)] hover:cursor-pointer",
          isSelected && "bg-solid-gray-800 text-white outline outline-1 outline-offset-[calc(2/16*1rem)] outline-solid-gray-800 ring-[calc(2/16*1rem)] ring-white",
          "focus-visible:outline focus-visible:!outline-4 focus-visible:!outline-black focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:ring-[calc(2/16*1rem)] focus-visible:!ring-yellow-300"
        )}
        onclick={() => onStepSelect(index)}
      >
        <span class='sr-only'>{unit}</span>
        {index + 1}
      </button>
    </li>
  {/each}
</ul>
