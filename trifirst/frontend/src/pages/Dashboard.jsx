import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import Layout from '../components/Layout'
import StatCard from '../components/StatCard'
import ActivityRow from '../components/ActivityRow'
import { getActivities } from '../api/activities'

export default function Dashboard() {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const [activities, setActivities] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  useEffect(() => { getActivities().then(r=>setActivities(r.data||[])).catch(()=>setError('Failed to load dashboard data')).finally(()=>setLoading(false)) }, [])
  const greeting = useMemo(() => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }, [])
  const weekly = [{week:'W1',swim:4,bike:6,run:5},{week:'W2',swim:5,bike:7,run:6},{week:'W3',swim:4,bike:8,run:7},{week:'W4',swim:6,bike:9,run:6}]
  return <Layout><div className="space-y-6"><div><h1 className="text-3xl font-bold">{greeting}, {user.name || user.username} 👋</h1><p className="text-primary">72 days until race day</p></div>
    <div className="grid gap-4 md:grid-cols-3"><StatCard title="Total Activities" value={activities.length} loading={loading}/><StatCard title="Total Distance (km)" value={activities.reduce((a,c)=>a+(c.distance||0),0)} loading={loading}/><StatCard title="Swim / Bike / Run" value={`${activities.filter(a=>a.type==='swim').length}/${activities.filter(a=>a.type==='bike').length}/${activities.filter(a=>a.type==='run').length}`}/></div>
    {error && <p className="text-red-400">{error}</p>}
    <div className="rounded-xl bg-dark-800 p-4"><h2 className="mb-3 text-xl font-semibold">Recent Activities</h2><table className="w-full text-left text-sm"><thead><tr className="text-gray-300"><th className="p-3">Date</th><th className="p-3">Type</th><th className="p-3">Distance</th><th className="p-3">Duration</th><th className="p-3">Avg HR</th></tr></thead><tbody>{activities.slice(0,10).map((a,idx)=><ActivityRow key={idx} activity={a}/> )}</tbody></table></div>
    <div className="rounded-xl bg-dark-800 p-4"><h2 className="mb-3 text-xl font-semibold">Weekly Volume</h2><div className="h-72"><ResponsiveContainer><BarChart data={weekly}><CartesianGrid stroke="#2D3148"/><XAxis dataKey="week"/><YAxis/><Tooltip/><Bar dataKey="swim" fill="#38BDF8"/><Bar dataKey="bike" fill="#FB923C"/><Bar dataKey="run" fill="#4ADE80"/></BarChart></ResponsiveContainer></div></div>
    <div className="rounded-xl border-l-4 border-primary bg-dark-800 p-4"><h3 className="font-semibold">Weekly Digest</h3><p className="my-2 text-gray-300">Solid consistency this week with improved bike endurance. Focus on recovery before weekend long run.</p><button className="rounded bg-primary px-4 py-2 text-black">Generate Digest</button></div>
    <div className="rounded-xl bg-dark-800 p-4"><h3 className="font-semibold">Race Day Calculator</h3><p className="mt-4 text-4xl font-bold text-primary">11h 48m</p><details className="mt-4"><summary className="cursor-pointer">Nutrition plan</summary><p className="mt-2 text-gray-300">90g carbs/hr on bike, 60g/hr on run, 600-800ml fluids/hr.</p></details></div>
  </div></Layout>
}
