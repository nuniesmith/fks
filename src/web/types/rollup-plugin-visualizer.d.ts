declare module 'rollup-plugin-visualizer' {
  import type { Plugin } from 'vite';
  interface VisualizerOptions {
    filename?: string;
    template?: 'treemap' | 'sunburst' | 'network';
    gzipSize?: boolean;
    brotliSize?: boolean;
    open?: boolean;
  }
  export function visualizer(options?: VisualizerOptions): Plugin;
}
