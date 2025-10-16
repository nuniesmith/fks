import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { useUser } from '../../../context/UserContext'

const DEMO_HINT = [
  { email: 'jordan', password: '567326' },
  { email: 'testuser@example.com', password: 'test123' }
]

const SimpleLoginForm: React.FC = () => {
  const { login, isAuthenticated, user } = useUser()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  // Determine return target from query param
  const [returnTo, setReturnTo] = useState<string | null>(null)
  useEffect(() => {
    try {
      const p = new URLSearchParams(window.location.search).get('return')
      if (p) setReturnTo(p)
    } catch {}
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      const target = returnTo && /^\//.test(returnTo) ? returnTo : '/'
      // If we are on auth subdomain and target is relative, bounce to main domain root (strip auth.)
      try {
        const host = window.location.host
        if (host.startsWith('auth.') && target === '/') {
          const without = host.replace(/^auth\./, '')
          window.location.replace(`${window.location.protocol}//${without}${window.location.port ? ':' + window.location.port : ''}${target}`)
          return
        }
      } catch {}
      navigate(target, { replace: true })
    }
  }, [isAuthenticated, navigate, returnTo])
  if (isAuthenticated) return null

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
  const ok = await login(email.trim(), password)
      if (!ok) {
        setError('Invalid credentials')
      } else {
        navigate('/')
      }
    } catch (err: any) {
      setError(err?.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-md bg-gray-800 border border-gray-700 rounded-xl p-8 shadow-xl space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold text-white">Sign In</h1>
          <p className="text-sm text-gray-400">Local demo authentication (no external provider)</p>
        </div>
        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm px-3 py-2 rounded">
            {error}
          </div>
        )}
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-gray-300">Email or Username</span>
            <input
              type="text"
              required
              autoComplete="username"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="mt-1 w-full rounded bg-gray-700 border border-gray-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 px-3 py-2 text-white placeholder-gray-400"
              placeholder="you@example.com"
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-300">Password</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="mt-1 w-full rounded bg-gray-700 border border-gray-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 px-3 py-2 text-white placeholder-gray-400"
              placeholder="••••••••"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-medium transition"
        >
          {loading && <span className="animate-spin h-4 w-4 border-2 border-white/40 border-t-white rounded-full" />}
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
  <div className="pt-2 text-xs text-gray-500">
          <details>
            <summary className="cursor-pointer text-gray-400 hover:text-gray-300">Demo accounts</summary>
            <ul className="mt-2 space-y-1">
              {DEMO_HINT.map(c => (
                <li key={c.email} className="flex items-center justify-between">
                  <button type="button" onClick={() => { setEmail(c.email); setPassword(c.password) }} className="text-blue-400 hover:text-blue-300 text-left text-xs underline">
                    {c.email}
                  </button>
                  <code className="text-xs text-gray-400">{c.password}</code>
                </li>
              ))}
            </ul>
          </details>
        </div>
      </form>
    </div>
  )
}

export default SimpleLoginForm
