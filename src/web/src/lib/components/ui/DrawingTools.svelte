<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  type DrawingType = 'trendline' | 'hline' | 'rect' | 'fib' | 'text';

  interface Point { x: number; y: number; }

  interface Drawing {
    type: DrawingType;
    points: Point[];
    color: string;
    text?: string;
  }

  let {
    chartContainer = null,
    chart = null,
    active = $bindable(false),
  } = $props<{
    chartContainer?: HTMLDivElement | null;
    chart?: any;
    active?: boolean;
  }>();

  let canvas: HTMLCanvasElement | null = null;
  let ctx: CanvasRenderingContext2D | null = null;
  let drawings = $state<Drawing[]>([]);
  let currentTool = $state<DrawingType>('trendline');
  let currentColor = $state('#6366f1');
  let tempPoints = $state<Point[]>([]);
  let mousePos = $state<Point | null>(null);
  let textInput = $state('');
  let textInputEl: HTMLInputElement | null = $state(null);
  let showTextPrompt = $state(false);
  let textPromptPos = $state<Point>({ x: 0, y: 0 });

  const tools: { id: DrawingType; label: string; icon: string }[] = [
    { id: 'trendline', label: 'Trend Line', icon: '╱' },
    { id: 'hline', label: 'Horizontal Line', icon: '─' },
    { id: 'rect', label: 'Rectangle', icon: '▭' },
    { id: 'fib', label: 'Fibonacci', icon: 'Fib' },
    { id: 'text', label: 'Text', icon: 'T' },
  ];

  const colors = ['#6366f1', '#16c784', '#ea3943', '#f59e0b', '#00e5ff', '#b388ff', '#ffffff'];

  function setupCanvas() {
    if (!chartContainer || canvas) return;

    canvas = document.createElement('canvas');
    canvas.style.position = 'absolute';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.pointerEvents = active ? 'auto' : 'none';
    canvas.style.zIndex = '10';
    canvas.style.cursor = active ? 'crosshair' : 'default';

    // Make sure container is positioned
    const containerStyle = getComputedStyle(chartContainer);
    if (containerStyle.position === 'static') {
      chartContainer.style.position = 'relative';
    }

    chartContainer.appendChild(canvas);
    resizeCanvas();
    ctx = canvas.getContext('2d');

    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('dblclick', handleDblClick);
  }

  function resizeCanvas() {
    if (!canvas || !chartContainer) return;
    canvas.width = chartContainer.clientWidth;
    canvas.height = chartContainer.clientHeight;
    redraw();
  }

  function handleMouseDown(e: MouseEvent) {
    if (!active || !canvas) return;
    const rect = canvas.getBoundingClientRect();
    const pt: Point = { x: e.clientX - rect.left, y: e.clientY - rect.top };

    if (currentTool === 'text') {
      textPromptPos = pt;
      showTextPrompt = true;
      return;
    }

    if (currentTool === 'hline') {
      drawings = [...drawings, { type: 'hline', points: [pt], color: currentColor }];
      redraw();
      return;
    }

    tempPoints = [...tempPoints, pt];

    const needed = currentTool === 'trendline' ? 2 : currentTool === 'rect' ? 2 : currentTool === 'fib' ? 2 : 2;

    if (tempPoints.length >= needed) {
      drawings = [...drawings, { type: currentTool, points: [...tempPoints], color: currentColor }];
      tempPoints = [];
      redraw();
    }
  }

  function handleMouseMove(e: MouseEvent) {
    if (!active || !canvas) return;
    const rect = canvas.getBoundingClientRect();
    mousePos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    redraw();
  }

  function handleDblClick(_e: MouseEvent) {
    // Cancel current drawing
    tempPoints = [];
    redraw();
  }

  function commitText() {
    if (textInput.trim()) {
      drawings = [...drawings, {
        type: 'text',
        points: [textPromptPos],
        color: currentColor,
        text: textInput.trim(),
      }];
    }
    textInput = '';
    showTextPrompt = false;
    redraw();
  }

  function clearAll() {
    drawings = [];
    tempPoints = [];
    redraw();
  }

  function undoLast() {
    if (drawings.length > 0) {
      drawings = drawings.slice(0, -1);
      redraw();
    }
  }

  function redraw() {
    if (!ctx || !canvas) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw completed drawings
    for (const d of drawings) {
      drawShape(d);
    }

    // Draw in-progress shape
    if (tempPoints.length > 0 && mousePos) {
      drawShape({
        type: currentTool,
        points: [...tempPoints, mousePos],
        color: currentColor + '99',
      });
    }

    // Draw crosshair when active
    if (active && mousePos) {
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#ffffff22';
      ctx.lineWidth = 0.5;

      ctx.beginPath();
      ctx.moveTo(mousePos.x, 0);
      ctx.lineTo(mousePos.x, canvas.height);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(0, mousePos.y);
      ctx.lineTo(canvas.width, mousePos.y);
      ctx.stroke();

      ctx.restore();
    }
  }

  function drawShape(d: Drawing) {
    if (!ctx || !canvas) return;
    ctx.save();
    ctx.strokeStyle = d.color;
    ctx.fillStyle = d.color;
    ctx.lineWidth = 1.5;
    ctx.font = '11px "SF Mono", "Fira Code", monospace';

    switch (d.type) {
      case 'trendline': {
        if (d.points.length >= 2) {
          ctx.beginPath();
          ctx.moveTo(d.points[0].x, d.points[0].y);
          ctx.lineTo(d.points[1].x, d.points[1].y);
          ctx.stroke();

          // Small circles at endpoints
          for (const pt of d.points) {
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        break;
      }

      case 'hline': {
        if (d.points.length >= 1) {
          const y = d.points[0].y;
          ctx.setLineDash([6, 3]);
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(canvas!.width, y);
          ctx.stroke();
          ctx.setLineDash([]);

          // Label on the right
          ctx.fillStyle = d.color;
          ctx.fillText('H-Line', canvas!.width - 52, y - 4);
        }
        break;
      }

      case 'rect': {
        if (d.points.length >= 2) {
          const x = Math.min(d.points[0].x, d.points[1].x);
          const y = Math.min(d.points[0].y, d.points[1].y);
          const w = Math.abs(d.points[1].x - d.points[0].x);
          const h = Math.abs(d.points[1].y - d.points[0].y);

          ctx.fillStyle = d.color + '15';
          ctx.fillRect(x, y, w, h);
          ctx.strokeRect(x, y, w, h);
        }
        break;
      }

      case 'fib': {
        if (d.points.length >= 2) {
          const y1 = d.points[0].y;
          const y2 = d.points[1].y;
          const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
          const range = y2 - y1;

          for (const level of levels) {
            const y = y1 + range * level;
            const alpha = level === 0 || level === 1 ? 'cc' : '66';
            ctx.strokeStyle = d.color + alpha;
            ctx.setLineDash(level === 0.5 ? [6, 3] : []);
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas!.width, y);
            ctx.stroke();

            // Level label
            ctx.fillStyle = d.color + 'cc';
            ctx.fillText(`${(level * 100).toFixed(1)}%`, 6, y - 3);
          }
          ctx.setLineDash([]);

          // Shaded zone between 0.382 and 0.618
          const y382 = y1 + range * 0.382;
          const y618 = y1 + range * 0.618;
          ctx.fillStyle = d.color + '08';
          ctx.fillRect(0, Math.min(y382, y618), canvas!.width, Math.abs(y618 - y382));
        }
        break;
      }

      case 'text': {
        if (d.points.length >= 1 && d.text) {
          ctx.fillStyle = d.color;
          ctx.font = '12px "SF Mono", "Fira Code", monospace';
          ctx.fillText(d.text, d.points[0].x, d.points[0].y);
        }
        break;
      }
    }

    ctx.restore();
  }

  // Update pointer-events when active changes
  $effect(() => {
    if (canvas) {
      canvas.style.pointerEvents = active ? 'auto' : 'none';
      canvas.style.cursor = active ? 'crosshair' : 'default';
    }
  });

  // Setup canvas when chartContainer becomes available
  $effect(() => {
    if (chartContainer && !canvas) {
      setupCanvas();
    }
  });

  $effect(() => {
    if (showTextPrompt && textInputEl) {
      textInputEl.focus();
    }
  });

  let resizeObserver: ResizeObserver | null = null;

  onMount(() => {
    if (chartContainer) {
      setupCanvas();
      resizeObserver = new ResizeObserver(resizeCanvas);
      resizeObserver.observe(chartContainer);
    }
  });

  onDestroy(() => {
    resizeObserver?.disconnect();
    if (canvas && chartContainer?.contains(canvas)) {
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('dblclick', handleDblClick);
      chartContainer.removeChild(canvas);
    }
    canvas = null;
    ctx = null;
  });
</script>

<div class="drawing-toolbar" class:visible={active}>
  <div class="dt-section">
    {#each tools as tool}
      <button
        class="dt-btn"
        class:active={currentTool === tool.id}
        onclick={() => { currentTool = tool.id; }}
        title={tool.label}
        aria-label={tool.label}
        aria-pressed={currentTool === tool.id}
      >
        <span class="dt-icon">{tool.icon}</span>
      </button>
    {/each}
  </div>

  <div class="dt-divider" aria-hidden="true"></div>

  <div class="dt-section" role="radiogroup" aria-label="Drawing color">
    {#each colors as c}
      <button
        class="dt-color"
        class:active={currentColor === c}
        style:background={c}
        onclick={() => { currentColor = c; }}
        role="radio"
        aria-checked={currentColor === c}
        aria-label="Color {c}"
      ></button>
    {/each}
  </div>

  <div class="dt-divider" aria-hidden="true"></div>

  <button class="dt-btn" onclick={undoLast} title="Undo last" aria-label="Undo last drawing">
    <span class="dt-icon">↩</span>
  </button>
  <button class="dt-btn dt-danger" onclick={clearAll} title="Clear all drawings" aria-label="Clear all drawings">
    <span class="dt-icon">✕</span>
  </button>
</div>

{#if showTextPrompt}
  <div
    class="text-prompt"
    style:left="{textPromptPos.x}px"
    style:top="{textPromptPos.y}px"
  >
    <input
      class="text-prompt-input"
      bind:this={textInputEl}
      bind:value={textInput}
      onkeydown={(e) => {
        if (e.key === 'Enter') commitText();
        if (e.key === 'Escape') { showTextPrompt = false; textInput = ''; }
      }}
      placeholder="Label…"
      aria-label="Drawing text label"
    />
  </div>
{/if}

<style>
  .drawing-toolbar {
    display: none;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: var(--bg1, #0c0c18);
    border: 1px solid var(--b2, #2a2a3e);
    border-radius: var(--r-md, 6px);
  }
  .drawing-toolbar.visible {
    display: flex;
  }

  .dt-section {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .dt-btn {
    all: unset;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 24px;
    font-size: 12px;
    color: var(--t3, #555);
    border: 1px solid transparent;
    border-radius: var(--r, 4px);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }
  .dt-btn:hover {
    color: var(--t1, #eee);
    background: var(--bg3, #1a1a2e);
    border-color: var(--b2, #2a2a3e);
  }
  .dt-btn.active {
    color: var(--accent, #6366f1);
    background: var(--accent-dim, rgba(99, 102, 241, 0.15));
    border-color: var(--accent, #6366f1);
  }
  .dt-btn.dt-danger:hover {
    color: var(--red, #ea3943);
    border-color: var(--red, #ea3943);
  }

  .dt-icon {
    font-size: 13px;
    line-height: 1;
  }

  .dt-color {
    all: unset;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    cursor: pointer;
    border: 2px solid transparent;
    transition: border-color 0.15s, transform 0.15s;
  }
  .dt-color:hover {
    transform: scale(1.2);
  }
  .dt-color.active {
    border-color: var(--t1, #eee);
    transform: scale(1.15);
  }

  .dt-divider {
    width: 1px;
    height: 18px;
    background: var(--b1, #1a1a2e);
    margin: 0 4px;
  }

  .text-prompt {
    position: absolute;
    z-index: 20;
    padding: 2px;
  }
  .text-prompt-input {
    padding: 3px 6px;
    font-size: 11px;
    color: var(--t1, #eee);
    background: var(--bg1, #0c0c18);
    border: 1px solid var(--accent, #6366f1);
    border-radius: var(--r, 4px);
    font-family: inherit;
    outline: none;
    width: 120px;
  }
</style>
