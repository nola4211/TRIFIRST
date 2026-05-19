import { useState } from 'react'
import Layout from '../components/Layout'
import ChatMessage from '../components/ChatMessage'

export default function CoachTri() {
  const [messages, setMessages] = useState([{ role: 'coach', text: 'Ready for this week. Shall I build a taper plan?' }])
  const [text, setText] = useState(''); const [loading, setLoading] = useState(false)
  const send = async () => { if (!text) return; setLoading(true); setMessages([{ role: 'user', text }, ...messages]); setText(''); setTimeout(()=>{setMessages((prev)=>[{ role:'coach', text:'Plan drafted. I proposed workouts for calendar review.' }, ...prev]); setLoading(false)}, 900) }
  return <Layout><div className="grid gap-4 lg:grid-cols-4"><section className="space-y-3 rounded-xl bg-dark-900 p-4 lg:col-span-3"><h1 className="text-2xl font-bold text-primary">🏅 Coach Tri</h1><div className="flex gap-2"><input value={text} onChange={e=>setText(e.target.value)} className="flex-1 rounded bg-dark-700 p-2" placeholder="Ask Coach Tri..."/><button onClick={send} className="rounded bg-primary px-3 py-2 text-black">Send</button></div>{loading && <p className="text-gray-400">Coach Tri is thinking...</p>}<div className="space-y-3">{messages.slice(0,10).map((m, i)=><ChatMessage key={i} message={m}/> )}</div><div className="rounded-lg bg-primary/20 p-3 text-primary">📅 Workouts proposed — review on <a href="/calendar" className="underline">Calendar</a></div></section>
  <aside className="rounded-xl bg-dark-800 p-4"><h2 className="text-lg font-semibold">About You</h2><textarea className="mt-3 h-40 w-full rounded bg-dark-700 p-2" defaultValue={'Injury history: mild IT band\nLimitations: no double runs\nPreferred days: long bike Sat'} /><button className="mt-3 w-full rounded bg-primary p-2 text-black">Save</button><hr className="my-4 border-dark-600"/><div className="rounded bg-dark-700 p-3 text-sm"><p>Days until race: 72</p><p>This week km: 38</p><p>Latest stats: improving bike FTP</p></div></aside></div></Layout>
}
