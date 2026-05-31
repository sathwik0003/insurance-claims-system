const CONFIG = {
  APPROVED:      { bg: 'bg-teal-500/15 border-teal-500/30',  text: 'text-teal-300',   dot: 'bg-teal-400',  label: 'Approved' },
  PARTIAL:       { bg: 'bg-amber-500/15 border-amber-500/30', text: 'text-amber-300',  dot: 'bg-amber-400', label: 'Partial'  },
  REJECTED:      { bg: 'bg-red-500/15 border-red-500/30',     text: 'text-red-300',    dot: 'bg-red-400',   label: 'Rejected' },
  MANUAL_REVIEW: { bg: 'bg-plum-500/15 border-plum-500/30',   text: 'text-plum-300',   dot: 'bg-plum-400',  label: 'Manual Review' },
}

export default function DecisionBadge({ decision, size = 'md' }) {
  const c = CONFIG[decision] || CONFIG.MANUAL_REVIEW
  const sz = size === 'lg'
    ? 'px-4 py-1.5 text-sm gap-2'
    : 'px-3 py-1 text-xs gap-1.5'
  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${c.bg} ${c.text} ${sz}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  )
}