// Placeholder for Chart.js setup (tree-shaken). Can be extended later.
export function toPieData(labels: string[], values: number[]) {
  const palette = ['#60a5fa', '#a78bfa', '#34d399', '#f472b6', '#f59e0b', '#f87171'];
  return {
    labels,
    datasets: [
      {
        data: values,
        backgroundColor: values.map((_, i) => palette[i % palette.length]),
        borderWidth: 0,
      },
    ],
  };
}
