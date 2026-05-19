import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import Layout from '../components/Layout'
import StatCard from '../components/StatCard'
import ActivityRow from '../components/ActivityRow'
import { getActivities } from '../api/activities'
import { getRaceGoal, getDigests, generateDigest, getRaceCalculator } from '../api/dashboard'

const EMOJI = { swim: '🏊', bike: '🚴', run: '🏃' }

export default function Dashboard() {
  const user = JSON.parse(localStorage.getItem('trifirst_user') || '{}')
  const userId = user.user_id
  const [activities, setActivities] = useState([])
  const [raceGoal, setRaceGoal] = useState(null)
  const [digests, setDigests] = useState([])
  const [calculator, setCalculator] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generatingDigest, setGeneratingDigest] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!userId) return
    Promise.all([
      getActivities(userId),
      getRaceGoal(userId),
      getDigests(userId),
      getRaceCalculator(userId),
    ])
      .then(([actRes, raceRes, digestRes, calcRes]) => {
        setActivities(actRes.data || [])
        setRaceGoal(raceRes.data || null)
        setDigests(digestRes.data || [])
        setCalculator(calcRes.data || null)
      })
      .catch(() => setError('Failed to load dashboard data'))
      .finally(() => setLoading(false))
  }, [userId])

  const greeting = useMemo(() => {
    const h = new Date().getHours()
    return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
  }, [])

  const daysUntilRace = useMemo(() => {
    if (!raceGoal?.race_date) return null
    const diff = Math.ceil((new Date(raceGoal.race_date) - new Date()) / (1000 * 60 * 60 * 24))
    return diff > 0 ? diff : null
  }, [raceGoal])

  // Build weekly volume from activities
  const weeklyData = useMemo(() => {
    const weeks = {}
    activities.forEach(a => {
      const d = new Date(a.date)
      const week = `W${Math.ceil(d.getDate() / 7)}`
      if (!weeks[week]) weeks[week] = { week, swim: 0, bike: 0, run: 0 }
      if (a.activity_type === 'swim') weeks[week].swim += a.distance_km || 0
      if (a.activity_type === 'bike') weeks[week].bike += a.distance_km || 0
      if (a.activity_type === 'run') weeks[week].run += a.distance_km || 0
    })
    return Object.values(weeks).slice(-8)
  }, [activities])

  const totalKm = activities.reduce((a, c) => a + (c.distance_km || 0), 0).toFixed(1)
  const swimCount = activities.filter(a => a.activity_type === 'swim').length
  const bikeCount = activities.filter(a => a.activity_type === 'bike').length
  const runCount = activities.filter(a => a.activity_type === 'run').length

  const handleGenerateDigest = async () => {
    setGeneratingDigest(true)
    try {
      await generateDigest(userId)
      const res = await getDigests(userId)
      setDigests(res.data || [])
    } catch {
      setError('Failed to generate digest')
    } finally {
      setGeneratingDigest(false)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">{greeting}, {user.name || user.username} 👋</h1>
          {daysUntilRace && (
            <p className="text-primary">{daysUntilRace} days until {raceGoal.race_name} 🏁</p>
          )}
        </div>

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-3">
          <StatCard title="Total Activities" value={activities.length} loading={loading} />
          <StatCard title="Total Distance (km)" value={totalKm} loading={loading} />
          <StatCard title="Swim / Bike / Run" value={`${swimCount} / ${bikeCount} / ${runCount}`} loading={loading} />
        </div>

        {error && <p className="text-red-400">{error}</p>}

        {/* Recent Activities */}
        <div className="rounded-xl bg-dark-800 p-4">
          <h2 className="mb-3 text-xl font-semibold">Recent Activities</h2>
          {loading ? (
            <p className="text-gray-400">Loading...</p>
          ) : activities.length === 0 ? (
            <p className="text-gray-400">No activities yet — sync Strava to get started.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-gray-300">
                  <th className="p-3">Date</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Distance (km)</th>
                  <th className="p-3">Duration (mins)</th>
                  <th className="p-3">Avg HR</th>
                </tr>
              </thead>
              <tbody>
                {activities.slice(0, 10).map((a, idx) => (
                  <ActivityRow key={idx} activity={a} />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Weekly Volume Chart */}
        <div className="rounded-xl bg-dark-800 p-4">
          <h2 className="mb-3 text-xl font-semibold">Weekly Volume</h2>
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={weeklyData}>
                <CartesianGrid stroke="#2D3148" />
                <XAxis dataKey="week" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" />
                <Tooltip contentStyle={{ backgroundColor: '#1A1D27', border: 'none' }} />
                <Bar dataKey="swim" fill="#38BDF8" name="Swim" />
                <Bar dataKey="bike" fill="#FB923C" name="Bike" />
                <Bar dataKey="run" fill="#4ADE80" name="Run" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Weekly Digest */}
        <div className="rounded-xl border-l-4 border-primary bg-dark-800 p-4">
          <h3 className="font-semibold">📰 Weekly Digest</h3>
          {digests.length > 0 ? (
            <p className="my-2 text-gray-300">{digests[0].ai_summary_text}</p>
          ) : (
            <p className="my-2 text-gray-400">No digest yet.</p>
          )}
          <button
            onClick={handleGenerateDigest}
            disabled={generatingDigest}
            className="rounded bg-primary px-4 py-2 text-black disabled:opacity-50"
          >
            {generatingDigest ? 'Generating...' : '✨ Generate Digest'}
          </button>
        </div>

        {/* Race Day Calculator */}
        {calculator && (
          <div className="rounded-xl bg-dark-800 p-4">
            <h3 className="font-semibold">🏁 Race Day Calculator</h3>
            <p className="mt-1 text-sm text-gray-400">
              Based on your last {calculator.activity_counts?.run || 0} runs,{' '}
              {calculator.activity_counts?.bike || 0} rides,{' '}
              {calculator.activity_counts?.swim || 0} swims
            </p>
            <p className="mt-4 text-4xl font-bold text-primary">
              {calculator.predicted_total || 'Set a race goal to calculate'}
            </p>
            <details className="mt-4">
              <summary className="cursor-pointer text-gray-300">🍌 Nutrition plan</summary>
              <p className="mt-2 text-gray-300">90g carbs/hr on bike, 60g/hr on run, 600-800ml fluids/hr.</p>
            </details>
          </div>
        )}
      </div>
    </Layout>
  )
}
