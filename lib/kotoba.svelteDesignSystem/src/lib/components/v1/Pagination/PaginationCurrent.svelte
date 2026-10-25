<script lang="ts">
  interface Props {
    current: number;
    max: number;
  }

  let { current, max }: Props = $props();
</script>

<span class='text-[calc(12/16*1rem)] leading-170'>
  <span aria-current='page'>{current}</span> / {max}
</span>
