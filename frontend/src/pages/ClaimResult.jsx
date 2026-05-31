import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { getClaim } from '../api/client'
import DecisionBadge from '../components/DecisionBadge'
import TraceViewer from '../components/TraceViewer'
import Spinner from '../components/Spinner'

function AmountCard({ label, value, accent }) {
  return (
    <div className="bg-slate-800/40 rounded-xl p-4 border border-slate-800">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-xl font-semibold font-mono ${accent || 'text-white'}`}>
        ₹{Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
      </p>
    </div>
  )
}

export default function ClaimResult() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [data, setData] = useState(location.state || null)
  const [loading, setLoading] = useState(!location.state)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!location.state && id) {
      getClaim(id)
        .then(setData)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false))
    }
  }, [id])

  if (loading) return <Spinner size="lg" label="Loading claim…" />
  if (error) return (
    <div className="max-w-xl mx-auto text-center py-20">
      <p className="text-red-400 mb-4">{error}</p>
      <button onClick={() => navigate('/')} className="btn-ghost">← Back</button>
    </div>
  )

  // Support both formats: response from /submit and from GET /claims/:id
  const decision = data?.decision || data?.claim
  const trace = data?.trace

  if (!decision) return (
    <div className="max-w-xl mx-auto text-center py-20">
      <p className="text-slate-400 mb-4">No claim data found.</p>
      <button onClick={() => navigate('/')} className="btn-ghost">← Back</button>
    </div>
  )

  const isDocError = !data?.success && data?.document_error

  return (
    <div className="max-w-2xl mx-auto animate-slide-up space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Claim Decision</h1>
          <p className="text-xs text-slate-500 font-mono mt-0.5">{decision.claim_id || id}</p>
        </div>
        <button onClick={() => navigate('/')} className="btn-ghost text-sm py-2">← New Claim</button>
      </div>

      {/* Document error early stop */}
      {isDocError && (
        <div className="card p-6 border-red-800/40 bg-red-900/10 space-y-2 animate-fade-in">
          <div className="flex items-center gap-2">
            <span>🚫</span>
            <span className="font-medium text-red-300">Document Verification Failed</span>
          </div>
          <p className="text-sm text-slate-300">{data.document_error.error_message}</p>
          <p className="text-xs text-slate-500">Code: {data.document_error.error_code}</p>
        </div>
      )}

      {/* Main decision card */}
      {decision.decision && (
        <div className="card p-6 space-y-5">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <DecisionBadge decision={decision.decision} size="lg" />
              <p className="text-sm text-slate-400 mt-2 max-w-md">{decision.member_message || decision.decision_reason}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Confidence</p>
              <p className="text-lg font-semibold text-white font-mono">
                {Math.round((decision.confidence_score || 0) * 100)}%
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <AmountCard label="Claimed" value={decision.claimed_amount} />
            <AmountCard
              label="Approved"
              value={decision.approved_amount}
              accent={
                decision.decision === 'APPROVED' ? 'text-teal-300' :
                decision.decision === 'PARTIAL'  ? 'text-amber-300' : 'text-red-300'
              }
            />
            <AmountCard label="Network Discount" value={decision.network_discount_applied} />
          </div>

          {decision.rejection_reasons?.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 mb-2">Rejection Reasons</p>
              <div className="flex flex-wrap gap-2">
                {decision.rejection_reasons.map((r) => (
                  <span key={r} className="text-xs px-2.5 py-1 rounded-full bg-red-900/30 border border-red-800/40 text-red-300 font-mono">
                    {r}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Line item breakdown */}
      {decision.line_item_decisions?.length > 0 && (
        <div className="card p-5 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Line Items</h3>
          <div className="divide-y divide-slate-800">
            {decision.line_item_decisions.map((li, i) => (
              <div key={i} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="text-sm text-slate-200">{li.description}</p>
                  <p className="text-xs text-slate-500">{li.reason}</p>
                </div>
                <div className="text-right shrink-0 ml-4">
                  <p className={`text-sm font-mono font-medium ${li.approved_amount > 0 ? 'text-teal-300' : 'text-red-400 line-through'}`}>
                    ₹{li.approved_amount?.toLocaleString('en-IN')}
                  </p>
                  <p className="text-xs text-slate-600">of ₹{li.claimed_amount?.toLocaleString('en-IN')}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Meta info */}
      <div className="card p-5 grid grid-cols-2 gap-4 text-sm">
        <div><p className="label">Member</p><p className="text-slate-200">{decision.member_id}</p></div>
        <div><p className="label">Category</p><p className="text-slate-200">{decision.claim_category?.replace(/_/g, ' ')}</p></div>
        <div><p className="label">Treatment Date</p><p className="text-slate-200">{decision.treatment_date}</p></div>
        <div><p className="label">Co-pay Deducted</p><p className="text-slate-200 font-mono">₹{(decision.copay_deducted || 0).toLocaleString('en-IN')}</p></div>
      </div>

      {decision.component_failures?.length > 0 && (
        <div className="rounded-xl border border-amber-800/40 bg-amber-900/10 px-4 py-3 text-xs text-amber-300">
          ⚠ Component failures: {decision.component_failures.join(' · ')}
        </div>
      )}

      <TraceViewer trace={trace} />
    </div>
  )
}