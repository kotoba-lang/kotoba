<script lang="ts">
  import '../app.css';

  let { children } = $props();
</script>

<div class="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
  <header class="h-12 flex items-center justify-between px-4 bg-[#141414]/90 backdrop-blur-md border-b border-[#2f2f2f] shrink-0">
    <strong>Safe Builder UI</strong>
  </header>
  <main class="flex-1 overflow-y-auto">
    {@render children()}
  </main>
</div>
