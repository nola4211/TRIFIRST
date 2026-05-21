import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api/auth'

export default function Login() {
  const [tab, setTab] = useState('login')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', name: '', email: '', confirmPassword: '', age: '' })
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const res = tab === 'login' 
        ? await login({ username: form.username, password: form.password }) 
        : await register({ 
            name: form.name, 
            email: form.email, 
            username: form.username, 
            password: form.password,
            age: form.age ? parseInt(form.age) : null
          })
      localStorage.setItem('trifirst_user', JSON.stringify(res.data.user || res.data))
      navigate('/dashboard')
    } catch (err) { 
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map(d => d.msg).join(', '))
      } else {
        setError(typeof detail === 'string' ? detail : 'Request failed')
      }
    }
    finally { setLoading(false) }
  }

  return <div className="min-h-screen bg-dark-900 flex items-center justify-center p-4"><div className="w-full max-w-lg rounded-2xl bg-dark-800 p-8">
    <div className="text-center"><div className="text-5xl">🏊🚴🏃</div><h1 className="text-4xl font-bold">TriFirst</h1><p className="text-primary">Your Ironman Training Companion</p></div>
    <div className="mt-6 flex gap-2"><button className={`flex-1 rounded p-2 ${tab==='login'?'bg-primary text-black':'bg-dark-700'}`} onClick={()=>setTab('login')}>Login</button><button className={`flex-1 rounded p-2 ${tab==='register'?'bg-primary text-black':'bg-dark-700'}`} onClick={()=>setTab('register')}>Create Account</button></div>
    <form onSubmit={submit} className="mt-4 space-y-3">
      {tab==='register' && <><input className="w-full rounded bg-dark-700 p-2" placeholder="Name" onChange={e=>setForm({...form,name:e.target.value})}/><input className="w-full rounded bg-dark-700 p-2" placeholder="Email" onChange={e=>setForm({...form,email:e.target.value})}/></>}
      <input className="w-full rounded bg-dark-700 p-2 focus:outline-none focus:ring-2 focus:ring-primary" placeholder="Username" onChange={e=>setForm({...form,username:e.target.value})}/>
      <input type="password" className="w-full rounded bg-dark-700 p-2 focus:outline-none focus:ring-2 focus:ring-primary" placeholder="Password" onChange={e=>setForm({...form,password:e.target.value})}/>
      {tab==='register' && <><input type="password" className="w-full rounded bg-dark-700 p-2" placeholder="Confirm password" onChange={e=>setForm({...form,confirmPassword:e.target.value})}/><input className="w-full rounded bg-dark-700 p-2" placeholder="Age (optional)" onChange={e=>setForm({...form,age:e.target.value})}/></>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button disabled={loading} className="w-full rounded bg-primary p-2 font-semibold text-black">{loading?'Loading...': tab==='login' ? 'Login' : 'Create Account'}</button>
    </form></div></div>
}
