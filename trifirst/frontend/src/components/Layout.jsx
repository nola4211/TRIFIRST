import Sidebar from './Sidebar'

export default function Layout({ children }) {
  return (
    <div className="flex">
      <Sidebar />
      <main className="h-screen flex-1 overflow-y-auto bg-dark-900 p-6">{children}</main>
    </div>
  )
}
