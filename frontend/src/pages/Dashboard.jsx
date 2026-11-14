
import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  Camera,
  Clock3,
  RefreshCw,
  Server,
  Users,
} from 'lucide-react'
import { getBackendHealth } from '../services/api'

const metrics = [
  {
    title: 'Registered Students',
    description: 'Awaiting student API',
    icon: Users,
  },
  {
    title: "Today's Recognitions",
    description: 'Awaiting event API',
    icon: Activity,
  },
  {
    title: 'Active Cameras',
    description: 'Awaiting camera API',
    icon: Camera,
  },
  {
    title: 'Recognition Events',
    description: 'Awaiting event API',
    icon: Clock3,
  },
]

export default function Dashboard() {
  const [connection, setConnection] = useState('checking')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  const checkBackend = useCallback(async () => {
    setConnection('checking')
    setError('')

    try {
      const result = await getBackendHealth()

      setHealth(result)
      setConnection('online')
    } catch (err) {
      setHealth(null)
      setConnection('offline')
      setError(err.message || 'Unable to reach backend')
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    const runHealthCheck = async () => {
      try {
        const result = await getBackendHealth()

        if (isMounted) {
          setHealth(result)
          setConnection('online')
          setError('')
        }
      } catch (err) {
        if (isMounted) {
          setHealth(null)
          setConnection('offline')
          setError(err.message || 'Unable to reach backend')
        }
      }
    }

    // Schedule initial backend health check asynchronously.
    const initialCheckId = window.setTimeout(() => {
      runHealthCheck()
    }, 0)

    // Automatically check backend every 15 seconds.
    const intervalId = window.setInterval(() => {
      runHealthCheck()
    }, 15000)

    return () => {
      isMounted = false
      window.clearTimeout(initialCheckId)
      window.clearInterval(intervalId)
    }
  }, [])

  const statusColor =
    connection === 'online'
      ? 'bg-emerald-400'
      : connection === 'offline'
        ? 'bg-red-400'
        : 'bg-amber-400'

  return (
    <div className="space-y-8">
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm text-blue-400">Overview</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">
            Dashboard
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Monitor student recognition and application activity.
          </p>
        </div>

        <button
          onClick={checkBackend}
          disabled={connection === 'checking'}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw
            size={16}
            className={connection === 'checking' ? 'animate-spin' : ''}
          />
          Refresh status
        </button>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ title, description, icon: Icon }) => (
          <article
            key={title}
            className="rounded-xl border border-slate-800 bg-slate-900 p-5"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-400">{title}</p>
              <div className="rounded-lg bg-blue-500/10 p-2 text-blue-400">
                <Icon size={19} />
              </div>
            </div>

            <p className="mt-5 text-3xl font-bold text-white">—</p>
            <p className="mt-2 text-xs text-slate-500">{description}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-3">
        <article className="rounded-xl border border-slate-800 bg-slate-900 p-6 xl:col-span-2">
          <div className="flex items-center gap-2">
            <Activity size={19} className="text-blue-400" />
            <h3 className="font-semibold text-white">
              Recognition Activity
            </h3>
          </div>

          <div className="flex min-h-64 flex-col items-center justify-center text-center">
            <Activity size={35} className="text-slate-600" />
            <p className="mt-4 font-medium text-slate-300">
              Waiting for recognition data
            </p>
            <p className="mt-2 max-w-sm text-sm text-slate-500">
              Recognition charts will display real database events after API integration.
            </p>
          </div>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <div className="flex items-center gap-2">
            <Server size={19} className="text-blue-400" />
            <h3 className="font-semibold text-white">System Status</h3>
          </div>

          <div className="mt-6 space-y-5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-slate-400">
                FastAPI backend
              </span>
              <span className="flex items-center gap-2 text-sm">
                <span className={`h-2 w-2 rounded-full ${statusColor}`} />
                {connection === 'online'
                  ? 'Online'
                  : connection === 'offline'
                    ? 'Offline'
                    : 'Checking'}
              </span>
            </div>

            <div className="border-t border-slate-800 pt-4">
              <p className="text-xs uppercase tracking-wider text-slate-500">
                Application
              </p>
              <p className="mt-2 text-sm text-slate-200">
                {health?.application ?? 'Not connected'}
              </p>
            </div>

            <div className="border-t border-slate-800 pt-4">
              <p className="text-xs uppercase tracking-wider text-slate-500">
                Inference device
              </p>
              <p className="mt-2 text-sm uppercase text-slate-200">
                {health?.device ?? 'Unknown'}
              </p>
            </div>

            <div className="border-t border-slate-800 pt-4">
              <p className="text-xs uppercase tracking-wider text-slate-500">
                API status
              </p>
              <p className="mt-2 text-sm text-slate-200">
                {health?.status ?? 'Unavailable'}
              </p>
            </div>

            {error && (
              <p className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
                {error}
              </p>
            )}
          </div>
        </article>
      </section>
    </div>
  )
}
