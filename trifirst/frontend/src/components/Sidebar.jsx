import { LayoutDashboard, CalendarDays, Medal, RefreshCw, LogOut } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { syncStrava } from '../api/activities'

export default function Sidebar() {
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('trifirst_user') || '{}')
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')

  const handleLogout = () => {
    localStorage.removeItem('trifirst_user')
    navigate('/')
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncMsg('')
    try {
      const res = await syncStrava(user.user_id)
      setSyncMsg(`✅ ${res.data.activities_added} added`)
    } catch {
      setSyncMsg('❌ Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <aside className="flex h-screen w-60 flex-col bg-dark-800 p-4">
      <div className="mb-8 text-2xl font-bold">🏊🚴🏃 TriFirst</div>
      <nav className="space-y-2">
        {[
          { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
          { to: '/coach', icon: Medal, label: 'Coach Tri' },
          { to: '/calendar', icon: CalendarDays, label: 'Calendar' },
        ].map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-3 py-2 ${isActive ? 'bg-primary text-black' : 'hover:bg-dark-700'}`
            }
          >
            <Icon size={16} /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="my-4 border-t border-dark-600" />
      <button
        onClick={handleSync}
        disabled={syncing}
        className="mb-2 flex items-center gap-2 rounded-lg bg-dark-700 px-3 py-2 hover:bg-primary hover:text-black disabled:opacity-50"
      >
        <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
        {syncing ? 'Syncing...' : 'Sync Strava'}
      </button>
      {syncMsg && <p className="mb-2 text-xs">{syncMsg}</p>}
      <button
        onClick={handleLogout}
        className="mt-auto flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-red-600"
      >
        <LogOut size={16} /> Logout
      </button>
      <p className="mt-2 text-xs text-gray-400">{user.name || user.username}</p>
    </aside>
  )
}
