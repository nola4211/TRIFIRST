export default function WorkoutCard({ workout, checked, onToggle }) {
  const tone = { swim: 'bg-swim', bike: 'bg-bike', run: 'bg-run', rest: 'bg-gray-500' }
  return (
    <label className="flex items-center gap-3 rounded-lg bg-dark-800 p-3">
      <input type="checkbox" checked={checked} onChange={() => onToggle(workout.id)} />
      <span className={`rounded-full px-2 py-1 text-xs font-semibold text-black ${tone[workout.type] || 'bg-gray-400'}`}>
        {workout.type}
      </span>
      <span>{workout.title}</span>
    </label>
  )
}
