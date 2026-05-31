import { useState } from 'react'
import TraceViewer from '../components/TraceViewer'
import { evalClaim } from '../api/client'
import DecisionBadge from '../components/DecisionBadge'
import Spinner from '../components/Spinner'

const EXPECTED = {
  TC001: 'WRONG_DOCUMENT_TYPE',
  TC002: 'UNREADABLE_DOCUMENT',
  TC003: 'PATIENT_MISMATCH',
  TC004: 'APPROVED',
  TC005: 'REJECTED',
  TC006: 'PARTIAL',
  TC007: 'REJECTED',
  TC008: 'REJECTED',
  TC009: 'MANUAL_REVIEW',
  TC010: 'APPROVED',
  TC011: 'graceful_degradation',
  TC012: 'REJECTED',
}

function outcomeLabel(res) {
  if (!res?.ok) return null
  const decision = res.data?.decision
  const docError = res.data?.document_error
  if (decision?.decision) return decision.decision
  if (docError?.error_code) return docError.error_code
  return null
}

function passCheck(caseId, res) {
  if (!res) return null        // not run yet — show as pending, not failed
  if (!res.ok) return false    // API error
  const outcome = outcomeLabel(res)
  if (!outcome) return null
  if (caseId === 'TC011') {
    const d = res.data?.decision
    return !!(d && d.component_failures?.length > 0 && d.decision !== 'REJECTED')
  }
  return outcome === EXPECTED[caseId]
}

// Small delay so React can paint each result before the next request fires
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms))

