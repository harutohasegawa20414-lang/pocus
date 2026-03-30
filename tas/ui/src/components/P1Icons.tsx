import { GlassWater, UtensilsCrossed, LayoutGrid, Clock } from 'lucide-react'
import type { FoodLevel } from '../types/api'

interface Props {
  drinkRequired: boolean | null
  foodLevel: FoodLevel | null
  tableCount: number | null
  peakTime: string | null
}

const FOOD_LABEL: Record<NonNullable<FoodLevel>, string> = {
  none:  'フードなし',
  basic: '軽食あり',
  rich:  'フード充実',
}

export default function P1Icons({ drinkRequired, foodLevel, tableCount, peakTime }: Props) {
  const icons = []

  if (drinkRequired === true) {
    icons.push(
      <span key="drink" title="ワンドリンク制"
        className="inline-flex items-center gap-1 text-xs text-stone-500 bg-stone-50 border border-stone-200 rounded-md px-2 py-0.5">
        <GlassWater size={12} />
        <span>1ドリンク</span>
      </span>
    )
  }

  if (foodLevel && foodLevel !== 'none') {
    icons.push(
      <span key="food" title={FOOD_LABEL[foodLevel]}
        className="inline-flex items-center gap-1 text-xs text-stone-500 bg-stone-50 border border-stone-200 rounded-md px-2 py-0.5">
        <UtensilsCrossed size={12} />
        <span>{FOOD_LABEL[foodLevel]}</span>
      </span>
    )
  }

  if (tableCount != null) {
    icons.push(
      <span key="tables" title={`テーブル${tableCount}台`}
        className="inline-flex items-center gap-1 text-xs text-stone-500 bg-stone-50 border border-stone-200 rounded-md px-2 py-0.5">
        <LayoutGrid size={12} />
        <span>{tableCount}台</span>
      </span>
    )
  }

  if (peakTime) {
    icons.push(
      <span key="peak" title={`ピーク: ${peakTime}`}
        className="inline-flex items-center gap-1 text-xs text-stone-500 bg-stone-50 border border-stone-200 rounded-md px-2 py-0.5">
        <Clock size={12} />
        <span>{peakTime}</span>
      </span>
    )
  }

  if (icons.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {icons.slice(0, 4)}
    </div>
  )
}
