import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  Camera,
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
  enrollStudent,
  getStudents,
  registerStudent,
  updateStudentStatus,
} from '../services/api'

const initialForm = {
  name: '',
  roll_no: '',
  branch: '',
  role: 'student',
  year_of_study: '',
  source_type: 'id_card',
}

const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export default function Students() {
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)

  const [form, setForm] = useState(initialForm)
  const [image, setImage] = useState(null)
  const [preview, setPreview] = useState('')
  const [cameraActive, setCameraActive] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [updatingId, setUpdatingId] = useState(null)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const fileInputRef = useRef(null)
  const previewUrlRef = useRef('')

  const releasePreviewUrl = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = ''
    }
  }, [])

  const clearSelectedImage = useCallback(() => {
    releasePreviewUrl()
    setImage(null)
    setPreview('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [releasePreviewUrl])

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setCameraActive(false)
  }, [])

  useEffect(() => {
    return () => {
      stopCamera()
      releasePreviewUrl()
    }
  }, [stopCamera, releasePreviewUrl])

  const loadStudents = useCallback(async (showRefresh = false) => {
    if (showRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    setError('')

    try {
      const data = await getStudents({
        limit: 500,
        offset: 0,
        activeOnly: false,
      })

      if (!Array.isArray(data)) {
        throw new Error('Invalid student data received from backend.')
      }

      setStudents(data)
    } catch (err) {
      console.error('Student loading error:', err)
      setError(err.message || 'Unable to load records.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadStudents()
  }, [loadStudents])

  const filteredStudents = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return students

    return students.filter((student) =>
      [
        student.name,
        student.roll_no,
        student.branch,
        student.role,
        student.year_of_study ? `year ${student.year_of_study}` : '',
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    )
  }, [students, search])

  const activeCount = students.filter((s) => s.is_active === true).length
  const inactiveCount = students.length - activeCount

  function handleInputChange(event) {
    const { name, value } = event.target

    setForm((previous) => ({
      ...previous,
      [name]: value,
      ...(name === 'role' && value !== 'student' ? { year_of_study: '' } : {}),
    }))

    if (name === 'source_type') {
      clearSelectedImage()
      stopCamera()
    }
  }

  function setSelectedImage(file) {
    if (!file) return false

    if (!ALLOWED_TYPES.includes(file.type)) {
      clearSelectedImage()
      setError('Only JPEG, PNG, and WebP images are supported.')
      return false
    }

    if (file.size === 0 || file.size > MAX_IMAGE_SIZE) {
      clearSelectedImage()
      setError('Image size must be between 1 byte and 5 MB.')
      return false
    }

    releasePreviewUrl()
    const previewUrl = URL.createObjectURL(file)
    previewUrlRef.current = previewUrl

    setImage(file)
    setPreview(previewUrl)
    setError('')
    return true
  }

  function handleImageChange(event) {
    const selectedFile = event.target.files?.[0] || null
    if (selectedFile) {
      setSelectedImage(selectedFile)
    }
  }

  async function startCamera() {
    setError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Camera access is not supported by this browser.')
      return
    }

    try {
      stopCamera()
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      })

      if (!videoRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }

      streamRef.current = stream
      videoRef.current.srcObject = stream
      await videoRef.current.play()
      setCameraActive(true)
    } catch (err) {
      stopCamera()
      setError(`Unable to start camera: ${err.message || 'Permission denied'}`)
    }
  }

  function capturePhoto() {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      setError('Camera is not ready. Please wait and try again.')
      return
    }

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return

    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const capturedFile = new File(
          [blob],
          `face-capture-${Date.now()}.jpg`,
          { type: 'image/jpeg' }
        )
        if (setSelectedImage(capturedFile)) {
          stopCamera()
        }
      },
      'image/jpeg',
      0.92
    )
  }

  async function handleRegister(event) {
    event.preventDefault()
    setError('')
    setSuccess('')

    const name = form.name.trim()
    const rollNo = form.roll_no.trim()
    const branch = form.branch.trim()
    const role = form.role

    if (!name || !rollNo || !branch) {
      setError('Full name, roll number / ID, and branch are required.')
      return
    }

    if (role === 'student') {
      if (!form.year_of_study || !['1', '2', '3', '4'].includes(String(form.year_of_study))) {
        setError('Please select a valid year of study for students.')
        return
      }
    }

    setSubmitting(true)
    stopCamera()

    try {
      const yearValue =
        role === 'student' && form.year_of_study
          ? Number(form.year_of_study)
          : null

      if (image) {
        await enrollStudent({
          name,
          roll_no: rollNo,
          branch,
          role,
          year_of_study: yearValue,
          source_type: form.source_type,
          image,
        })
        setSuccess(`${name} was registered and face-enrolled successfully.`)
      } else {
        await registerStudent({
          name,
          roll_no: rollNo,
          branch,
          role,
          year_of_study: yearValue,
        })
        setSuccess(`${name} was registered successfully (details only).`)
      }

      setForm(initialForm)
      clearSelectedImage()
      setShowForm(false)
      await loadStudents()
    } catch (err) {
      console.error('Registration error:', err)
      setError(err.message || 'Registration failed.')
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
      const updatedStudent = await updateStudentStatus(student.id, nextStatus)
      if (!updatedStudent || !updatedStudent.id) {
        throw new Error('Backend did not return the updated record.')
      }

      setStudents((previous) =>
        previous.map((item) => (item.id === student.id ? updatedStudent : item))
      )
      setSuccess(
        `${student.name} has been ${nextStatus ? 'activated' : 'deactivated'}.`
      )
    } catch (err) {
      console.error('Status update error:', err)
      setError(err.message || 'Unable to update status.')
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div className="space-y-7">
      {/* HEADER */}
      <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm text-blue-400">Database management</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">
            Student Management
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Manage registered users, ID-card / face enrollment, and status.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => loadStudents(true)}
            disabled={refreshing || loading}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>

          <button
            type="button"
            onClick={() => {
              if (showForm) {
                stopCamera()
                clearSelectedImage()
              }
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

      {/* REGISTRATION FORM */}
      {showForm && (
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="rounded-lg bg-blue-500/10 p-2 text-blue-400">
              <UserRoundPlus size={20} />
            </div>
            <div>
              <h3 className="font-semibold text-white">Register a user</h3>
              <p className="mt-1 text-xs text-slate-400">
                Enter user details and upload an ID card or face photo for instant recognition enrollment.
              </p>
            </div>
          </div>

          <form onSubmit={handleRegister} className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="block text-sm text-slate-300">Full name *</span>
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
                <span className="block text-sm text-slate-300">Roll number / ID *</span>
                <input
                  name="roll_no"
                  value={form.roll_no}
                  onChange={handleInputChange}
                  required
                  maxLength={50}
                  placeholder="Enter unique roll number or ID"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
                />
              </label>

              <label className="space-y-2">
                <span className="block text-sm text-slate-300">Branch / Department *</span>
                <input
                  name="branch"
                  value={form.branch}
                  onChange={handleInputChange}
                  required
                  maxLength={100}
                  placeholder="e.g. AI & DS"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
                />
              </label>

              <label className="space-y-2">
                <span className="block text-sm text-slate-300">Role</span>
                <select
                  name="role"
                  value={form.role}
                  onChange={handleInputChange}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500"
                >
                  <option value="student">Student</option>
                  <option value="faculty">Faculty</option>
                  <option value="staff">Staff</option>
                  <option value="admin">Admin</option>
                </select>
              </label>

              {form.role === 'student' && (
                <label className="space-y-2 sm:col-span-2">
                  <span className="block text-sm text-slate-300">Year of study *</span>
                  <select
                    name="year_of_study"
                    value={form.year_of_study}
                    onChange={handleInputChange}
                    required
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500"
                  >
                    <option value="">Select year</option>
                    <option value="1">1st year</option>
                    <option value="2">2nd year</option>
                    <option value="3">3rd year</option>
                    <option value="4">4th year</option>
                  </select>
                </label>
              )}
            </div>

            {/* ID CARD / DIRECT FACE ENROLLMENT METHOD */}
            <div className="border-t border-slate-800 pt-4">
              <span className="mb-3 block text-sm font-medium text-slate-300">
                Photo / ID Card Registration Method
              </span>

              <div className="grid gap-3 sm:grid-cols-2">
                <label
                  className={`cursor-pointer rounded-lg border p-3.5 text-sm ${
                    form.source_type === 'id_card'
                      ? 'border-blue-500 bg-blue-500/10 text-white'
                      : 'border-slate-700 bg-slate-950 text-slate-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="source_type"
                    value="id_card"
                    checked={form.source_type === 'id_card'}
                    onChange={handleInputChange}
                    className="mr-2 accent-blue-500"
                  />
                  <span className="font-medium">ID-card upload</span>
                  <p className="mt-1 text-xs text-slate-400">
                    Upload the complete ID card; the system automatically extracts the face.
                  </p>
                </label>

                <label
                  className={`cursor-pointer rounded-lg border p-3.5 text-sm ${
                    form.source_type === 'face'
                      ? 'border-blue-500 bg-blue-500/10 text-white'
                      : 'border-slate-700 bg-slate-950 text-slate-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="source_type"
                    value="face"
                    checked={form.source_type === 'face'}
                    onChange={handleInputChange}
                    className="mr-2 accent-blue-500"
                  />
                  <span className="font-medium">Direct face registration</span>
                  <p className="mt-1 text-xs text-slate-400">
                    Upload a direct face photo or capture one live with your camera.
                  </p>
                </label>
              </div>

              {form.source_type === 'face' && (
                <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950 p-4">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className={`mb-3 max-h-64 w-full rounded-lg bg-black object-contain ${
                      cameraActive ? 'block' : 'hidden'
                    }`}
                  />
                  <canvas ref={canvasRef} className="hidden" />

                  <div className="flex flex-wrap gap-2">
                    {!cameraActive ? (
                      <button
                        type="button"
                        onClick={startCamera}
                        className="inline-flex items-center gap-2 rounded-lg border border-blue-500/50 px-3 py-2 text-xs font-medium text-blue-300 hover:bg-blue-500/10"
                      >
                        <Camera size={15} />
                        Capture via camera
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={capturePhoto}
                          className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-500"
                        >
                          Take photo
                        </button>
                        <button
                          type="button"
                          onClick={stopCamera}
                          className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
                        >
                          Stop camera
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )}

              <div className="mt-4">
                <label className="mb-2 block text-xs text-slate-400">
                  {form.source_type === 'id_card'
                    ? 'Select ID-card image (JPEG, PNG, WebP — max 5 MB)'
                    : 'Select face photograph (JPEG, PNG, WebP — max 5 MB)'}
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageChange}
                  className="block w-full rounded-lg border border-dashed border-slate-700 bg-slate-950 p-3 text-xs text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:font-medium file:text-white"
                />
              </div>

              {preview && (
                <div className="mt-3 flex items-center gap-4 rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <img
                    src={preview}
                    alt="Preview"
                    className="h-20 w-20 rounded-md object-cover"
                  />
                  <div className="text-xs">
                    <p className="font-medium text-slate-200">{image?.name}</p>
                    <button
                      type="button"
                      onClick={clearSelectedImage}
                      className="mt-1 text-red-400 hover:text-red-300"
                    >
                      Remove image
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  stopCamera()
                  clearSelectedImage()
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
                {submitting && <LoaderCircle size={16} className="animate-spin" />}
                {submitting ? 'Registering...' : 'Register & enroll'}
              </button>
            </div>
          </form>
        </section>
      )}

      {/* STATISTICS */}
      <section className="grid gap-4 sm:grid-cols-3">
        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">Total records</p>
            <Users size={19} className="text-blue-400" />
          </div>
          <p className="mt-4 text-3xl font-bold text-white">
            {loading ? '—' : students.length}
          </p>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">Active</p>
            <CheckCircle2 size={19} className="text-emerald-400" />
          </div>
          <p className="mt-4 text-3xl font-bold text-white">
            {loading ? '—' : activeCount}
          </p>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">Inactive</p>
            <UserRound size={19} className="text-amber-400" />
          </div>
          <p className="mt-4 text-3xl font-bold text-white">
            {loading ? '—' : inactiveCount}
          </p>
        </article>
      </section>

      {/* TABLE */}
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
        <div className="flex flex-col gap-4 border-b border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-semibold text-white">Registered records</h3>
            <p className="mt-1 text-xs text-slate-500">
              Records retrieved from the database
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
              placeholder="Search records..."
              className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2.5 pl-10 pr-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 text-sm text-slate-400">
            <LoaderCircle size={20} className="animate-spin" />
            Loading records...
          </div>
        ) : filteredStudents.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center px-5 text-center">
            <Users size={30} className="text-slate-600" />
            <p className="mt-3 font-medium text-slate-300">No records found</p>
            <p className="mt-1 text-sm text-slate-500">
              {search ? 'Try another search term.' : 'Records will appear here after registration.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-4 font-medium">Name</th>
                  <th className="px-5 py-4 font-medium">Roll number / ID</th>
                  <th className="px-5 py-4 font-medium">Branch</th>
                  <th className="px-5 py-4 font-medium">Role</th>
                  <th className="px-5 py-4 font-medium">Year</th>
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

                    <td className="px-5 py-4 text-slate-300">{student.roll_no}</td>
                    <td className="px-5 py-4 text-slate-400">{student.branch || '—'}</td>
                    <td className="px-5 py-4 capitalize text-slate-400">
                      {student.role || 'student'}
                    </td>
                    <td className="px-5 py-4 text-slate-400">
                      {student.role === 'student' && student.year_of_study
                        ? `Year ${student.year_of_study}`
                        : '—'}
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
          Showing {filteredStudents.length} of {students.length} records
        </div>
      </section>
    </div>
  )
}