export default function EvalRunner() {
  const [file, setFile]         = useState(null)
  const [cases, setCases]       = useState([])
  const [results, setResults]   = useState({})
  const [running, setRunning]   = useState(false)
  const [runningId, setRunningId] = useState(null)
  const [parseError, setParseError] = useState(null)

  function loadFile(e) {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setParseError(null)
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result)
        const arr = Array.isArray(data) ? data : (data.test_cases || [])
        setCases(arr)
        setResults({})
      } catch {
        setParseError('Invalid JSON file')
      }
    }
    reader.readAsText(f)
  }

  async function runCase(tc) {
    const id  = tc.case_id
    const inp = tc.input || {}

    setRunningId(id)

    // Clear previous result for this case so it shows spinner while running
    setResults(prev => {
      const next = { ...prev }
      delete next[id]
      return next
    })

    try {
      const payload = {
        member_id:                  inp.member_id,
        policy_id:                  inp.policy_id || 'PLUM_GHI_2024',
        claim_category:             inp.claim_category,
        treatment_date:             inp.treatment_date,
        claimed_amount:             inp.claimed_amount,
        hospital_name:              inp.hospital_name || null,
        ytd_claims_amount:          inp.ytd_claims_amount || 0,
        simulate_component_failure: inp.simulate_component_failure || false,
        claims_history:             inp.claims_history || [],
        documents:                  inp.documents || [],
      }
      const res = await evalClaim(payload)
      setResults(prev => ({ ...prev, [id]: { ok: true, data: res } }))
    } catch (err) {
      const msg = err.response?.data?.detail
        ? JSON.stringify(err.response.data.detail)
        : err.message
      setResults(prev => ({ ...prev, [id]: { ok: false, error: msg } }))
    } finally {
      setRunningId(null)
      // Yield to React so it can render this result before the next starts
      await sleep(80)
    }
  }

  async function runAll() {
    setRunning(true)
    setResults({})
    for (const tc of cases) {
      await runCase(tc)
    }
    setRunning(false)
  }

  // Count pass/fail properly
  const done   = Object.keys(results).length
  const passed = Object.entries(results).filter(([id, res]) => passCheck(id, res) === true).length
  const failed  = Object.entries(results).filter(([id, res]) => passCheck(id, res) === false).length

  return (
    <div className="max-w-4xl mx-auto animate-slide-up space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Eval Runner</h1>
        <p className="text-slate-400 text-sm mt-1">
          Load <span className="font-mono text-slate-300">test_cases.json</span> and run all 12 cases against the live API.
        </p>
      </div>

      {/* Toolbar */}
      <div className="card p-5 flex items-center justify-between gap-4 flex-wrap">
        <label className="flex items-center gap-3 cursor-pointer">
          <div className="btn-ghost py-2 px-4 text-sm flex items-center gap-2">
            <span>📂</span>
            {file ? file.name : 'Load test_cases.json'}
          </div>
          <input type="file" accept=".json" className="hidden" onChange={loadFile} />
        </label>

        {cases.length > 0 && (
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">{cases.length} cases</span>
            {done > 0 && (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-teal-400 font-medium">{passed} passed</span>
                {failed > 0 && <span className="text-red-400 font-medium">{failed} failed</span>}
                <span className="text-slate-600">/ {done} run</span>
              </div>
            )}
            <button
              onClick={runAll}
              disabled={running}
              className="btn-primary py-2 text-sm flex items-center gap-2"
            >
              {running
                ? <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Running…</>
                : '▶ Run All'}
            </button>
          </div>
        )}
      </div>

      {parseError && <p className="text-red-400 text-sm">{parseError}</p>}

      {/* Case cards */}
      {cases.map((tc) => {
        const id        = tc.case_id
        const inp       = tc.input || {}
        const res       = results[id]
        const isRunning = runningId === id
        const outcome   = outcomeLabel(res)
        const pass      = passCheck(id, res)
        const expected  = EXPECTED[id]
        const decision  = res?.data?.decision
        const docError  = res?.data?.document_error

        return (
          <div key={id} className={`card p-5 transition-all duration-200 ${isRunning ? 'border-plum-700/60 shadow-lg shadow-plum-900/20' : ''}`}>

            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-mono font-bold shrink-0 ${
                  pass === true  ? 'bg-teal-500/20 text-teal-300 border border-teal-700/40' :
                  pass === false ? 'bg-red-500/20 text-red-300 border border-red-700/40' :
                  isRunning      ? 'bg-plum-500/20 text-plum-300 border border-plum-700/40 animate-pulse' :
                  'bg-slate-800 text-slate-400 border border-slate-700'
                }`}>
                  {pass === true ? '✓' : pass === false ? '✗' : isRunning ? '…' : id?.replace('TC', '')}
                </span>
                <div>
                  <p className="text-sm font-medium text-slate-200">{id} — {tc.case_name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {inp.member_id} · {inp.claim_category?.replace(/_/g,' ')} · ₹{inp.claimed_amount?.toLocaleString('en-IN')}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {!res && !isRunning && (
                  <button onClick={() => runCase(tc)} className="btn-ghost text-xs py-1.5 px-3">Run</button>
                )}
                {isRunning && <Spinner size="sm" label="" />}
                {outcome && (
                  <DecisionBadge decision={
                    outcome === 'APPROVED'      ? 'APPROVED'      :
                    outcome === 'PARTIAL'       ? 'PARTIAL'       :
                    outcome === 'MANUAL_REVIEW' ? 'MANUAL_REVIEW' : 'REJECTED'
                  } />
                )}
              </div>
            </div>

            {/* API error */}
            {res && !res.ok && (
              <div className="mt-3 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
                <p className="text-xs text-red-300 font-mono break-all">{res.error}</p>
              </div>
            )}

            {/* Decision result */}
            {decision && (
              <div className="mt-3 pt-3 border-t border-slate-800 space-y-2">
                <div className="grid grid-cols-4 gap-3 text-xs">
                  <div>
                    <p className="text-slate-600">Decision</p>
                    <p className="text-slate-300 font-medium mt-0.5">{decision.decision}</p>
                  </div>
                  <div>
                    <p className="text-slate-600">Approved</p>
                    <p className="text-slate-300 font-mono mt-0.5">₹{(decision.approved_amount || 0).toLocaleString('en-IN')}</p>
                  </div>
                  <div>
                    <p className="text-slate-600">Confidence</p>
                    <p className="text-slate-300 font-mono mt-0.5">{Math.round((decision.confidence_score || 0) * 100)}%</p>
                  </div>
                  <div>
                    <p className="text-slate-600">Expected</p>
                    <p className={`font-mono mt-0.5 ${pass === true ? 'text-teal-400' : 'text-red-400'}`}>{expected}</p>
                  </div>
                </div>
                {decision.rejection_reasons?.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-xs text-slate-600">Rejection:</p>
                    {decision.rejection_reasons.map(r => (
                      <span key={r} className="text-xs px-2 py-0.5 rounded-full bg-red-900/30 border border-red-800/40 text-red-300 font-mono">{r}</span>
                    ))}
                  </div>
                )}
                {decision.component_failures?.length > 0 && (
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-slate-600">Failures:</p>
                    <p className="text-xs text-amber-300 font-mono">{decision.component_failures.length} component(s)</p>
                  </div>
                )}
              </div>
            )}

            {/* Doc error (TC001-TC003) */}
            {docError && (
              <div className="mt-3 pt-3 border-t border-slate-800 space-y-1 text-xs">
                <div className="flex items-center gap-3">
                  <div>
                    <p className="text-slate-600">Error code</p>
                    <p className="text-red-300 font-mono mt-0.5">{docError.error_code}</p>
                  </div>
                  <div className="flex-1">
                    <p className="text-slate-600">Expected</p>
                    <p className={`font-mono mt-0.5 ${pass === true ? 'text-teal-400' : 'text-red-400'}`}>{expected}</p>
                  </div>
                </div>
                <p className="text-slate-500 leading-relaxed pt-1">{docError.error_message}</p>
              </div>
            )}
            {/* Full pipeline trace */}
            {res?.ok && res?.data?.trace && (
              <div className="mt-3">
                <TraceViewer trace={res.data.trace} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}