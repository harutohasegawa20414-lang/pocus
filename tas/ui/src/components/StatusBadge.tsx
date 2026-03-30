import type { OpenStatus } from '../types/api'

interface Props {
  status: OpenStatus
  hoursToday?: string | null
  size?: 'sm' | 'md'
}

const LABEL: Record<OpenStatus, string> = {
  open:    '営業中',
  closed:  '本日休業',
  unknown: '時間不明',
}

const STYLE: Record<OpenStatus, string> = {
  open:    'bg-emerald-50 text-emerald-700 border-emerald-200',
  closed:  'bg-stone-100 text-stone-400 border-stone-200',
  unknown: 'bg-amber-50 text-amber-600 border-amber-200',
}

const DOT: Record<OpenStatus, string> = {
  open:    'bg-emerald-500',
  closed:  'bg-stone-400',
  unknown: 'bg-amber-400',
}

export default function StatusBadge({ status, hoursToday, size = 'md' }: Props) {
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'
  const dotSize  = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'
  const px       = size === 'sm' ? 'px-2 py-0.5' : 'px-2.5 py-1'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${textSize} ${px} ${STYLE[status]}`}>
      <span className={`rounded-full flex-shrink-0 ${dotSize} ${DOT[status]}`} />
      <span>{LABEL[status]}</span>
      {hoursToday && status !== 'closed' && (
        <span className="opacity-70 font-normal">{hoursToday}</span>
      )}
    </span>
  )
}
