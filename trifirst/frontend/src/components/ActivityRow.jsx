const typeStyles = {
  swim: 'text-swim',
  bike: 'text-bike',
  run: 'text-run',
}

const typeEmoji = { swim: '🏊', bike: '🚴', run: '🏃' }

export default function ActivityRow({ activity }) {
  const type = activity.type?.toLowerCase() || 'run'
  return (
    <tr className="border-b border-dark-700">
      <td className="p-3">{activity.date}</td>
      <td className={`p-3 ${typeStyles[type] || ''}`}>{typeEmoji[type]} {activity.type}</td>
      <td className="p-3">{activity.distance} km</td>
      <td className="p-3">{activity.duration}</td>
      <td className="p-3">{activity.avgHr || '-'}</td>
    </tr>
  )
}
