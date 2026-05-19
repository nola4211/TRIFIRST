import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import Layout from '../components/Layout'
import { getCalendar, getPendingWorkouts, confirmWorkouts, dismissPending, updateWorkoutStatus, deleteWorkout, scheduleWorkout } from '../api/calendar'

const TYPE_COLORS = { swim: 'bg-sky-500', bike: 'bg-orange-400', run: 'bg-green-400', brick: 'bg-purple-400', rest: 'bg-gray-500' }
const TYPE_EMOJI = { swim: '🏊', bike: '🚴', run: '🏃', brick: '🧱', rest: '💤' }

export default function Calendar() {
  const user = JSON.parse(localStorage.getItem('trifirst_user') || '{}')
  const userId = user.user_id
  const [month, setMonth] = useState(new Date())
  const [selected, setSelected] = useState(null)
  const [workouts, setWorkouts] = useState([])
  const [pending, setPending] = useState(null)
  const [checkedIds, setCheckedIds] = useState([])
  const [loading, setLoading] = useState(true)
  const [newWorkout, setNewWorkout] = useState({ title: '', activity_type: 'run', duration_mins: 30 })
  const [error, setError] = useState('')

  const monthStr = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`

  const loadData = async () => {
    if (!userId) return
    setLoading(true)
    try {
      const [calRes, pendRes] = await Promise.all([
        getCalendar(userId, monthStr),
        getPendingWorkouts(userId),
      ])
      setWorkouts(calRes.data || [])
      const p = pendRes.data
      if (p && p.id) {
        const parsed = JSON.parse(p.workouts_json || '[]')
        setPending({ ...p, workouts: parsed })
        setCheckedIds(parsed.map(w => w.id))
      } else {
        setPending(null)
      }
    } catch {
      setError('Failed to load calendar')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [userId, monthStr])

  const daysInMonth = useMemo(() => {
    const year = month.getFullYear()
    const mon = month.getMonth()
    const firstDay = new Date(year, mon, 1).getDay()
    const offset = firstDay === 0 ? 6 : firstDay - 1
    const total = new Date(year, mon + 1, 0).getDate()
    return { offset, total }
  }, [month])

  const workoutsByDate = useMemo(() => {
    const map = {}
    workouts.forEach(w => {
      const d = new Date(w.date).getDate()
      if (!map[d]) map[d] = []
      map[d].push(w)
    })
    return map
  }, [workouts])

  const selectedWorkouts = selected ? (workoutsByDate[selected] || []) : []

  const handleConfirm = async () => {
    if (!pending) return
    try {
      await confirmWorkouts({ user_id: userId, pending_id: pending.id, selected_ids: checkedIds })
      setPending(null)
      loadData()
    } catch { setError('Failed to confirm workouts') }
  }

  const handleDismiss = async () => {
    if (!pending) return
    try {
      await dismissPending(pending.id)
      setPending(null)
    } catch { setError('Failed to dismiss') }
  }

  const handleStatusUpdate = async (workoutId, status) => {
    try {
      await updateWorkoutStatus(workoutId, status)
      loadData()
    } catch { setError('Failed to update workout') }
  }

  const handleDelete = async (workoutId) => {
    try {
      await deleteWorkout(workoutId)
      loadData()
    } catch { setError('Failed to delete workout') }
  }

  const handleAddWorkout = async (e) => {
    e.preventDefault()
    if (!selected || !newWorkout.title) return
    const dateStr = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}-${String(selected).padStart(2, '0')}`
    try {
      await scheduleWorkout({ ...newWorkout, user_id: userId, date: dateStr, source: 'manual' })
      setNewWorkout({ title: '', activity_type: 'run', duration_mins: 30 })
      loadData()
    } catch { setError('Failed to add workout') }
  }

  return (
    <Layout>
      <div className="space-y-4">
        {error && <p className="text-red-400">{error}</p>}

        {/* Pending workouts banner */}
        {pending && (
          <div className="rounded-lg bg-orange-500/20 border border-orange-500/40 p-4">
            <p className="font-semibold text-primary">🏅 Coach Tri proposed {pending.workouts.length} workouts</p>
            <div className="mt-2 space-y-2">
              {pending.workouts.map(w => (
                <label key={w.id} className="flex items-center gap-3 rounded-lg bg-dark-700 p-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checkedIds.includes(w.id)}
                    onChange={() => setCheckedIds(c => c.includes(w.id) ? c.filter(x => x !== w.id) : [...c, w.id])}
                    className="accent-orange-500"
                  />
                  <span>{TYPE_EMOJI[w.activity_type]} {w.title}</span>
                  <span className="ml-auto text-sm text-gray-400">{w.date} · {w.duration_mins}min · {w.intensity}</span>
                </label>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <button onClick={handleConfirm} className="rounded bg-primary px-4 py-2 text-black font-semibold">
                ✅ Confirm Selected ({checkedIds.length})
              </button>
              <button onClick={handleDismiss} className="rounded bg-dark-700 px-4 py-2 hover:bg-dark-600">
                ❌ Dismiss All
              </button>
            </div>
          </div>
        )}

        {/* Month navigation */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="rounded p-1 hover:bg-dark-700">
              <ChevronLeft />
            </button>
            <h1 className="text-3xl font-bold">{month.toLocaleString('default', { month: 'long', year: 'numeric' })}</h1>
            <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="rounded p-1 hover:bg-dark-700">
              <ChevronRight />
            </button>
          </div>
          <button onClick={() => setMonth(new Date())} className="rounded bg-primary px-3 py-2 text-black font-semibold">Today</button>
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7 gap-2 text-center font-semibold text-primary">
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => <div key={d}>{d}</div>)}
        </div>

        {/* Calendar grid */}
        {loading ? <p className="text-gray-400">Loading...</p> : (
          <div className="grid grid-cols-7 gap-2">
            {Array.from({ length: daysInMonth.offset }).map((_, i) => <div key={`empty-${i}`} />)}
            {Array.from({ length: daysInMonth.total }, (_, i) => i + 1).map(d => {
              const today = new Date()
              const isToday = d === today.getDate() && month.getMonth() === today.getMonth() && month.getFullYear() === today.getFullYear()
              const dayWorkouts = workoutsByDate[d] || []
              return (
                <button
                  key={d}
                  onClick={() => setSelected(d)}
                  className={`min-h-20 rounded-lg bg-dark-800 p-2 text-right hover:border hover:border-primary ${isToday ? 'border border-primary' : ''} ${selected === d ? 'border-2 border-primary' : ''}`}
                >
                  <div className={`text-sm ${isToday ? 'text-primary font-bold' : 'text-gray-400'}`}>{d}</div>
                  <div className="mt-1 space-y-1">
                    {dayWorkouts.map((w, i) => (
                      <div key={i} className={`rounded-full px-2 py-0.5 text-xs text-left text-black font-medium ${TYPE_COLORS[w.activity_type] || 'bg-gray-500'} ${w.status === 'completed' ? 'opacity-100' : w.status === 'skipped' ? 'opacity-40 line-through' : 'opacity-80'}`}>
                        {TYPE_EMOJI[w.activity_type]} {w.title?.slice(0, 10)}
                      </div>
                    ))}
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Day detail panel */}
        {selected && (
          <div className="rounded-xl bg-dark-800 p-4">
            <h2 className="mb-3 text-xl font-semibold">
              {month.toLocaleString('default', { month: 'long' })} {selected}
            </h2>
            {selectedWorkouts.length === 0 ? (
              <p className="text-gray-400 mb-3">No workouts scheduled.</p>
            ) : (
              <div className="space-y-2 mb-4">
                {selectedWorkouts.map(w => (
                  <div key={w.id} className="flex items-center justify-between rounded-lg bg-dark-700 p-3">
                    <div>
                      <span className="font-semibold">{TYPE_EMOJI[w.activity_type]} {w.title}</span>
                      <p className="text-sm text-gray-400">{w.duration_mins}min · {w.intensity} · {w.description}</p>
                    </div>
                    <div className="flex gap-2">
                      {w.status !== 'completed' && (
                        <button onClick={() => handleStatusUpdate(w.id, 'completed')} className="rounded bg-green-500 px-2 py-1 text-xs text-black">✓ Done</button>
                      )}
                      {w.status !== 'skipped' && (
                        <button onClick={() => handleStatusUpdate(w.id, 'skipped')} className="rounded bg-gray-500 px-2 py-1 text-xs">Skip</button>
                      )}
                      <button onClick={() => handleDelete(w.id)} className="rounded bg-red-500 px-2 py-1 text-xs text-black">✕</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Add workout form */}
            <form onSubmit={handleAddWorkout} className="grid gap-2 md:grid-cols-4">
              <input
                className="rounded bg-dark-700 p-2 col-span-2"
                placeholder="Workout title"
                value={newWorkout.title}
                onChange={e => setNewWorkout(w => ({ ...w, title: e.target.value }))}
              />
              <select
                className="rounded bg-dark-700 p-2"
                value={newWorkout.activity_type}
                onChange={e => setNewWorkout(w => ({ ...w, activity_type: e.target.value }))}
              >
                <option value="swim">🏊 Swim</option>
                <option value="bike">🚴 Bike</option>
                <option value="run">🏃 Run</option>
                <option value="brick">🧱 Brick</option>
                <option value="rest">💤 Rest</option>
              </select>
              <button type="submit" className="rounded bg-primary p-2 text-black font-semibold">+ Add</button>
            </form>
          </div>
        )}
      </div>
    </Layout>
  )
}
