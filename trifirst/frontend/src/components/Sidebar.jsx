import { LayoutDashboard, CalendarDays, Medal, RefreshCw, LogOut } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { syncStrava } from '../api/activities'

export default function Sidebar() {
  const navigate = useNavigate()
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  const handleLogout = () => {
    localStorage.removeItem('user')
    navigate('/')
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
          <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-2 rounded-lg px-3 py-2 ${isActive ? 'bg-primary text-black' : 'hover:bg-dark-700'}`}>
            <Icon size={16} /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="my-4 border-t border-dark-600" />
      <button onClick={() => syncStrava()} className="mb-2 flex items-center gap-2 rounded-lg bg-dark-700 px-3 py-2 hover:bg-primary hover:text-black"><RefreshCw size={16}/> Sync Strava</button>
      <button onClick={handleLogout} className="mt-auto flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-red-600"><LogOut size={16}/> Logout</button>
      <p className="mt-2 text-xs text-gray-400">{user.name || user.username}</p>
    </aside>
  )
}
