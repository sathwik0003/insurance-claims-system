import { useState, useEffect } from 'react'
import { getMemberClaims, listMembers } from '../api/client'
import DecisionBadge from '../components/DecisionBadge'
import Spinner from '../components/Spinner'

export default function MemberLookup() {
  const [members, setMembers]         = useState([])
  const [selected, setSelected]       = useState(null)
  const [claims, setClaims]           = useState([])
  const [loadingMembers, setLoadingMembers] = useState(true)
  const [loadingClaims, setLoadingClaims]   = useState(false)
  const [search, setSearch]           = useState('')

  useEffect(() => {
    listMembers()
      .then((d) => setMembers(d.members || []))
      .catch(() => {})
      .finally(() => setLoadingMembers(false))
  }, [])

  async function select(m) {
    setSelected(m)
    setLoadingClaims(true)
    try {
      const d = await getMemberClaims(m.member_id)
      setClaims(d.claims || [])
    } catch {
      setClaims([])
    } finally {
      setLoadingClaims(false)
    }
  }

  const filtered = members.filter(
    (m) =>
      m.member_id?.toLowerCase().includes(search.toLowerCase()) ||
      m.name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="max-w-5xl mx-auto animate-slide-up">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white">Members</h1>
        <p className="text-slate-400 text-sm mt-1">Browse members and their claim history.</p>
      </div>

      {/* Two-column layout — both columns scroll independently */}
      <div className="flex gap-6 items-start">

        {/* Left — member list, fixed height, scrollable */}
        <div className="w-64 shrink-0 flex flex-col gap-3 sticky top-20">
          <input
            className="input"
            placeholder="Search name or ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="overflow-y-auto max-h-[calc(100vh-220px)] pr-1 space-y-1.5">
            {loadingMembers ? (
              <Spinner size="sm" label="Loading…" />
            ) : filtered.length === 0 ? (
              <p className="text-xs text-slate-600 text-center py-4">No members found</p>
            ) : (
              filtered.map((m) => (
                <button
                  key={m.member_id}
                  onClick={() => select(m)}
                  className={`w-full text-left px-4 py-3 rounded-xl border transition-all duration-150 ${
                    selected?.member_id === m.member_id
                      ? 'bg-plum-600/20 border-plum-600/40 text-white'
                      : 'bg-slate-900/40 border-slate-800 text-slate-300 hover:bg-slate-800/60 hover:border-slate-700'
                  }`}
                >
                  <p className="text-sm font-medium truncate">{m.name}</p>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">{m.member_id}</p>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right — detail panel */}
        <div className="flex-1 min-w-0">
          {!selected ? (
            <div className="card p-10 flex flex-col items-center justify-center text-center h-64">
              <p className="text-slate-600 text-3xl mb-3">👤</p>
              <p className="text-slate-500 text-sm">Select a member to view details</p>
            </div>
          ) : (
            <div className="space-y-4 animate-fade-in">
              {/* Member info card */}
              <div className="card p-5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{selected.name}</h2>
                    <p className="text-xs font-mono text-slate-500">{selected.member_id}</p>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-teal-500/15 border border-teal-600/30 text-teal-300">
                    {selected.plan || 'Standard'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {selected.email      && <div><p className="label">Email</p><p className="text-slate-300 truncate">{selected.email}</p></div>}
                  {selected.join_date  && <div><p className="label">Joined</p><p className="text-slate-300">{selected.join_date}</p></div>}
                  {selected.sum_insured && (
                    <div>
                      <p className="label">Sum Insured</p>
                      <p className="text-slate-300 font-mono">₹{Number(selected.sum_insured).toLocaleString('en-IN')}</p>
                    </div>
                  )}
                  {selected.relationship && <div><p className="label">Relationship</p><p className="text-slate-300">{selected.relationship}</p></div>}
                </div>
              </div>

              {/* Claim history */}
              <div className="card p-5 space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Claim History
                </h3>

                {loadingClaims ? (
                  <Spinner size="sm" label="Loading claims…" />
                ) : claims.length === 0 ? (
                  <p className="text-sm text-slate-600 py-4 text-center">No claims on record</p>
                ) : (
                  <div className="divide-y divide-slate-800">
                    {claims.map((c) => (
                      <div key={c.claim_id} className="py-3 flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm text-slate-200 truncate">
                            {c.claim_category?.replace(/_/g, ' ')} — {c.treatment_date}
                          </p>
                          <p className="text-xs text-slate-500 font-mono mt-0.5 truncate">{c.claim_id}</p>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <p className="text-xs font-mono text-slate-300">
                            ₹{Number(c.approved_amount || 0).toLocaleString('en-IN')}
                            <span className="text-slate-600"> / ₹{Number(c.claimed_amount).toLocaleString('en-IN')}</span>
                          </p>
                          <DecisionBadge decision={c.decision} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}