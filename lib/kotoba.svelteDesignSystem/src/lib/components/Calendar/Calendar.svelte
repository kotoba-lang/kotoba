<script lang="ts">
  import { cn } from '../../utils.js';

  const DAYS = ['日', '月', '火', '水', '木', '金', '土'] as const;
  const YEARS = Array.from({ length: 13 }, (_, i) => 2018 + i);

  interface Props {
    value?: Date | null;
    onchange?: (date: Date | null) => void;
    class?: string;
  }

  let { value = $bindable(null), onchange, class: className }: Props = $props();

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let viewYear = $state(value ? value.getFullYear() : today.getFullYear());
  let viewMonth = $state(value ? value.getMonth() : today.getMonth());

  const daysInMonth = $derived(new Date(viewYear, viewMonth + 1, 0).getDate());
  const firstDayOfWeek = $derived(new Date(viewYear, viewMonth, 1).getDay());

  const calendarRows = $derived.by(() => {
    const cells: (number | null)[] = Array(firstDayOfWeek).fill(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    while (cells.length % 7 !== 0) cells.push(null);
    const rows: (number | null)[][] = [];
    for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
    return rows;
  });

  function isSelected(day: number | null): boolean {
    if (!day || !value) return false;
    return value.getFullYear() === viewYear && value.getMonth() === viewMonth && value.getDate() === day;
  }

  function isToday(day: number | null): boolean {
    if (!day) return false;
    return today.getFullYear() === viewYear && today.getMonth() === viewMonth && today.getDate() === day;
  }

  function selectDay(day: number | null) {
    if (!day) return;
    const d = new Date(viewYear, viewMonth, day);
    value = d;
    onchange?.(d);
  }

  function prevMonth() {
    if (viewMonth === 0) { viewMonth = 11; viewYear--; }
    else viewMonth--;
  }

  function nextMonth() {
    if (viewMonth === 11) { viewMonth = 0; viewYear++; }
    else viewMonth++;
  }

  function goToday() {
    viewYear = today.getFullYear();
    viewMonth = today.getMonth();
    value = new Date(today);
    onchange?.(value);
  }

  function clearDate() {
    value = null;
    onchange?.(null);
  }

  const cellBase = `
    m-1 flex items-center justify-center size-10 rounded-full
    underline-offset-[calc(3/16*1rem)]
    hover:bg-solid-gray-50 hover:underline
    focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-black
    focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300
  `;
</script>

<div class={cn('flex flex-col items-center w-max', className)}>
  <!-- ナビゲーション行 -->
  <div class="flex items-center gap-2 p-4">
    <select
      class="h-11 rounded-4 border border-solid-gray-400 px-2 text-oln-16N-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-yellow"
      aria-label="年"
      bind:value={viewYear}
    >
      {#each YEARS as y}
        <option value={y}>{y}年</option>
      {/each}
    </select>

    <div class="flex items-center">
      <button
        type="button"
        class={cn(cellBase, 'size-11 rounded-8')}
        onclick={prevMonth}
        aria-label="前の月"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="m5.27 8 5.33-5.33-.93-.94L3.4 8l6.27 6.27.93-.94L5.27 8Z" fill="currentColor"/>
        </svg>
      </button>
      <p class="w-14 text-center text-oln-16N-100 tabular-nums">{viewMonth + 1}月</p>
      <button
        type="button"
        class={cn(cellBase, 'size-11 rounded-8')}
        onclick={nextMonth}
        aria-label="次の月"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="m6 1.73-.93.94L10.4 8l-5.33 5.33.93.94L12.27 8 6 1.73Z" fill="currentColor"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- カレンダーグリッド -->
  <table class="mx-3 mb-2" aria-label="{viewYear}年{viewMonth + 1}月">
    <thead class="[&_th]:p-0">
      <tr>
        {#each DAYS as day}
          <th class="size-12 text-center font-bold text-oln-16N-100" scope="col">{day}</th>
        {/each}
      </tr>
    </thead>
    <tbody class="[&_td]:p-0">
      {#each calendarRows as row}
        <tr>
          {#each row as day}
            <td>
              {#if day}
                <button
                  type="button"
                  aria-label="{viewYear}年{viewMonth + 1}月{day}日 {DAYS[new Date(viewYear, viewMonth, day).getDay()]}曜日{isToday(day) ? ' 本日' : ''}"
                  aria-pressed={isSelected(day)}
                  class={cn(
                    cellBase,
                    isSelected(day) && '!bg-blue-900 border border-transparent text-white hover:bg-blue-900',
                    isToday(day) && !isSelected(day) && 'font-bold underline'
                  )}
                  onclick={() => selectDay(day)}
                >
                  {day}
                </button>
              {/if}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>

  <!-- フッター -->
  <div class="flex self-stretch justify-between gap-4 p-4">
    <button
      type="button"
      class="text-blue-900 underline underline-offset-[calc(3/16*1rem)] text-oln-16B-100 hover:bg-blue-50 hover:text-blue-1000 px-3 py-1 rounded-4 focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-black"
      onclick={clearDate}
    >
      削除
    </button>
    <button
      type="button"
      class="border border-current text-blue-900 text-oln-16B-100 px-3 py-1 rounded-4 hover:bg-blue-200 hover:text-blue-1000 focus-visible:bg-yellow-300 focus-visible:outline focus-visible:outline-4 focus-visible:outline-black"
      onclick={goToday}
    >
      今日
    </button>
  </div>
</div>
