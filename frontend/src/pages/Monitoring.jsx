
import { useCallback, useEffect, useState } from 'react'
import { getSystemMonitoring } from '../services/api'

function StatusBadge({ status }) {
  const labels = {
    online: 'Online',
    warning: 'Warning',
    error: 'Error',
    unknown: 'Unknown',
  }

  return (
    <span className={`monitoring-badge monitoring-${status || 'unknown'}`}>
      {labels[status] || 'Unknown'}
    </span>
  )
}

function formatUptime(seconds) {
  const value = Number(seconds || 0)
  const days = Math.floor(value / 86400)
  const hours = Math.floor((value % 86400) / 3600)
  const minutes = Math.floor((value % 3600) / 60)

  return `${days}d ${hours}h ${minutes}m`
}

export default function Monitoring() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadMonitoring = useCallback(async () => {
    try {
      const response = await getSystemMonitoring()

      setData(response)
      setError('')
    } catch (err) {
      console.error('System monitoring error:', err)
      setError(err.message || 'Unable to retrieve monitoring data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMonitoring()

    const interval = window.setInterval(loadMonitoring, 15000)

    return () => window.clearInterval(interval)
  }, [loadMonitoring])

  const runtime = data?.runtime || {}
  const resources = data?.resources || {}

  return (
    <main className="monitoring-page">
      <style>{`
        .monitoring-page {
          width: 100%;
          color: var(--text-primary, #172033);
        }

        .monitoring-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 14px;
          margin-bottom: 22px;
        }

        .monitoring-header h1 {
          margin: 0;
          font-size: 26px;
        }

        .monitoring-muted {
          margin-top: 6px;
          color: var(--text-secondary, #667085);
          font-size: 13px;
        }

        .monitoring-button {
          padding: 10px 15px;
          border: 1px solid var(--border-color, #dce1e8);
          border-radius: 8px;
          background: var(--surface, white);
          color: inherit;
          cursor: pointer;
        }

        .monitoring-overview {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 15px;
          padding: 20px;
          margin-bottom: 20px;
          border: 1px solid var(--border-color, #e2e6ec);
          border-radius: 13px;
          background: var(--surface, white);
        }

        .monitoring-overview strong {
          font-size: 18px;
        }

        .monitoring-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
          margin-bottom: 20px;
        }

        .monitoring-card {
          padding: 18px;
          border: 1px solid var(--border-color, #e2e6ec);
          border-radius: 12px;
          background: var(--surface, white);
          min-width: 0;
        }

        .monitoring-card h2 {
          margin: 0 0 14px;
          font-size: 16px;
        }

        .monitoring-check {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 14px;
          padding: 13px 0;
          border-bottom: 1px solid var(--border-color, #e2e6ec);
        }

        .monitoring-check:last-child {
          border-bottom: 0;
        }

        .monitoring-check-name {
          font-size: 14px;
          font-weight: 600;
        }

        .monitoring-check-details {
          margin-top: 5px;
          font-size: 12px;
          color: var(--text-secondary, #667085);
          overflow-wrap: anywhere;
        }

        .monitoring-badge {
          display: inline-flex;
          align-items: center;
          padding: 5px 9px;
          border-radius: 20px;
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
        }

        .monitoring-online {
          color: #137547;
          background: #e5f7ed;
        }

        .monitoring-warning {
          color: #946200;
          background: #fff4d6;
        }

        .monitoring-error {
          color: #a12626;
          background: #ffebeb;
        }

        .monitoring-unknown {
          color: #667085;
          background: #eef0f3;
        }

        .monitoring-runtime-row {
          display: flex;
          justify-content: space-between;
          gap: 14px;
          padding: 11px 0;
          border-bottom: 1px solid var(--border-color, #e2e6ec);
          font-size: 13px;
        }

        .monitoring-runtime-row:last-child {
          border-bottom: 0;
        }

        .monitoring-runtime-row span:first-child {
          color: var(--text-secondary, #667085);
        }

        .monitoring-runtime-row span:last-child {
          font-weight: 600;
          text-align: right;
          overflow-wrap: anywhere;
        }

        .monitoring-error-message {
          padding: 12px;
          margin-bottom: 15px;
          color: #a12626;
          background: #fff1f1;
          border-radius: 8px;
        }

        .monitoring-note {
          padding: 13px 15px;
          border-radius: 9px;
          background: var(--surface, white);
          border: 1px solid var(--border-color, #e2e6ec);
          color: var(--text-secondary, #667085);
          font-size: 12px;
          line-height: 1.6;
        }

        @media (max-width: 700px) {
          .monitoring-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <header className="monitoring-header">
        <div>
          <h1>System Monitoring</h1>
          <div className="monitoring-muted">
            Backend, database, AI assets and recognition runtime checks
          </div>
        </div>

        <button
          className="monitoring-button"
          onClick={loadMonitoring}
          disabled={loading}
        >
          {loading ? 'Checking...' : 'Run checks'}
        </button>
      </header>

      {error && (
        <div className="monitoring-error-message">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="monitoring-card">Checking system components...</div>
      ) : data ? (
        <>
          <section className="monitoring-overview">
            <div>
              <strong>Overall System Status</strong>
              <div className="monitoring-muted">
                Last checked: {new Date(
                  data.checked_at * 1000
                ).toLocaleString()}
              </div>
            </div>

            <StatusBadge status={data.overall_status} />
          </section>

          <section className="monitoring-grid">
            <div className="monitoring-card">
              <h2>Component Health</h2>

              {(data.checks || []).map((check) => (
                <div className="monitoring-check" key={check.name}>
                  <div>
                    <div className="monitoring-check-name">
                      {check.name}
                    </div>
                    <div className="monitoring-check-details">
                      {check.details || check.location || 'Status checked'}
                    </div>
                  </div>

                  <StatusBadge status={check.status} />
                </div>
              ))}
            </div>

            <div className="monitoring-card">
              <h2>Runtime Information</h2>

              <div className="monitoring-runtime-row">
                <span>Operating System</span>
                <span>{runtime.operating_system || '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Python</span>
                <span>{runtime.python_version || '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Inference Device</span>
                <span>{runtime.device || '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Backend Uptime</span>
                <span>{formatUptime(runtime.uptime_seconds)}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>YOLO Confidence</span>
                <span>{runtime.yolo_confidence ?? '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Image Size</span>
                <span>{runtime.yolo_image_size ?? '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Minimum Similarity</span>
                <span>{runtime.minimum_similarity ?? '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Minimum Margin</span>
                <span>{runtime.minimum_margin ?? '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Vote Requirement</span>
                <span>
                  {runtime.required_votes ?? '—'} / {runtime.vote_window ?? '—'}
                </span>
              </div>
            </div>

            <div className="monitoring-card">
              <h2>Resource Usage</h2>

              <div className="monitoring-runtime-row">
                <span>CPU Usage</span>
                <span>
                  {resources.cpu_percent == null
                    ? 'Unavailable'
                    : `${resources.cpu_percent}%`}
                </span>
              </div>

              <div className="monitoring-runtime-row">
                <span>System Memory</span>
                <span>
                  {resources.memory_percent == null
                    ? 'Unavailable'
                    : `${resources.memory_percent}%`}
                </span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Backend Process Memory</span>
                <span>
                  {resources.memory_used_mb == null
                    ? 'Unavailable'
                    : `${resources.memory_used_mb} MB`}
                </span>
              </div>
            </div>

            <div className="monitoring-card">
              <h2>Recognition Configuration</h2>

              <div className="monitoring-runtime-row">
                <span>Face Check Interval</span>
                <span>{runtime.face_check_interval ?? '—'} sec</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Track Lost Timeout</span>
                <span>{runtime.lost_timeout ?? '—'} sec</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Vote Window</span>
                <span>{runtime.vote_window ?? '—'}</span>
              </div>

              <div className="monitoring-runtime-row">
                <span>Required Votes</span>
                <span>{runtime.required_votes ?? '—'}</span>
              </div>
            </div>
          </section>

          <div className="monitoring-note">
            Checks refresh automatically every 15 seconds. Model checks verify
            asset availability on disk; they do not independently prove that
            the AI models are loaded and inference is working. CPU and memory
            statistics require the optional psutil package.
          </div>
        </>
      ) : null}
    </main>
  )
}
