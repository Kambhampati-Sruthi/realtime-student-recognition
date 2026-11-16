import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getDashboardSummary,
  getBackendHealth,
} from '../services/api'

const REFRESH_INTERVAL = 10000

const EMPTY_METRICS = {
  total_students: 0,
  active_students: 0,
  enrolled_students: 0,
  today_recognitions: 0,
  active_cameras: 0,
  total_events: 0,
  configured_cameras: 0,
}

function extractPayload(response) {
  if (
    response?.data &&
    typeof response.data === 'object' &&
    !Array.isArray(response.data)
  ) {
    return response.data
  }

  return response
}

function formatNumber(value) {
  const number = Number(value)

  return Number.isFinite(number)
    ? number.toLocaleString()
    : '0'
}

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  return date.toLocaleString()
}

function MetricCard({ title, value, subtitle, icon }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </p>

          <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
            {formatNumber(value)}
          </p>

          {subtitle && (
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {subtitle}
            </p>
          )}
        </div>

        <span className="text-2xl" aria-hidden="true">
          {icon}
        </span>
      </div>
    </div>
  )
}

function Dashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [backendStatus, setBackendStatus] = useState('checking')
  const [lastUpdated, setLastUpdated] = useState(null)

  const mountedRef = useRef(false)
  const requestInProgress = useRef(false)
  const dashboardRef = useRef(null)

  const loadDashboard = useCallback(async (showLoader = false) => {
    if (requestInProgress.current) return

    requestInProgress.current = true

    if (showLoader && !dashboardRef.current) {
      setLoading(true)
    } else {
      setRefreshing(true)
    }

    try {
      const response = await getDashboardSummary()
      const payload = extractPayload(response)

      if (!payload || typeof payload !== 'object') {
        throw new Error('Invalid dashboard response from backend.')
      }

      if (payload.success === false) {
        throw new Error(
          payload.message || 'Unable to load dashboard information.'
        )
      }

      if (mountedRef.current) {
        dashboardRef.current = payload
        setDashboard(payload)
        setError('')
        setLastUpdated(new Date().toISOString())
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(
          err?.message || 'Unable to refresh dashboard information.'
        )
      }
    } finally {
      requestInProgress.current = false

      if (mountedRef.current) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  const checkBackend = useCallback(async () => {
    try {
      await getBackendHealth()

      if (mountedRef.current) {
        setBackendStatus('connected')
      }
    } catch {
      if (mountedRef.current) {
        setBackendStatus('disconnected')
      }
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true

    loadDashboard(true)
    checkBackend()

    const refreshTimer = window.setInterval(() => {
      loadDashboard(false)
    }, REFRESH_INTERVAL)

    const healthTimer = window.setInterval(() => {
      checkBackend()
    }, 30000)

    const handleVisibilityOrFocus = () => {
      if (document.visibilityState === 'visible') {
        loadDashboard(false)
        checkBackend()
      }
    }

    window.addEventListener('focus', handleVisibilityOrFocus)
    document.addEventListener('visibilitychange', handleVisibilityOrFocus)

    return () => {
      mountedRef.current = false
      window.clearInterval(refreshTimer)
      window.clearInterval(healthTimer)
      window.removeEventListener('focus', handleVisibilityOrFocus)
      document.removeEventListener('visibilitychange', handleVisibilityOrFocus)
    }
  }, [loadDashboard, checkBackend])

  const rawMetrics = dashboard?.metrics || {}
  const metrics = {
    ...EMPTY_METRICS,
    ...rawMetrics,
    enrolled_students:
      rawMetrics.enrolled_students ?? rawMetrics.active_students ?? 0,
  }

  const activity = Array.isArray(dashboard?.activity)
    ? dashboard.activity
    : []

  const recentEvents = Array.isArray(dashboard?.recent_events)
    ? dashboard.recent_events
    : []

  const systemStatus =
    backendStatus === 'connected'
      ? 'Backend connected'
      : backendStatus === 'disconnected'
        ? 'Backend unavailable'
        : 'Checking backend'

  if (loading && !dashboard) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
          <p className="mt-4 text-sm text-gray-500">
            Loading dashboard...
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Dashboard
          </h1>

          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Real-time student recognition overview
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              backendStatus === 'connected'
                ? 'bg-green-100 text-green-700'
                : backendStatus === 'disconnected'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-gray-100 text-gray-600'
            }`}
          >
            {systemStatus}
          </span>

          <button
            type="button"
            onClick={() => {
              loadDashboard(false)
              checkBackend()
            }}
            disabled={refreshing}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          <p className="font-semibold">Dashboard refresh failed</p>
          <p className="mt-1">{error}</p>
          {dashboard && (
            <p className="mt-1 text-xs">
              Showing the last successfully loaded dashboard data.
            </p>
          )}
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Total Students"
          value={metrics.total_students}
          subtitle="Registered student records"
          icon="👨‍🎓"
        />

        <MetricCard
          title="Active Students"
          value={metrics.active_students}
          subtitle="Currently active records"
          icon="🟢"
        />

        <MetricCard
          title="Enrolled Students"
          value={metrics.enrolled_students}
          subtitle="Students with face enrollment"
          icon="🪪"
        />

        <MetricCard
          title="Today's Recognitions"
          value={metrics.today_recognitions}
          subtitle="Recognition events today"
          icon="📊"
        />

        <MetricCard
          title="Active Cameras"
          value={metrics.active_cameras}
          subtitle="Currently active camera sessions"
          icon="📷"
        />

        <MetricCard
          title="Total Events"
          value={metrics.total_events}
          subtitle="Stored recognition events"
          icon="📝"
        />

        <MetricCard
          title="Configured Cameras"
          value={metrics.configured_cameras}
          subtitle="Configured camera records"
          icon="🎥"
        />
      </div>

      {/* Activity */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Recognition Activity
          </h2>

          <span className="text-xs text-gray-500">
            Recent activity
          </span>
        </div>

        {activity.length > 0 ? (
          <div className="space-y-3">
            {activity.map((item, index) => {
              const count = Number(item.count) || 0
              const maxCount = Math.max(
                1,
                ...activity.map((entry) => Number(entry.count) || 0)
              )

              const width = `${(count / maxCount) * 100}%`

              return (
                <div key={item.date || index}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">
                      {item.date || `Day ${index + 1}`}
                    </span>

                    <span className="font-medium text-gray-900 dark:text-white">
                      {formatNumber(count)}
                    </span>
                  </div>

                  <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{ width }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-gray-500">
            No recognition activity available yet.
          </p>
        )}
      </div>

      {/* Recent Events */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center justify-between border-b border-gray-200 p-5 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Recent Recognition Events
          </h2>

          <span className="text-xs text-gray-500">
            Latest records
          </span>
        </div>

        {recentEvents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[650px] text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500 dark:bg-gray-900 dark:text-gray-400">
                <tr>
                  <th className="px-5 py-3">Student</th>
                  <th className="px-5 py-3">Roll Number</th>
                  <th className="px-5 py-3">Branch</th>
                  <th className="px-5 py-3">Similarity</th>
                  <th className="px-5 py-3">Last Seen</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {recentEvents.map((event, index) => (
                  <tr
                    key={event.event_id || event.id || index}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/40"
                  >
                    <td className="px-5 py-3 font-medium text-gray-900 dark:text-white">
                      {event.student_name || 'Unknown'}
                    </td>

                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300">
                      {event.roll_no || '—'}
                    </td>

                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300">
                      {event.branch || '—'}
                    </td>

                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300">
                      {event.similarity_score != null
                        ? `${(Number(event.similarity_score) * 100).toFixed(1)}%`
                        : '—'}
                    </td>

                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300">
                      {formatDate(event.last_seen || event.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="py-10 text-center text-sm text-gray-500">
            No recognition events have been recorded yet.
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="flex flex-col justify-between gap-2 text-xs text-gray-500 sm:flex-row">
        <span>
          {lastUpdated
            ? `Last dashboard update: ${formatDate(lastUpdated)}`
            : 'Dashboard has not loaded successfully yet.'}
        </span>

        <span>
          {refreshing
            ? 'Refreshing dashboard...'
            : 'Automatic refresh every 10 seconds'}
        </span>
      </div>
    </div>
  )
}

export default Dashboard