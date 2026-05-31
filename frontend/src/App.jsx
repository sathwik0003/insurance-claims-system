import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import SubmitClaim from './pages/SubmitClaim'
import ClaimResult from './pages/ClaimResult'
import EvalRunner from './pages/EvalRunner'
import MemberLookup from './pages/MemberLookup'
import { getHealth } from './api/client'

const NAV = [
  { to: '/',       label: 'Submit Claim', icon: '📋' },
  { to: '/eval',   label: 'Eval Runner',  icon: '🧪' },
  { to: '/member', label: 'Members',      icon: '👤' },
]

export default function App() {
  const [apiOk, setApiOk] = useState(null)
  const location = useLocation()

  useEffect(() => {
    getHealth()
      .then(() => setApiOk(true))
      .catch(() => setApiOk(false))
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-8">
          <div className="flex items-center gap-2.5 shrink-0">
            <span className="text-xl">🩺</span>
            <span className="font-semibold text-sm tracking-wide text-white">
              Plum <span className="text-plum-400">Claims</span>
            </span>
          </div>

          <nav className="flex items-center gap-1">
            {NAV.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ` +
                  (isActive
                    ? 'bg-plum-600/20 text-plum-300 border border-plum-700/40'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60')
                }
              >
                <span>{icon}</span>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${apiOk === true ? 'bg-teal-400' : apiOk === false ? 'bg-red-400' : 'bg-slate-600 animate-pulse'}`} />
            <span className="text-xs text-slate-500">
              {apiOk === true ? 'API connected' : apiOk === false ? 'API offline' : 'Connecting…'}
            </span>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8">
        <Routes>
          <Route path="/"           element={<SubmitClaim />} />
          <Route path="/claim/:id"  element={<ClaimResult />} />
          <Route path="/eval"       element={<EvalRunner />} />
          <Route path="/member"     element={<MemberLookup />} />
        </Routes>
      </main>

      <footer className="border-t border-slate-800/50 py-4 text-center text-xs text-slate-600">
        Plum Claims Processing — AI-powered pipeline
      </footer>
    </div>
  )
}