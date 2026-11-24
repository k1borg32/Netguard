// Shared look of the charts: recessive grid and axes, text in text colours (never the series colour).
export const CHART_GRID = '#eceff3'
export const CHART_AXIS = { fontSize: 11, stroke: '#9aa0a6', tick: { fill: '#6b7280' } }
export const TOOLTIP_STYLE = { itemStyle: { color: '#202124' }, labelStyle: { color: '#6b7280' } }
export const BAR_STYLE = {
  maxBarSize: 24,
  radius: [4, 4, 0, 0] as [number, number, number, number],
  stroke: '#ffffff', // 2px surface-coloured gap between touching segments and bars
  strokeWidth: 2,
  isAnimationActive: false,
}

export function legendText(value: string) {
  return <span style={{ color: '#6b7280' }}>{value}</span>
}
