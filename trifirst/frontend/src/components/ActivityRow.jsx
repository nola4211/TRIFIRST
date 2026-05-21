const typeStyles = {
  swim: 'text-sky-400',
  bike: 'text-orange-400',
  run: 'text-green-400',
}

const typeEmoji = { swim: '🏊', bike: '🚴', run: '🏃' }

export default function ActivityRow({ activity }) {
  const type = activity.activity_type?.toLowerCase() || 'run'
  const distance = activity.distance_km ? `${activity.distance_km.toFixed(2)} km` : '-'
  const duration = activity.duration_mins ? `${Math.round(activity.duration_mins)} min` : '-'
  return (
    <tr className="border-b border-dark-700 hover:bg-dark-700">
      <td className="p-3 text-gray-300">{activity.date}</td>
      <td className={`p-3 font-medium ${typeStyles[type] || ''}`}>{typeEmoji[type]} {activity.activity_type}</td>
      <td className="p-3">{distance}</td>
      <td className="p-3">{duration}</td>
      <td className="p-3">{activity.avg_hr || '-'}</td>
    </tr>
  )
}
