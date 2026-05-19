export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`max-w-[80%] rounded-xl p-3 ${isUser ? 'ml-auto bg-dark-700' : 'bg-dark-800 border-l-4 border-primary'}`}>
      <p className="text-sm text-gray-100">{message.text}</p>
    </div>
  )
}
