
import { useCallback, useEffect, useState } from 'react'
import { getDashboardSummary } from '../services/api'

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  return date.toLocaleString()
}

function MetricCard({ title, value, description }) {
  return (
    <div className="dashboard-metric-card">
      <div className="dashboard-metric-title">{title}</div>
      <div className="dashboard-metric-value">{formatNumber(value)}</div>
      <div className="dashboard-metric-description">{description}</div>
    </div>
  )
}

function ActivityChart({ activity = [] }) {
  const maximum = Math.max(
    1,
    ...activity.map((item) => Number(item.count || 0))
  )

  if (!activity.length) {
    return <div className="dashboard-empty">No activity data available.</div>
  }

  return (
    <div className="dashboard-chart">
      {activity.map((item) => {
        const count = Number(item.count || 0)
        const height = Math.max(5, (count / maximum) * 150)

        return (
          <div className="dashboard-chart-column" key={item.date}>
            <div className="dashboard-chart-count">{count}</div>

            <div className="dashboard-chart-bar-area">
              <div
                className="dashboard-chart-bar"
                style={{ height: `${height}px` }}
                title={`${item.date}: ${count} recognitions`}
              />
            </div>

            <div className="dashboard-chart-label">
              {new Date(`${item.date}T00:00:00`).toLocaleDateString(
                undefined,
                { weekday: 'short' }
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function RecentEvents({ events = [] }) {
  if (!events.length) {
    return (
      <div className="dashboard-empty">
        No recognition events have been recorded yet.
      </div>
    )
  }

  return (
    <div className="dashboard-table-wrapper">
      <table className="dashboard-table">
        <thead>
          <tr>
            <th>Student</th>
            <th>Roll Number</th>
            <th>Branch</th>
            <th>Similarity</th>
            <th>Last Seen</th>
          </tr>
        </thead>

        <tbody>
          {events.map((event) => (
            <tr key={event.event_id}>
              <td>{event.student_name}</td>
              <td>{event.roll_no || '—'}</td>
              <td>{event.branch || '—'}</td>
              <td>
                {event.similarity_score == null
                  ? '—'
                  : `${(Number(event.similarity_score) * 100).toFixed(1)}%`}
              </td>
              <td>{formatDate(event.last_seen || event.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async (showLoader = false) => {
    if (showLoader) {
      setLoading(true)
    } else {
      setRefreshing(true)
    }

    try {
      const response = await getDashboardSummary()

      if (!response?.success) {
        throw new Error('The dashboard API returned an invalid response.')
      }

      setDashboard(response)
      setError('')
    } catch (err) {
      console.error('Dashboard loading failed:', err)
      setError(err.message || 'Unable to load dashboard data.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard(true)

    const interval = window.setInterval(() => {
      loadDashboard(false)
    }, 30000)

    return () => window.clearInterval(interval)
  }, [loadDashboard])

  const metrics = dashboard?.metrics || {}

  return (
    <main className="dashboard-page">
      <style>{`
        .dashboard-page {
          width: 100%;
          color: var(--text-primary, #172033);
        }

        .dashboard-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 24px;
          flex-wrap: wrap;
        }

        .dashboard-heading {
          margin: 0;
          font-size: 26px;
          font-weight: 700;
        }

        .dashboard-subtitle {
          margin-top: 6px;
          color: var(--text-secondary, #667085);
          font-size: 14px;
        }

        .dashboard-refresh-button {
          padding: 10px 16px;
          border: 1px solid var(--border-color, #dce1e8);
          border-radius: 9px;
          background: var(--surface, #fff);
          color: inherit;
          cursor: pointer;
        }

        .dashboard-refresh-button:disabled {
          opacity: .6;
          cursor: wait;
        }

        .dashboard-metrics-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }

        .dashboard-metric-card {
          padding: 20px;
          border: 1px solid var(--border-color, #e2e6ec);
          border-radius: 13px;
          background: var(--surface, #fff);
          min-width: 0;
        }

        .dashboard-metric-title {
          font-size: 14px;
          color: var(--text-secondary, #667085);
        }

        .dashboard-metric-value {
          margin-top: 13px;
          font-size: 30px;
          font-weight: 750;
          overflow-wrap: anywhere;
        }

        .dashboard-metric-description {
          margin-top: 7px;
          font-size: 12px;
          color: var(--text-secondary, #667085);
        }

        .dashboard-content-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.4fr) minmax(260px, 1fr);
          gap: 18px;
          margin-bottom: 22px;
        }

        .dashboard-panel {
          min-width: 0;
          padding: 20px;
          border: 1px solid var(--border-color, #e2e6ec);
          border-radius: 13px;
          background: var(--surface, #fff);
        }

        .dashboard-panel h2 {
          margin: 0;
          font-size: 17px;
          font-weight: 650;
        }

        .dashboard-panel-subtitle {
          margin-top: 6px;
          color: var(--text-secondary, #667085);
          font-size: 12px;
        }

        .dashboard-chart {
          display: flex;
          align-items: flex-end;
          justify-content: space-around;
          gap: 10px;
          height: 220px;
          padding-top: 25px;
        }

        .dashboard-chart-column {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: flex-end;
          gap: 7px;
        }

        .dashboard-chart-count {
          font-size: 12px;
          color: var(--text-secondary, #667085);
        }

        .dashboard-chart-bar-area {
          height: 155px;
          width: 100%;
          display: flex;
          align-items: flex-end;
          justify-content: center;
        }

        .dashboard-chart-bar {
          width: min(34px, 75%);
          min-height: 5px;
          border-radius: 6px 6px 2px 2px;
          background: var(--accent-color, #3978d5);
          transition: height .25s ease;
        }

        .dashboard-chart-label {
          font-size: 11px;
          color: var(--text-secondary, #667085);
        }

        .dashboard-status-row {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          padding: 13px 0;
          border-bottom: 1px solid var(--border-color, #e2e6ec);
          font-size: 14px;
        }

        .dashboard-status-row:last-child {
          border-bottom: 0;
        }

        .dashboard-status-value {
          font-weight: 650;
          text-align: right;
        }

        .dashboard-table-wrapper {
          overflow-x: auto;
          margin-top: 15px;
        }

        .dashboard-table {
          width: 100%;
          border-collapse: collapse;
          text-align: left;
          font-size: 13px;
          white-space: nowrap;
        }

        .dashboard-table th,
        .dashboard-table td {
          padding: 13px 12px;
          border-bottom: 1px solid var(--border-color, #e2e6ec);
        }

        .dashboard-table th {
          color: var(--text-secondary, #667085);
          font-weight: 600;
        }

        .dashboard-empty {
          padding: 28px 10px;
          color: var(--text-secondary, #667085);
          text-align: center;
          font-size: 14px;
        }

        .dashboard-error {
          margin-bottom: 18px;
          padding: 13px 16px;
          border: 1px solid #e7b4b4;
          border-radius: 9px;
          color: #a12626;
          background: #fff4f4;
          font-size: 14px;
        }

        .dashboard-updated {
          margin-top: 12px;
          color: var(--text-secondary, #667085);
          font-size: 11px;
        }

        @media (max-width: 1000px) {
          .dashboard-metrics-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .dashboard-content-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 520px) {
          .dashboard-metrics-grid {
            grid-template-columns: 1fr;
          }

          .dashboard-metric-value {
            font-size: 26px;
          }

          .dashboard-panel {
            padding: 14px;
          }
        }
      `}</style>

      <header className="dashboard-header">
        <div>
          <h1 className="dashboard-heading">Dashboard</h1>
          <div className="dashboard-subtitle">
            Real-time person recognition system overview
          </div>
        </div>

        <button
          className="dashboard-refresh-button"
          onClick={() => loadDashboard(false)}
          disabled={refreshing || loading}
        >
          {refreshing ? 'Refreshing...' : 'Refresh data'}
        </button>
      </header>

      {error && (
        <div className="dashboard-error">
          {error}
        </div>
      )}

      {loading && !dashboard ? (
        <div className="dashboard-empty">
          Loading dashboard data from the database...
        </div>
      ) : (
        <>
          <section className="dashboard-metrics-grid">
            <MetricCard
              title="Registered Students"
              value={metrics.total_students}
              description={`${formatNumber(metrics.active_students)} active students`}
            />

            <MetricCard
              title="Today's Recognitions"
              value={metrics.today_recognitions}
              description="Recognition events recorded today"
            />

            <MetricCard
              title="Active Camera Sessions"
              value={metrics.active_cameras}
              description="Sessions currently marked active"
            />

            <MetricCard
              title="Total Recognition Events"
              value={metrics.total_events}
              description="Events stored in the database"
            />
          </section>

          <section className="dashboard-content-grid">
            <div className="dashboard-panel">
              <h2>Recognition Activity</h2>
              <div className="dashboard-panel-subtitle">
                Recognition events over the last seven days
              </div>

              <ActivityChart activity={dashboard?.activity || []} />
            </div>

            <div className="dashboard-panel">
              <h2>System Overview</h2>
              <div className="dashboard-panel-subtitle">
                Database-backed system information
              </div>

              <div style={{ marginTop: 18 }}>
                <div className="dashboard-status-row">
                  <span>Backend API</span>
                  <span className="dashboard-status-value">
                    Connected
                  </span>
                </div>

                <div className="dashboard-status-row">
                  <span>Registered Students</span>
                  <span className="dashboard-status-value">
                    {formatNumber(metrics.total_students)}
                  </span>
                </div>

                <div className="dashboard-status-row">
                  <span>Active Students</span>
                  <span className="dashboard-status-value">
                    {formatNumber(metrics.active_students)}
                  </span>
                </div>

                <div className="dashboard-status-row">
                  <span>Configured Cameras</span>
                  <span className="dashboard-status-value">
                    {formatNumber(metrics.configured_cameras)}
                  </span>
                </div>

                <div className="dashboard-status-row">
                  <span>Active Sessions</span>
                  <span className="dashboard-status-value">
                    {formatNumber(metrics.active_cameras)}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section className="dashboard-panel">
            <h2>Recent Recognition Events</h2>
            <div className="dashboard-panel-subtitle">
              Latest recognition records retrieved from Supabase
            </div>

            <RecentEvents events={dashboard?.recent_events || []} />

            <div className="dashboard-updated">
              Last updated: {formatDate(dashboard?.generated_at)}
              {' · '}Automatic refresh every 30 seconds
            </div>
          </section>
        </>
      )}
    </main>
  )
}
