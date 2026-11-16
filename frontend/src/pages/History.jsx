import { useEffect, useState } from 'react'
import {
  getRecognitionHistory,
  getRecognitionHistorySummary,
} from '../services/api'

const PAGE_SIZE = 20

function formatDate(value) {
  if (value == null || value === '') return '—'

  // Support ISO date strings and Unix timestamps (seconds or milliseconds).
  let dateValue = value
  if (typeof value === 'number' || (typeof value === 'string' && /^\d{10,13}$/.test(value))) {
    const timestamp = Number(value)
    dateValue = timestamp < 1_000_000_000_000 ? timestamp * 1000 : timestamp
  }

  const date = new Date(dateValue)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

function formatSimilarity(value) {
  if (value == null || value === '') return '—'

  const score = Number(value)
  if (!Number.isFinite(score)) return '—'

  // The API stores similarity as a 0–1 score.
  return `${(score * 100).toFixed(1)}%`
}

function Stat({ label, value }) {
  const count = Number(value)

  return (
    <div className="history-stat">
      <span>{label}</span>
      <strong>{Number.isFinite(count) ? count.toLocaleString() : '0'}</strong>
    </div>
  )
}

export default function History() {
  const [events, setEvents] = useState([])
  const [summary, setSummary] = useState(null)

  // Keep form input separate from applied filters so the API is called only
  // when the user presses Apply.
  const [searchInput, setSearchInput] = useState('')
  const [startDateInput, setStartDateInput] = useState('')
  const [endDateInput, setEndDateInput] = useState('')
  const [filters, setFilters] = useState({
    search: '',
    startDate: '',
    endDate: '',
  })

  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [error, setError] = useState('')
  const [summaryError, setSummaryError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      setLoading(true)
      setError('')

      try {
        const response = await getRecognitionHistory({
          startDate: filters.startDate || undefined,
          endDate: filters.endDate || undefined,
          search: filters.search || undefined,
          limit: PAGE_SIZE,
          offset,
        })

        if (cancelled) return

        const receivedEvents = Array.isArray(response?.events)
          ? response.events
          : []
        const receivedTotal = Number(
          response?.pagination?.total ?? response?.total ?? receivedEvents.length,
        )

        setEvents(receivedEvents)
        setTotal(
          Number.isFinite(receivedTotal) && receivedTotal >= 0
            ? receivedTotal
            : receivedEvents.length,
        )
      } catch (err) {
        if (cancelled) return
        console.error('Recognition history error:', err)
        setError(err?.message || 'Unable to load recognition history.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadHistory()

    return () => {
      // Prevent an older request from overwriting newer filter/page results.
      cancelled = true
    }
  }, [filters, offset, refreshKey])

  useEffect(() => {
    let cancelled = false

    async function loadSummary() {
      setSummaryLoading(true)
      setSummaryError('')

      try {
        const response = await getRecognitionHistorySummary()
        if (!cancelled) setSummary(response || null)
      } catch (err) {
        if (cancelled) return
        console.error('Recognition history summary error:', err)
        setSummaryError(err?.message || 'Unable to load history summary.')
      } finally {
        if (!cancelled) setSummaryLoading(false)
      }
    }

    loadSummary()

    return () => {
      cancelled = true
    }
  }, [refreshKey])

  function applyFilters(event) {
    event.preventDefault()

    if (startDateInput && endDateInput && startDateInput > endDateInput) {
      setError('The From date cannot be later than the To date.')
      return
    }

    setError('')
    setOffset(0)
    setFilters({
      search: searchInput.trim(),
      startDate: startDateInput,
      endDate: endDateInput,
    })
  }

  function clearFilters() {
    setSearchInput('')
    setStartDateInput('')
    setEndDateInput('')
    setFilters({ search: '', startDate: '', endDate: '' })
    setOffset(0)
    setError('')
  }

  function refreshHistory() {
    setRefreshKey((current) => current + 1)
  }

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <main className="history-page">
      <style>{`
        .history-page {
          width: 100%;
          color: var(--text-primary, #172033);
        }

        .history-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 22px;
        }

        .history-header h1 {
          margin: 0;
          font-size: 26px;
        }

        .history-muted {
          margin-top: 6px;
          color: var(--text-secondary, #667085);
          font-size: 13px;
        }

        .history-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 14px;
          margin-bottom: 20px;
        }

        .history-stat {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 18px;
          background: var(--surface, white);
          border: 1px solid var(--border-color, #e2e6ec);
          border-radius: 12px;
        }

        .history-stat span {
          color: var(--text-secondary, #667085);
          font-size: 13px;
        }

        .history-stat strong {
          font-size: 26px;
        }

        .history-panel {
          padding: 18px;
          background: var(--surface, white);
          border: 1px solid var(--border-color, #e2e6ec);
          border-radius: 12px;
          margin-bottom: 18px;
        }

        .history-filters {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr auto auto;
          gap: 12px;
          align-items: end;
        }

        .history-field {
          display: flex;
          flex-direction: column;
          gap: 7px;
          font-size: 13px;
          color: var(--text-secondary, #667085);
        }

        .history-field input {
          width: 100%;
          min-width: 0;
          box-sizing: border-box;
          padding: 10px 11px;
          border: 1px solid var(--border-color, #dce1e8);
          border-radius: 8px;
          background: var(--surface, white);
          color: inherit;
        }

        .history-button {
          padding: 10px 16px;
          border: 0;
          border-radius: 8px;
          background: var(--accent-color, #3978d5);
          color: white;
          cursor: pointer;
        }

        .history-button:disabled {
          opacity: .55;
          cursor: not-allowed;
        }

        .history-button-secondary {
          padding: 10px 14px;
          border: 1px solid var(--border-color, #dce1e8);
          border-radius: 8px;
          background: var(--surface, white);
          color: inherit;
          cursor: pointer;
        }

        .history-table-wrap {
          overflow-x: auto;
        }

        .history-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
          text-align: left;
          white-space: nowrap;
        }

        .history-table th,
        .history-table td {
          padding: 13px 11px;
          border-bottom: 1px solid var(--border-color, #e2e6ec);
        }

        .history-table th {
          color: var(--text-secondary, #667085);
          font-weight: 600;
        }

        .history-empty {
          padding: 35px 12px;
          text-align: center;
          color: var(--text-secondary, #667085);
        }

        .history-error {
          padding: 12px;
          margin-bottom: 15px;
          border-radius: 8px;
          background: #fff1f1;
          color: #a12626;
        }

        .history-pagination {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          margin-top: 18px;
          font-size: 13px;
        }

        .history-pagination button {
          padding: 8px 13px;
          border: 1px solid var(--border-color, #dce1e8);
          border-radius: 8px;
          background: var(--surface, white);
          color: inherit;
          cursor: pointer;
        }

        .history-pagination button:disabled {
          opacity: .4;
          cursor: not-allowed;
        }

        @media (max-width: 900px) {
          .history-filters {
            grid-template-columns: 1fr 1fr;
          }
        }

        @media (max-width: 520px) {
          .history-stats {
            grid-template-columns: 1fr;
          }

          .history-filters {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <header className="history-header">
        <div>
          <h1>Recognition History</h1>
          <div className="history-muted">
            Search and review previously recorded recognition events.
          </div>
        </div>

        <button
          className="history-button"
          type="button"
          onClick={refreshHistory}
          disabled={loading || summaryLoading}
        >
          {loading || summaryLoading ? 'Loading...' : 'Refresh'}
        </button>
      </header>

      <section className="history-stats">
        <Stat label="Today" value={summary?.today} />
        <Stat label="Last 7 Days" value={summary?.last_seven_days} />
        <Stat label="All-Time Events" value={summary?.all_time} />
      </section>

      {summaryError && <div className="history-error">{summaryError}</div>}

      <section className="history-panel">
        <form className="history-filters" onSubmit={applyFilters}>
          <label className="history-field">
            Search student name or roll number
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Enter name or roll number"
            />
          </label>

          <label className="history-field">
            From
            <input
              type="date"
              value={startDateInput}
              onChange={(event) => setStartDateInput(event.target.value)}
            />
          </label>

          <label className="history-field">
            To
            <input
              type="date"
              value={endDateInput}
              onChange={(event) => setEndDateInput(event.target.value)}
            />
          </label>

          <button className="history-button" type="submit" disabled={loading}>
            Apply
          </button>

          <button
            className="history-button-secondary"
            type="button"
            onClick={clearFilters}
          >
            Clear
          </button>
        </form>
      </section>

      {error && <div className="history-error">{error}</div>}

      <section className="history-panel">
        <h2 style={{ marginTop: 0, fontSize: 17 }}>Recognition Records</h2>

        <div className="history-muted">
          {total.toLocaleString()} matching event(s)
        </div>

        {loading ? (
          <div className="history-empty">Loading recognition records...</div>
        ) : events.length === 0 ? (
          <div className="history-empty">
            No recognition events match your filters.
          </div>
        ) : (
          <div className="history-table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Roll Number</th>
                  <th>Branch</th>
                  <th>Year</th>
                  <th>Similarity</th>
                  <th>First Seen</th>
                  <th>Last Seen</th>
                </tr>
              </thead>

              <tbody>
                {events.map((event, index) => (
                  <tr key={event.event_id ?? `${event.roll_no ?? 'event'}-${event.first_seen ?? index}`}>
                    <td>{event.student_name || '—'}</td>
                    <td>{event.roll_no || '—'}</td>
                    <td>{event.branch || '—'}</td>
                    <td>{event.year_of_study ?? '—'}</td>
                    <td>{formatSimilarity(event.similarity_score)}</td>
                    <td>{formatDate(event.first_seen)}</td>
                    <td>{formatDate(event.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="history-pagination">
          <button
            type="button"
            disabled={offset === 0 || loading}
            onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
          >
            Previous
          </button>

          <span>
            Page {currentPage} of {totalPages}
          </span>

          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset((current) => current + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      </section>
    </main>
  )
}
