import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TimeseriesPoint } from '../api/dashboard'
import { SEVERITIES } from '../api/detections'
import { formatAxisNumber, formatClock, formatTime } from '../lib/format'
import { SEVERITY_COLORS } from '../lib/severity'
import { BAR_STYLE, CHART_AXIS, CHART_GRID, legendText, TOOLTIP_STYLE } from './chartStyle'

export function DetectionsChart({ data, showSeconds }: { data: TimeseriesPoint[]; showSeconds: boolean }) {
  const formatTick = showSeconds ? formatTime : formatClock
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke={CHART_GRID} />
        <XAxis dataKey="timestamp" tickFormatter={(ts: string) => formatTick(ts)} minTickGap={40} {...CHART_AXIS} />
        <YAxis allowDecimals={false} tickFormatter={formatAxisNumber} {...CHART_AXIS} />
        <Tooltip labelFormatter={(ts) => formatTick(String(ts))} {...TOOLTIP_STYLE} />
        <Legend
          iconType="square"
          iconSize={10}
          itemSorter={null}
          formatter={legendText}
          wrapperStyle={{ fontSize: 12 }}
        />
        {SEVERITIES.map((s) => (
          <Bar
            key={s}
            dataKey={`detections_by_severity.${s}`}
            name={s}
            stackId="severity"
            fill={SEVERITY_COLORS[s]}
            {...BAR_STYLE}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
