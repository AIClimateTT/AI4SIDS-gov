import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { formatDisplayLabel } from '@/lib/format-display'
import { chartAxisPercent } from '@/lib/quality-display'
import type { ThresholdStatus } from '@/types/dmcu'

const chartConfig = {
  actual: {
    label: 'Actual',
    color: 'var(--chart-1)',
  },
  threshold: {
    label: 'Threshold',
    color: 'var(--chart-2)',
  },
} satisfies ChartConfig

type QualityThresholdChartProps = {
  thresholds: ThresholdStatus[]
}

export function QualityThresholdChart({
  thresholds,
}: QualityThresholdChartProps) {
  const data = thresholds.flatMap((item) => {
    const actual = chartAxisPercent(item.name, item.actual)
    const threshold = chartAxisPercent(item.name, item.threshold)
    if (actual === null || threshold === null) return []
    return [
      {
        name: item.name,
        label: formatDisplayLabel(item.name),
        actual,
        threshold,
      },
    ]
  })

  if (data.length === 0) return null

  return (
    <div>
      <ul className="sr-only">
        {data.map((row) => (
          <li key={row.name}>{row.label}</li>
        ))}
      </ul>
      <ChartContainer
        config={chartConfig}
        className="aspect-auto h-80 w-full"
        style={{ width: '100%', height: 320 }}
        initialDimension={{ width: 800, height: 320 }}
        role="img"
        aria-label="Actual versus threshold"
      >
        <BarChart
          accessibilityLayer
          data={data}
          layout="vertical"
          margin={{ left: 8, right: 16 }}
        >
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => `${value}%`}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={148}
            tickLine={false}
            axisLine={false}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                formatter={(value) =>
                  typeof value === 'number' ? `${value}%` : String(value)
                }
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          <Bar dataKey="actual" fill="var(--color-actual)" radius={4} />
          <Bar dataKey="threshold" fill="var(--color-threshold)" radius={4} />
        </BarChart>
      </ChartContainer>
    </div>
  )
}
