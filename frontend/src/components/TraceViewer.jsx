import { useState } from 'react'

// ── Confidence bar ─────────────────────────────────────────────────────────
function ConfBar({ value }) {
  const pct = Math.round((value || 0) * 100)
  const color = pct >= 80 ? 'bg-teal-400' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-400 w-8 text-right">{pct}%</span>
    </div>
  )
}

// ── Doc Verifier renderer ──────────────────────────────────────────────────
function DocVerifierOutput({ summary }) {
  if (!summary?.docs?.length) return null
  return (
    <div className="space-y-3">
      {summary.docs.map((doc, i) => (
        <div key={i} className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">🖼️</span>
              <span className="text-sm font-medium text-slate-200 truncate">{doc.file}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                ${doc.quality === 'GOOD' ? 'bg-teal-500/20 text-teal-300' :
                  doc.quality === 'DEGRADED' ? 'bg-amber-500/20 text-amber-300' :
                  'bg-red-500/20 text-red-300'}`}>
                {doc.quality}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-plum-500/20 text-plum-300 font-medium">
                {doc.type?.replace(/_/g,' ')}
              </span>
            </div>
          </div>
          {doc.confidence != null && (
            <div>
              <p className="text-xs text-slate-500 mb-1">Classification confidence</p>
              <ConfBar value={doc.confidence} />
            </div>
          )}
          {doc.llm_reasoning && (
            <div className="bg-plum-900/20 border border-plum-800/30 rounded-lg px-3 py-2">
              <p className="text-xs text-slate-500 mb-1">🤖 LLM reasoning</p>
              <p className="text-xs text-slate-300 leading-relaxed">{doc.llm_reasoning}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Doc Parser renderer ────────────────────────────────────────────────────
function DocParserOutput({ summary }) {
  if (!summary?.extractions?.length) return null
  return (
    <div className="space-y-3">
      {summary.extractions.map((ext, i) => (
        <div key={i} className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50 space-y-3">
          <p className="text-xs font-medium text-slate-400 font-mono">{ext.file}</p>

          {/* Extracted fields */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
            {ext.patient   && <div><span className="text-slate-500">Patient </span><span className="text-slate-200">{ext.patient}</span></div>}
            {ext.doctor    && <div><span className="text-slate-500">Doctor </span><span className="text-slate-200">{ext.doctor}</span></div>}
            {ext.hospital  && <div><span className="text-slate-500">Hospital </span><span className="text-slate-200">{ext.hospital}</span></div>}
            {ext.diagnosis && <div className="col-span-2"><span className="text-slate-500">Diagnosis </span><span className="text-amber-300 font-medium">{ext.diagnosis}</span></div>}
            {ext.total_amount != null && <div><span className="text-slate-500">Total </span><span className="text-teal-300 font-mono">₹{ext.total_amount?.toLocaleString('en-IN')}</span></div>}
          </div>

          {/* Field confidences */}
          {ext.field_confidences && Object.keys(ext.field_confidences).length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-slate-500">Field confidences</p>
              {Object.entries(ext.field_confidences).map(([field, conf]) => (
                <div key={field} className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 w-32 shrink-0 capitalize">
                    {field.replace(/_/g,' ')}
                  </span>
                  <ConfBar value={conf} />
                </div>
              ))}
            </div>
          )}

          {/* LLM extraction notes */}
          {ext.llm_notes && (
            <div className="bg-plum-900/20 border border-plum-800/30 rounded-lg px-3 py-2">
              <p className="text-xs text-slate-500 mb-1">🤖 LLM extraction notes</p>
              <p className="text-xs text-slate-300 leading-relaxed">{ext.llm_notes}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Rules Engine renderer ──────────────────────────────────────────────────
function RulesEngineOutput({ summary }) {
  if (!summary?.rule_verdicts?.length) return null
  return (
    <div className="space-y-3">
      {/* Financial summary */}
      {summary.net_amount != null && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Net Amount', value: `₹${summary.net_amount?.toLocaleString('en-IN')}`, accent: 'text-teal-300' },
            { label: 'Network Discount', value: `₹${summary.network_discount?.toLocaleString('en-IN')}`, accent: 'text-amber-300' },
            { label: 'Co-pay', value: `₹${summary.copay?.toLocaleString('en-IN')}`, accent: 'text-slate-300' },
          ].map(({ label, value, accent }) => (
            <div key={label} className="bg-slate-800/60 rounded-lg p-3 text-center">
              <p className="text-xs text-slate-500">{label}</p>
              <p className={`text-sm font-mono font-medium mt-0.5 ${accent}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Rule verdicts */}
      <div className="space-y-1">
        {summary.rule_verdicts.map((r, i) => (
          <div key={i} className={`flex items-start gap-3 rounded-lg px-3 py-2.5 text-xs
            ${r.passed ? 'bg-teal-900/10 border border-teal-800/20' : 'bg-red-900/15 border border-red-800/30'}`}>
            <span className={`mt-0.5 shrink-0 ${r.passed ? 'text-teal-400' : 'text-red-400'}`}>
              {r.passed ? '✓' : '✗'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`font-medium capitalize ${r.passed ? 'text-teal-300' : 'text-red-300'}`}>
                  {r.rule.replace(/_/g,' ')}
                </span>
                {r.rejection_code && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/40 text-red-300 font-mono">
                    {r.rejection_code}
                  </span>
                )}
              </div>
              <p className="text-slate-400 mt-0.5 leading-relaxed">{r.reason}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Fraud Detector renderer ────────────────────────────────────────────────
function FraudDetectorOutput({ summary }) {
  const score = summary.fraud_score || 0
  const signals = summary.signals || []
  const scoreColor = score >= 0.8 ? 'text-red-300' : score >= 0.5 ? 'text-amber-300' : 'text-teal-300'
  const scoreBg = score >= 0.8 ? 'bg-red-500/15 border-red-600/30' : score >= 0.5 ? 'bg-amber-500/15 border-amber-600/30' : 'bg-teal-500/15 border-teal-600/30'
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div className={`rounded-lg p-3 text-center border ${scoreBg}`}>
          <p className="text-xs text-slate-500">Fraud Score</p>
          <p className={`text-2xl font-mono font-bold mt-0.5 ${scoreColor}`}>{Math.round(score * 100)}%</p>
        </div>
        <div className={`rounded-lg p-3 text-center border ${summary.manual_review ? 'bg-amber-500/15 border-amber-600/30' : 'bg-slate-800/60 border-slate-700'}`}>
          <p className="text-xs text-slate-500">Outcome</p>
          <p className={`text-sm font-medium mt-1 ${summary.manual_review ? 'text-amber-300' : 'text-teal-300'}`}>
            {summary.manual_review ? '⚠ Manual Review' : '✓ Clear'}
          </p>
        </div>
      </div>
      {signals.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">Signals ({signals.length})</p>
          {signals.map((sig, i) => {
            const sev = sig.severity || 0
            const isHigh = sev >= 0.7
            const isMed = sev >= 0.4
            return (
              <div key={i} className={`rounded-xl border p-3 space-y-1 ${isHigh ? 'bg-red-900/15 border-red-800/40' : isMed ? 'bg-amber-900/15 border-amber-800/40' : 'bg-slate-800/40 border-slate-700'}`}>
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-semibold ${isHigh ? 'text-red-300' : isMed ? 'text-amber-300' : 'text-slate-400'}`}>
                    {isHigh ? '🔴' : isMed ? '🟡' : '🔵'} {sig.type?.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${isHigh ? 'bg-red-900/40 text-red-300' : isMed ? 'bg-amber-900/40 text-amber-300' : 'bg-slate-700 text-slate-400'}`}>
                    {Math.round(sev * 100)}% severity
                  </span>
                </div>
                {sig.detail && <p className="text-xs text-slate-400 leading-relaxed">{sig.detail}</p>}
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-3 text-xs text-teal-400/70">✓ No fraud signals detected</div>
      )}
    </div>
  )
}

function DecisionOutput({ summary }) {
  const decisionColors = {
    APPROVED: 'text-teal-300 bg-teal-500/15 border-teal-600/30',
    PARTIAL: 'text-amber-300 bg-amber-500/15 border-amber-600/30',
    REJECTED: 'text-red-300 bg-red-500/15 border-red-600/30',
    MANUAL_REVIEW: 'text-plum-300 bg-plum-500/15 border-plum-600/30',
  }
  const colors = decisionColors[summary.decision] || decisionColors.MANUAL_REVIEW
  return (
    <div className="space-y-3">
      <div className={`rounded-xl p-4 border text-center ${colors}`}>
        <p className="text-xs opacity-70 mb-1">Final Decision</p>
        <p className="text-xl font-semibold">{summary.decision}</p>
        <p className="text-sm font-mono mt-1">₹{(summary.approved_amount || 0).toLocaleString('en-IN')} approved</p>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-slate-800/60 rounded-lg p-3">
          <p className="text-slate-500">Confidence</p>
          <ConfBar value={summary.confidence} />
        </div>
        <div className="bg-slate-800/60 rounded-lg p-3">
          <p className="text-slate-500">Manual Review</p>
          <p className={`font-medium mt-1 ${summary.manual_review ? 'text-amber-300' : 'text-teal-300'}`}>
            {summary.manual_review ? 'Flagged' : 'Not required'}
          </p>
        </div>
      </div>
      {summary.rejections?.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 mb-1.5">Rejection reasons</p>
          <div className="flex flex-wrap gap-1.5">
            {summary.rejections.map(r => (
              <span key={r} className="text-xs px-2 py-1 rounded-full bg-red-900/30 border border-red-800/40 text-red-300 font-mono">{r}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Generic JSON fallback ──────────────────────────────────────────────────
function GenericOutput({ data }) {
  if (!data || Object.keys(data).length === 0) return null
  return (
    <pre className="text-xs text-slate-300 font-mono bg-slate-800/60 rounded-lg p-3 overflow-auto">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

// ── Single trace entry ─────────────────────────────────────────────────────
function TraceEntry({ entry }) {
  const [open, setOpen] = useState(false)
  const hasError = !!entry.error
  const hasOutput = entry.output_summary && Object.keys(entry.output_summary).length > 0

  function renderOutput(component, summary) {
    if (component.includes('DocVerifier')) return <DocVerifierOutput summary={summary} />
    if (component.includes('DocParser'))  return <DocParserOutput summary={summary} />
    if (component.includes('RulesEngine')) return <RulesEngineOutput summary={summary} />
    if (component.includes('Fraud'))      return <FraudDetectorOutput summary={summary} />
    if (component.includes('Aggregator') || component.includes('Decision')) return <DecisionOutput summary={summary} />
    return <GenericOutput data={summary} />
  }

  return (
    <div className={`rounded-xl border overflow-hidden ${hasError ? 'border-red-800/50 bg-red-900/10' : 'border-slate-800 bg-slate-900/40'}`}>
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-800/20 transition-colors">
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full shrink-0 ${hasError ? 'bg-red-400' : 'bg-teal-400'}`} />
          <span className="text-sm font-medium text-slate-200">{entry.component}</span>
          {hasError && <span className="text-xs text-red-400 bg-red-900/30 px-2 py-0.5 rounded-full">error</span>}
        </div>
        <div className="flex items-center gap-3">
          {entry.duration_ms != null && (
            <span className="text-xs text-slate-500 font-mono">{entry.duration_ms}ms</span>
          )}
          <span className="text-slate-600 text-xs">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-slate-800/60 pt-3 space-y-3 animate-fade-in">
          {entry.error && (
            <div className="text-xs font-mono text-red-300 bg-red-900/20 rounded-lg p-3">{entry.error}</div>
          )}
          {hasOutput && renderOutput(entry.component, entry.output_summary)}
        </div>
      )}
    </div>
  )
}

// ── Main TraceViewer ───────────────────────────────────────────────────────
export default function TraceViewer({ trace }) {
  const [open, setOpen] = useState(false)
  if (!trace || !trace.entries?.length) return null

  const hasErrors = trace.entries.some(e => e.error)
  const totalMs = trace.total_duration_ms || 0
  const llmMs = trace.entries
    .filter(e => e.component.includes('Verifier') || e.component.includes('Parser'))
    .reduce((s, e) => s + (e.duration_ms || 0), 0)

  return (
    <div className="card p-5">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-slate-400">🔍</span>
          <span className="text-sm font-medium text-slate-300">Pipeline Trace</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-600 font-mono">{trace.entries.length} stages · {totalMs}ms</span>
            {llmMs > 0 && (
              <span className="text-xs text-plum-400/70 font-mono">({llmMs}ms LLM)</span>
            )}
            {hasErrors && (
              <span className="text-xs bg-amber-900/30 text-amber-300 px-2 py-0.5 rounded-full border border-amber-800/40">
                has failures
              </span>
            )}
          </div>
        </div>
        <span className="text-slate-600 text-xs">{open ? '▲ Hide' : '▼ Show'}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-2 animate-fade-in">
          {trace.entries.map((e, i) => (
            <TraceEntry key={i} entry={e} />
          ))}
        </div>
      )}
    </div>
  )
}