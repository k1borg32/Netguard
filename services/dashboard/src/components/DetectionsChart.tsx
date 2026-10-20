import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { SEVERITIES } from '../api/detections'
import type { SeverityBucket } from '../lib/buckets'
import { formatTime } from '../lib/format'

// Same colours as the severity badges in index.css.
const COLORS = {
  LOW: '#868e96',
  MEDIUM: '#e8a400',
  HIGH: '#e8590c',
  CRITICAL: '#c92a2a',
}

export function DetectionsChart({ data }: { data: SeverityBucket[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#d0d4da" />
        <XAxis dataKey="ts" tickFormatter={(ts: number) => formatTime(ts)} minTickGap={40} fontSize={11} />
        <YAxis allowDecimals={false} fontSize={11} />
        <Tooltip labelFormatter={(ts) => formatTime(Number(ts))} />
        <Legend iconType="square" iconSize={10} itemSorter={null} wrapperStyle={{ fontSize: 12 }} />
        {SEVERITIES.map((s) => (
          <Bar key={s} dataKey={s} stackId="severity" fill={COLORS[s]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
