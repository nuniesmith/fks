<script lang="ts">
  let { lines = 3, height = '14px' } = $props<{
    lines?: number;
    height?: string;
  }>();

  const widths = ['100%', '90%', '75%', '60%', '50%', '45%', '40%', '55%'];

  function lineWidth(i: number): string {
    return widths[i % widths.length];
  }
</script>

<div class="skeleton-group" role="status" aria-label="Loading">
  {#each Array(lines) as _, i}
    <div
      class="skeleton-line"
      style:width={lineWidth(i)}
      style:height={height}
    ></div>
  {/each}
</div>

<style>
  .skeleton-group {
    display: flex;
    flex-direction: column;
  }

  .skeleton-line {
    border-radius: var(--r);
    margin: 6px 0;
    background: linear-gradient(
      90deg,
      var(--bg2) 25%,
      var(--bg3) 50%,
      var(--bg2) 75%
    );
    background-size: 200% 100%;
    animation: skeleton-pulse 1.6s ease-in-out infinite;
  }

  @keyframes skeleton-pulse {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton-line {
      animation: none;
      background: var(--bg2);
    }
  }
</style>
