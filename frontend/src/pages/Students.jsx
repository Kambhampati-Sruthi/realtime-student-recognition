
import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  UserRound,
  UserRoundPlus,
  Users,
  X,
} from 'lucide-react'

import {
  getStudents,
  registerStudent,
  updateStudentStatus,
} from '../services/api'

const initialForm = {
  name: '',
  roll_no: '',
  branch: '',
  role: 'student',
}

export default function Students() {
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(initialForm)
  const [submitting, setSubmitting] = useState(false)
  const [updatingId, setUpdatingId] = useState(null)

  async function loadStudents(showRefresh = false) {
    if (showRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    setError('')

    try {
      const data = await getStudents({ limit: 500 })
      setStudents(data)
    } catch (err) {
      setError(err.message || 'Unable to load student records.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    let mounted = true

    getStudents({ limit: 500 })
      .then((data) => {
        if (mounted) {
          setStudents(data)
          setError('')
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Unable to load student records.')
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false)
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  const filteredStudents = useMemo(() => {
    const query = search.trim().toLowerCase()

    if (!query) return students

    return students.filter((student) =>
      [
        student.name,
        student.roll_no,
        student.branch,
        student.role,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    )
  }, [students, search])

  const activeCount = students.filter(
    (student) => student.is_active
  ).length

  const inactiveCount = students.length - activeCount

  function handleInputChange(event) {
    const { name, value } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }))
  }

  async function handleRegister(event) {
    event.preventDefault()

    setSubmitting(true)
    setError('')
    setSuccess('')

    try {
      const newStudent = {
        name: form.name.trim(),
        roll_no: form.roll_no.trim(),
        branch: form.branch.trim() || null,
        role: form.role,
      }

      await registerStudent(newStudent)

      setForm(initialForm)
      setShowForm(false)
      setSuccess(
        `Student ${newStudent.name} was registered successfully.`
      )

      await loadStudents()
    } catch (err) {
      setError(err.message || 'Student registration failed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStatusChange(student) {
    const nextStatus = !student.is_active

    setUpdatingId(student.id)
    setError('')
    setSuccess('')

    try {
      const updatedStudent = await updateStudentStatus(
        student.id,
        nextStatus
      )

      setStudents((previous) =>
        previous.map((item) =>
          item.id === student.id ? updatedStudent : item
        )
      )

      setSuccess(
        `${student.name} has been ${
          nextStatus ? 'activated' : 'deactivated'
        }.`
      )
    } catch (err) {
      setError(err.message || 'Unable to update student status.')
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div className="space-y-7">
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm text-blue-400">Database management</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">
            Student Management
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Manage registered students and their application status.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => loadStudents(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCw
              size={16}
              className={refreshing ? 'animate-spin' : ''}
            />
            Refresh
          </button>

          <button
            type="button"
            onClick={() => {
              setShowForm((previous) => !previous)
              setError('')
              setSuccess('')
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-500"
          >
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Close form' : 'Register student'}
          </button>
        </div>
      </section>

      {error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
        >
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300"
        >
          <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {showForm && (
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-lg bg-blue-500/10 p-2 text-blue-400">
              <UserRoundPlus size={20} />
            </div>
            <div>
              <h3 className="font-semibold text-white">
                Register a student
              </h3>
              <p className="mt-1 text-xs text-slate-400">
                Enter the student's details. Face enrollment will follow
                as a separate step.
              </p>
            </div>
          </div>

          <form onSubmit={handleRegister} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="block text-sm text-slate-300">
                  Student name *
                </span>
                <input
                  name="name"
                  value={form.name}
                  onChange={handleInputChange}
                  required
                  maxLength={150}
                  placeholder="Enter full name"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
                />
              </label>

              <label className="space-y-2">
                <span className="block text-sm text-slate-300">
                  Roll number *
                </span>
                <input
                  name="roll_no"
                  value={form.roll_no}
                  onChange={handleInputChange}
                  required
                  maxLength={50}
                  placeholder="Enter unique roll number"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
                />
              </label>

              <label className="space-y-2">
                <span className="block text-sm text-slate-300">
                  Branch
                </span>
                <input
                  name="branch"
                  value={form.branch}
                  onChange={handleInputChange}
                  maxLength={100}
                  placeholder="e.g. AI & DS"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
                />
              </label>

              <label className="space-y-2">
                <span className="block text-sm text-slate-300">
                  Role
                </span>
                <select
                  name="role"
                  value={form.role}
                  onChange={handleInputChange}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500"
                >
                  <option value="student">Student</option>
                  <option value="admin">Admin</option>
                </select>
              </label>
            </div>

            <div className="flex flex-wrap justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  setForm(initialForm)
                }}
                className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {submitting && (
                  <LoaderCircle size={16} className="animate-spin" />
                )}
                {submitting ? 'Registering...' : 'Register student'}
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-3">
        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">Total students</p>
            <Users size={19} className="text-blue-400" />
          </div>
          <p className="mt-4 text-3xl font-bold text-white">
            {loading ? '—' : students.length}
          </p>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">Active students</p>
            <CheckCircle2 size={19} className="text-emerald-400" />
          </div>
          <p className="mt-4 text-3xl font-bold text-white">
            {loading ? '—' : activeCount}
          </p>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">Inactive students</p>
            <UserRound size={19} className="text-amber-400" />
          </div>
          <p className="mt-4 text-3xl font-bold text-white">
            {loading ? '—' : inactiveCount}
          </p>
        </article>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
        <div className="flex flex-col gap-4 border-b border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-semibold text-white">
              Registered students
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Student records retrieved from the database
            </p>
          </div>

          <div className="relative w-full sm:max-w-xs">
            <Search
              size={17}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
            />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search students..."
              className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2.5 pl-10 pr-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 text-sm text-slate-400">
            <LoaderCircle size={20} className="animate-spin" />
            Loading student records...
          </div>
        ) : filteredStudents.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center px-5 text-center">
            <Users size={30} className="text-slate-600" />
            <p className="mt-3 font-medium text-slate-300">
              No students found
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {search
                ? 'Try another search term.'
                : 'Student records will appear here after registration.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-4 font-medium">Student</th>
                  <th className="px-5 py-4 font-medium">Roll number</th>
                  <th className="px-5 py-4 font-medium">Branch</th>
                  <th className="px-5 py-4 font-medium">Role</th>
                  <th className="px-5 py-4 font-medium">Status</th>
                  <th className="px-5 py-4 font-medium">Action</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-800">
                {filteredStudents.map((student) => (
                  <tr key={student.id} className="hover:bg-slate-800/40">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/10 text-blue-400">
                          <UserRound size={17} />
                        </div>
                        <span className="font-medium text-slate-200">
                          {student.name}
                        </span>
                      </div>
                    </td>

                    <td className="px-5 py-4 text-slate-300">
                      {student.roll_no}
                    </td>

                    <td className="px-5 py-4 text-slate-400">
                      {student.branch || '—'}
                    </td>

                    <td className="px-5 py-4 capitalize text-slate-400">
                      {student.role || 'student'}
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                          student.is_active
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-slate-700 text-slate-400'
                        }`}
                      >
                        {student.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      <button
                        type="button"
                        onClick={() => handleStatusChange(student)}
                        disabled={updatingId === student.id}
                        className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                      >
                        {updatingId === student.id
                          ? 'Updating...'
                          : student.is_active
                            ? 'Deactivate'
                            : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="border-t border-slate-800 px-5 py-3 text-xs text-slate-500">
          Showing {filteredStudents.length} of {students.length} students
        </div>
      </section>
    </div>
  )
}
