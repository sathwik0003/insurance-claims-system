import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitClaim } from '../api/client'

const CATEGORIES = [
  { value: 'CONSULTATION',        label: 'Consultation',         docs: 'Prescription + Hospital Bill' },
  { value: 'DIAGNOSTIC',          label: 'Diagnostic',           docs: 'Prescription + Lab Report + Bill' },
  { value: 'PHARMACY',            label: 'Pharmacy',             docs: 'Prescription + Pharmacy Bill' },
  { value: 'DENTAL',              label: 'Dental',               docs: 'Hospital Bill (prescription optional)' },
  { value: 'VISION',              label: 'Vision',               docs: 'Prescription + Hospital Bill' },
  { value: 'ALTERNATIVE_MEDICINE',label: 'Alternative Medicine', docs: 'Prescription + Hospital Bill' },
]

export default function SubmitClaim() {
  const navigate = useNavigate()
  const inputRef = useRef(null)

  const [form, setForm] = useState({
    member_id: '',
    claim_category: 'CONSULTATION',
    treatment_date: '',
    claimed_amount: '',
    hospital_name: '',
  })
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const selectedCategory = CATEGORIES.find(c => c.value === form.claim_category)

  // Accumulate files — each pick ADDS to the list rather than replacing
  function handleFilePick(e) {
    const picked = Array.from(e.target.files)
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      const fresh = picked.filter(f => !existing.has(f.name))
      return [...prev, ...fresh]
    })
    // Reset input so same file can be re-picked if removed
    e.target.value = ''
  }

  function removeFile(index) {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!files.length) { setError('Please upload at least one document.'); return }
    setError(null)
    setLoading(true)
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
      files.forEach(f => fd.append('files', f))
      const res = await submitClaim(fd)
      if (res.success && res.decision) {
        navigate(`/claim/${res.decision.claim_id}`, { state: res })
      } else if (!res.success && res.document_error) {
        setError(`${res.document_error.error_message}`)
      } else {
        setError('Unexpected response from server.')
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Server error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white tracking-tight">Submit a Claim</h1>
        <p className="text-slate-400 text-sm mt-1">Upload medical documents and claim details for instant AI processing.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* Member & Policy */}
        <div className="card p-6 space-y-5">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Member & Policy</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Member ID</label>
              <input className="input" placeholder="EMP001" value={form.member_id}
                onChange={set('member_id')} required />
            </div>
            <div>
              <label className="label">Claim Category</label>
              <select className="input" value={form.claim_category} onChange={set('claim_category')}>
                {CATEGORIES.map(c => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Required docs hint */}
          <div className="flex items-center gap-2 bg-plum-900/20 border border-plum-800/30 rounded-lg px-3 py-2">
            <span className="text-plum-400 text-sm">📋</span>
            <p className="text-xs text-slate-400">
              <span className="text-plum-300 font-medium">{selectedCategory?.label}</span> requires:{' '}
              <span className="text-slate-300">{selectedCategory?.docs}</span>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Treatment Date</label>
              <input type="date" className="input" value={form.treatment_date}
                onChange={set('treatment_date')} required />
            </div>
            <div>
              <label className="label">Claimed Amount (₹)</label>
              <input type="number" className="input" placeholder="1500" min="1"
                value={form.claimed_amount} onChange={set('claimed_amount')} required />
            </div>
          </div>

          <div>
            <label className="label">
              Hospital Name <span className="normal-case text-slate-600 font-normal">(optional — required for network discount)</span>
            </label>
            <input className="input" placeholder="Apollo Hospitals" value={form.hospital_name}
              onChange={set('hospital_name')} />
          </div>
        </div>

        {/* Document upload */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Documents</h2>
            {files.length > 0 && (
              <span className="text-xs text-slate-500">{files.length} file{files.length > 1 ? 's' : ''} added</span>
            )}
          </div>

          {/* Drop zone — clicking always opens file picker */}
          <div
            onClick={() => inputRef.current?.click()}
            className={`
              flex flex-col items-center justify-center gap-3 border-2 border-dashed
              rounded-xl p-8 cursor-pointer transition-all duration-200
              ${files.length ? 'border-plum-700/50 bg-plum-900/10' : 'border-slate-700 hover:border-slate-500 hover:bg-slate-800/30'}
            `}
          >
            <span className="text-3xl">{files.length ? '📎' : '📤'}</span>
            <div className="text-center">
              {files.length === 0 ? (
                <>
                  <p className="text-sm text-slate-300 font-medium">Click to add document</p>
                  <p className="text-xs text-slate-500 mt-1">JPG, PNG or PDF</p>
                </>
              ) : (
                <>
                  <p className="text-sm text-plum-300 font-medium">Click to add another document</p>
                  <p className="text-xs text-slate-500 mt-1">Each click adds a new file</p>
                </>
              )}
            </div>
          </div>

          {/* Hidden input — no multiple attr so user picks one at a time, clearer UX */}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
            onChange={handleFilePick}
          />

          {/* File list */}
          {files.length > 0 && (
            <div className="space-y-2">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-3 bg-slate-800/40 rounded-xl px-4 py-3 border border-slate-700/50">
                  <span className="text-lg">
                    {f.name.endsWith('.pdf') ? '📄' : '🖼️'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-200 truncate font-medium">{f.name}</p>
                    <p className="text-xs text-slate-500">{(f.size / 1024).toFixed(0)} KB</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="text-slate-600 hover:text-red-400 transition-colors text-sm px-2 py-1 rounded hover:bg-red-900/20"
                  >
                    ✕ Remove
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Quick-add tip */}
          {files.length === 1 && (
            <div className="flex items-center gap-2 bg-amber-900/15 border border-amber-800/30 rounded-lg px-3 py-2">
              <span className="text-amber-400 text-sm">💡</span>
              <p className="text-xs text-amber-300/80">
                Most claims need 2 documents. Click the upload area again to add your second file.
              </p>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-xl bg-red-900/20 border border-red-800/50 px-4 py-3 text-sm text-red-300 animate-fade-in">
            ⚠ {error}
          </div>
        )}

        <button type="submit" disabled={loading || !files.length}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base">
          {loading
            ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Processing claim…</>
            : `→ Process Claim (${files.length} file${files.length !== 1 ? 's' : ''})`}
        </button>
      </form>
    </div>
  )
}