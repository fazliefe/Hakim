export function bboxCss(bbox: number[]): { left: string; top: string; width: string; height: string } {
  const [x0, y0, x1, y1] = bbox;
  return {
    left: `${Math.min(x0, x1) * 100}%`,
    top: `${Math.min(y0, y1) * 100}%`,
    width: `${Math.max(0.01, Math.abs(x1 - x0)) * 100}%`,
    height: `${Math.max(0.01, Math.abs(y1 - y0)) * 100}%`,
  };
}

export function usefulBbox(bbox: number[] | undefined): boolean {
  if (!bbox || bbox.length !== 4) return false;
  const [x0, y0, x1, y1] = bbox;
  const width = Math.abs(x1 - x0);
  const height = Math.abs(y1 - y0);
  const area = width * height;
  return width >= 0.04 && height >= 0.012 && area >= 0.0008 && area < 0.22;
}

export function fieldKey(field: { name: string; page: number; bbox?: number[] }, index: number): string {
  const box = (field.bbox || []).map((n) => Number(n).toFixed(3)).join(",");
  return `${field.name}-${field.page}-${index}-${box}`;
}

export function confidencePct(value: number): string {
  return `%${Math.round(Math.max(0, Math.min(1, value)) * 100)}`;
}

