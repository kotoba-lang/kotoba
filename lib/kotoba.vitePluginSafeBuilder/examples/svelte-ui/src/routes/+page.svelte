<script lang="ts">
  import { Card, Button, Input, Textarea } from '@etzhayyim/design-system';
  import { listTools, runTool } from '$lib/mcp';

  type Tool = { name?: string; description?: string };

  const healthCards = [
    { key: 'MCP', value: 'Online', hint: '/xrpc' },
    { key: 'Build', value: 'Safe', hint: 'safe-builder' },
    { key: 'UI', value: 'Svelte 5', hint: 'AppShell v2' }
  ];

  let tools = $state<Tool[]>([]);
  let toolName = $state('');
  let argsText = $state('{\n  "action": "status"\n}');
  let output = $state('Ready');

  async function refresh() {
    try {
      tools = await listTools();
      if (!toolName && tools[0]?.name) toolName = tools[0].name;
      output = 'Loaded ' + tools.length + ' tools';
    } catch (e) {
      output = String(e);
    }
  }

  async function call() {
    try {
      const args = JSON.parse(argsText) as Record<string, unknown>;
      const res = await runTool(toolName, args);
      output = JSON.stringify(res, null, 2);
    } catch (e) {
      output = String(e);
    }
  }
</script>

<div class="mx-auto grid max-w-[1320px] gap-3.5 p-[18px]">
  <section class="rounded-xl border border-[rgba(111,203,238,0.3)] bg-[color-mix(in_srgb,#0a2030_84%,#193e52_16%)] p-4">
    <p class="m-0 text-[13px] uppercase tracking-[0.09em]">Safe Builder UI</p>
    <h1 class="my-2 text-[34px] leading-[1.06]">iPad First Operations Console</h1>
    <p class="m-0 text-[17px] leading-[1.46]">HIG 準拠の 4 ブレークポイントで、MCP 実行と運用状態確認を 1 画面で扱います。</p>
  </section>

  <section class="grid gap-2.5 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3">
    {#each healthCards as card}
      <Card class="rounded-xl">
        <div class="p-4">
          <div class="text-sm font-semibold uppercase tracking-[0.08em] text-[#a7bfd2]">{card.key}</div>
          <div class="text-[28px] font-bold leading-[1.1]">{card.value}</div>
          <div class="mt-1 text-[13px] text-[#a7bfd2]">{card.hint}</div>
        </div>
      </Card>
    {/each}
  </section>

  <section class="grid gap-3 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-[1.1fr_1fr]">
    <Card>
      <div class="p-4">
        <div class="mb-3 text-lg font-semibold">MCP Tool Browser</div>
        <div class="grid gap-2">
          <Button onclick={refresh}>Refresh Tools</Button>
          <Input bind:value={toolName} placeholder="Tool name" />
        </div>

        <div class="mt-3 grid max-h-[280px] gap-2 overflow-auto">
          {#if tools.length === 0}
            <p class="text-[#9eb4c7]">No tools loaded.</p>
          {:else}
            {#each tools as t}
              <button class="grid min-h-11 gap-1 rounded-[10px] border border-[rgba(152,185,209,0.35)] bg-[rgba(9,22,35,0.65)] px-2.5 py-2 text-left text-[#e3f3ff]" onclick={() => (toolName = t.name ?? '')}>
                <strong>{t.name}</strong>
                <span class="text-[13px] text-[#abc0d3]">{t.description ?? 'no description'}</span>
              </button>
            {/each}
          {/if}
        </div>
      </div>
    </Card>

    <Card>
      <div class="p-4">
        <div class="mb-3 text-lg font-semibold">Tool Runner</div>
        <label class="mb-2 block text-[13px]" for="tool-args">Arguments (JSON)</label>
        <Textarea id="tool-args" class="min-h-[180px] font-mono" bind:value={argsText} rows={9} />
        <Button class="mt-2.5 min-h-11" onclick={call} disabled={!toolName}>Run Tool</Button>
        <pre class="mt-2.5 max-h-[300px] overflow-auto rounded-xl border border-[rgba(152,185,209,0.35)] bg-[rgba(9,22,35,0.7)] p-2.5 text-[13px]">{output}</pre>
      </div>
    </Card>
  </section>
</div>
