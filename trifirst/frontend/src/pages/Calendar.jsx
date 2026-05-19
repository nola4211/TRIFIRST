import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import Layout from '../components/Layout'
import WorkoutCard from '../components/WorkoutCard'

export default function Calendar() {
  const [month, setMonth] = useState(new Date())
  const [selected, setSelected] = useState(null)
  const [checked, setChecked] = useState([])
  const pending = [{ id: 1, type: 'swim', title: '2.5km drills' }, { id: 2, type: 'run', title: 'Tempo 8km' }]
  const days = useMemo(() => Array.from({ length: 30 }, (_, i) => i + 1), [month])
  return <Layout><div className="space-y-4">{pending.length>0 && <div className="rounded-lg bg-primary/20 p-4"><p className="font-semibold text-primary">Coach Tri proposed {pending.length} workouts</p><div className="mt-2 space-y-2">{pending.map(w => <WorkoutCard key={w.id} workout={w} checked={checked.includes(w.id)} onToggle={(id)=>setChecked(c=>c.includes(id)?c.filter(x=>x!==id):[...c,id])} />)}</div><div className="mt-3 flex gap-2"><button className="rounded bg-primary px-3 py-2 text-black">Confirm Selected</button><button className="rounded bg-dark-700 px-3 py-2">Dismiss</button></div></div>}
  <div className="flex items-center justify-between"><div className="flex items-center gap-2"><button onClick={()=>setMonth(new Date(month.getFullYear(), month.getMonth()-1,1))}><ChevronLeft/></button><h1 className="text-3xl font-bold">{month.toLocaleString('default',{month:'long',year:'numeric'})}</h1><button onClick={()=>setMonth(new Date(month.getFullYear(), month.getMonth()+1,1))}><ChevronRight/></button></div><button className="rounded bg-primary px-3 py-2 text-black" onClick={()=>setMonth(new Date())}>Today</button></div>
  <div className="grid grid-cols-7 gap-2 text-center text-primary">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=><div key={d}>{d}</div>)}</div>
  <div className="grid grid-cols-7 gap-2">{days.map((d)=><button key={d} onClick={()=>setSelected(d)} className="min-h-24 rounded-lg bg-dark-800 p-2 text-right hover:border hover:border-primary"><div>{d}</div>{d%5===0&&<span className="mt-2 inline-block rounded-full bg-bike px-2 text-xs text-black">bike</span>}</button>)}</div>
  {selected && <div className="rounded-xl bg-dark-800 p-4"><h2 className="text-xl">Day {selected} details</h2><p className="my-2">Workout: Endurance run 10km</p><div className="flex gap-2"><button className="rounded bg-green-500 px-3 py-2 text-black">Mark Complete</button><button className="rounded bg-gray-500 px-3 py-2">Skip</button><button className="rounded bg-red-500 px-3 py-2">Delete</button></div><form className="mt-3 grid gap-2 md:grid-cols-3"><input className="rounded bg-dark-700 p-2" placeholder="Workout title"/><select className="rounded bg-dark-700 p-2"><option>swim</option><option>bike</option><option>run</option><option>rest</option></select><button className="rounded bg-primary p-2 text-black">Add Workout</button></form></div>}
  </div></Layout>
}
