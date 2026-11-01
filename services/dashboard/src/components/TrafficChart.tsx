import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TimeseriesPoint } from '../api/dashboard'
import { formatAxisNumber, formatClock, formatNumber, formatTime } from '../lib/format'
import { BAR_STYLE, CHART_AXIS, CHART_GRID, TOOLTIP_STYLE } from './chartStyle'

export function TrafficChart({ data, showSeconds }: { data: TimeseriesPoint[]; showSeconds: boolean }) {
  const formatTick = showSeconds ? formatTime : formatClock
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} stroke={CHART_GRID} />
        <XAxis dataKey="timestamp" tickFormatter={(ts: string) => formatTick(ts)} minTickGap={40} {...CHART_AXIS} />
        <YAxis allowDecimals={false} tickFormatter={formatAxisNumber} {...CHART_AXIS} />
        <Tooltip
          labelFormatter={(ts) => formatTick(String(ts))}
          formatter={(value) => [formatNumber(Number(value)), 'Flows']}
          {...TOOLTIP_STYLE}
        />
        <Bar dataKey="flows_count" name="Flows" fill="#3b5bdb" {...BAR_STYLE} />
      </BarChart>
    </ResponsiveContainer>
  )
}
