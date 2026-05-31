export default function Spinner({ size = 'md', label = 'Processing…' }) {
  const sz = size === 'lg' ? 'w-8 h-8' : size === 'sm' ? 'w-4 h-4' : 'w-5 h-5'
  return (
    <div className="flex flex-col items-center gap-3 py-6">
      <div className={`${sz} border-2 border-plum-500/30 border-t-plum-500 rounded-full animate-spin`} />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  )
}