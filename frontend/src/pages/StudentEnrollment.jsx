import { useEffect, useRef, useState } from 'react'
import { enrollStudent } from '../services/api'

const initialForm = {
  name: '',
  roll_no: '',
  branch: '',
  year_of_study: '',
  source_type: 'id_card',
}

const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export default function StudentEnrollment() {
  const [form, setForm] = useState(initialForm)
  const [image, setImage] = useState(null)
  const [preview, setPreview] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(null)
  const [cameraActive, setCameraActive] = useState(false)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const fileInputRef = useRef(null)
  const previewUrlRef = useRef('')

  function releasePreviewUrl() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = ''
    }
  }

  function clearSelectedImage() {
    releasePreviewUrl()
    setImage(null)
    setPreview('')

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setCameraActive(false)
  }

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
        streamRef.current = null
      }

      releasePreviewUrl()
    }
  }, [])

  function updateField(event) {
    const { name, value } = event.target

    setForm((current) => ({
      ...current,
      [name]: value,
    }))

    setError('')
    setSuccess(null)

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

    if (file.size === 0) {
      clearSelectedImage()
      setError('The selected image is empty. Please choose another image.')
      return false
    }

    if (file.size > MAX_IMAGE_SIZE) {
      clearSelectedImage()
      setError('Image size must not exceed 5 MB.')
      return false
    }

    releasePreviewUrl()

    const previewUrl = URL.createObjectURL(file)

    previewUrlRef.current = previewUrl

    setImage(file)
    setPreview(previewUrl)
    setError('')
    setSuccess(null)

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
    setSuccess(null)

    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        'Camera access is not supported by this browser. Use image upload instead.'
      )
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

      if (err.name === 'NotAllowedError') {
        setError(
          'Camera permission was denied. Allow camera access or upload an image.'
        )
      } else if (err.name === 'NotFoundError') {
        setError('No camera was found on this device.')
      } else {
        setError(`Unable to start camera: ${err.message || 'Unknown error'}`)
      }
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

    if (!context) {
      setError('Unable to capture the camera image.')
      return
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setError('Could not capture the image. Please try again.')
          return
        }

        const capturedFile = new File(
          [blob],
          `face-capture-${Date.now()}.jpg`,
          { type: 'image/jpeg' }
        )

        const imageSelected = setSelectedImage(capturedFile)

        if (imageSelected) {
          stopCamera()
        }
      },
      'image/jpeg',
      0.92
    )
  }

  async function handleSubmit(event) {
    event.preventDefault()

    if (loading) return

    setError('')
    setSuccess(null)

    const name = form.name.trim()
    const rollNo = form.roll_no.trim()
    const branch = form.branch.trim()

    if (!name || !rollNo || !branch) {
      setError('Please complete all required student details.')
      return
    }

    if (
      name.length > 150 ||
      rollNo.length > 50 ||
      branch.length > 100
    ) {
      setError('Please check the maximum allowed length of the student details.')
      return
    }

    if (
      form.year_of_study &&
      !['1', '2', '3', '4'].includes(String(form.year_of_study))
    ) {
      setError('Please select a valid year of study.')
      return
    }

    if (!image) {
      setError(
        form.source_type === 'id_card'
          ? 'Please upload the student ID-card image.'
          : 'Please upload a face photograph or capture one using the camera.'
      )
      return
    }

    if (!ALLOWED_TYPES.includes(image.type)) {
      setError('Only JPEG, PNG, and WebP images are supported.')
      return
    }

    if (image.size === 0 || image.size > MAX_IMAGE_SIZE) {
      setError('Image size must be greater than 0 and must not exceed 5 MB.')
      return
    }

    try {
      setLoading(true)
      stopCamera()

      const result = await enrollStudent({
        name,
        roll_no: rollNo,
        branch,
        year_of_study: form.year_of_study
          ? Number(form.year_of_study)
          : null,
        source_type: form.source_type,
        image,
      })

      setSuccess(result)
      setForm(initialForm)
      clearSelectedImage()

      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      setError(err.message || 'Student enrollment failed.')
    } finally {
      setLoading(false)
    }
  }

  const student = success?.student

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100 sm:px-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <p className="text-sm font-medium uppercase tracking-wider text-cyan-400">
            Student management
          </p>

          <h1 className="mt-2 text-3xl font-bold">
            Student face enrollment
          </h1>

          <p className="mt-2 max-w-2xl text-sm text-slate-400">
            Register a student using either their ID card or a direct
            face photograph. You can also capture the face using your camera.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-xl"
        >
          <section>
            <h2 className="mb-4 text-lg font-semibold">Student details</h2>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Student name
                </label>

                <input
                  required
                  maxLength={150}
                  name="name"
                  value={form.name}
                  onChange={updateField}
                  placeholder="Enter full name"
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-500 disabled:opacity-60"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Roll number
                </label>

                <input
                  required
                  maxLength={50}
                  name="roll_no"
                  value={form.roll_no}
                  onChange={updateField}
                  placeholder="Enter roll number"
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-500 disabled:opacity-60"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Branch
                </label>

                <input
                  required
                  maxLength={100}
                  name="branch"
                  value={form.branch}
                  onChange={updateField}
                  placeholder="Example: AI & DS"
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-500 disabled:opacity-60"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Year of study
                </label>

                <select
                  name="year_of_study"
                  value={form.year_of_study}
                  onChange={updateField}
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-500 disabled:opacity-60"
                >
                  <option value="">Select year</option>
                  <option value="1">1st year</option>
                  <option value="2">2nd year</option>
                  <option value="3">3rd year</option>
                  <option value="4">4th year</option>
                </select>
              </div>
            </div>
          </section>

          <div className="border-t border-slate-800 pt-6">
            <h2 className="mb-4 text-lg font-semibold">
              Choose enrollment method
            </h2>

            <div className="grid gap-4 sm:grid-cols-2">
              <label
                className={`cursor-pointer rounded-xl border p-4 ${
                  form.source_type === 'id_card'
                    ? 'border-cyan-500 bg-cyan-950/30'
                    : 'border-slate-700 bg-slate-950'
                }`}
              >
                <input
                  type="radio"
                  name="source_type"
                  value="id_card"
                  checked={form.source_type === 'id_card'}
                  onChange={updateField}
                  disabled={loading}
                  className="mr-2 accent-cyan-500"
                />

                <span className="font-semibold">ID-card upload</span>

                <p className="mt-2 text-sm text-slate-400">
                  Upload the complete student ID card. The backend extracts
                  the face region.
                </p>
              </label>

              <label
                className={`cursor-pointer rounded-xl border p-4 ${
                  form.source_type === 'face'
                    ? 'border-cyan-500 bg-cyan-950/30'
                    : 'border-slate-700 bg-slate-950'
                }`}
              >
                <input
                  type="radio"
                  name="source_type"
                  value="face"
                  checked={form.source_type === 'face'}
                  onChange={updateField}
                  disabled={loading}
                  className="mr-2 accent-cyan-500"
                />

                <span className="font-semibold">Direct face registration</span>

                <p className="mt-2 text-sm text-slate-400">
                  Upload a face photograph or capture a new photograph
                  using your camera.
                </p>
              </label>
            </div>
          </div>

          <section className="border-t border-slate-800 pt-6">
            <h2 className="mb-2 text-lg font-semibold">
              {form.source_type === 'id_card'
                ? 'Upload student ID card'
                : 'Register face photograph'}
            </h2>

            <p className="mb-4 text-sm text-slate-400">
              JPEG, PNG or WebP. Maximum file size: 5 MB.
            </p>

            {form.source_type === 'face' && (
              <div className="mb-5 rounded-xl border border-slate-700 bg-slate-950 p-4">
                <p className="mb-3 font-medium">Live camera capture</p>

                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`mb-4 max-h-96 w-full rounded-lg bg-black object-contain ${
                    cameraActive ? 'block' : 'hidden'
                  }`}
                />

                <canvas ref={canvasRef} className="hidden" />

                <div className="flex flex-wrap gap-3">
                  {!cameraActive ? (
                    <button
                      type="button"
                      onClick={startCamera}
                      disabled={loading}
                      className="rounded-lg border border-cyan-500 px-4 py-2 text-sm font-semibold text-cyan-300 hover:bg-cyan-950 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Start camera
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={capturePhoto}
                        disabled={loading}
                        className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
                      >
                        Capture photograph
                      </button>

                      <button
                        type="button"
                        onClick={stopCamera}
                        disabled={loading}
                        className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                      >
                        Stop camera
                      </button>
                    </>
                  )}
                </div>

                <p className="mt-3 text-xs text-slate-500">
                  Allow browser camera permission when prompted. Camera access
                  normally requires localhost or HTTPS.
                </p>
              </div>
            )}

            <label className="mb-2 block text-sm text-slate-300">
              {form.source_type === 'id_card'
                ? 'Select ID-card image'
                : 'Upload face photograph'}
            </label>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleImageChange}
              disabled={loading}
              className="block w-full rounded-lg border border-dashed border-slate-600 bg-slate-950 p-4 text-sm text-slate-300 file:mr-4 file:rounded-md file:border-0 file:bg-cyan-500 file:px-4 file:py-2 file:font-semibold file:text-slate-950 disabled:opacity-50"
            />

            {preview && (
              <div className="mt-5 rounded-xl border border-slate-700 bg-slate-950 p-4">
                <p className="mb-3 text-sm font-medium text-cyan-300">
                  Selected image preview
                </p>

                <img
                  src={preview}
                  alt="Selected enrollment image"
                  className="max-h-72 max-w-full rounded-lg object-contain"
                />

                <p className="mt-3 break-all text-xs text-slate-400">
                  {image?.name}
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  {(image.size / (1024 * 1024)).toFixed(2)} MB
                </p>

                <button
                  type="button"
                  onClick={clearSelectedImage}
                  disabled={loading}
                  className="mt-3 text-sm text-red-300 hover:text-red-200 disabled:opacity-50"
                >
                  Remove selected image
                </button>
              </div>
            )}
          </section>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-300"
            >
              {error}
            </div>
          )}

          {success && (
            <div
              role="status"
              className="rounded-lg border border-emerald-800 bg-emerald-950/30 p-4 text-sm text-emerald-300"
            >
              <p className="font-semibold">
                Face enrollment completed successfully.
              </p>

              <p className="mt-2">
                {student?.name} — {student?.roll_no}
              </p>

              <p>
                Embeddings saved:{' '}
                {success.embedding_count ??
                  success.embeddings_saved ??
                  '5'}
              </p>

              <p>
                Enrollment status:{' '}
                {student?.enrollment_status ?? success.enrollment_status ?? 'enrolled'}
              </p>

              <p className="mt-1 text-xs text-emerald-400">
                {success.created
                  ? 'New student registered.'
                  : 'Existing student enrolled.'}
              </p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-cyan-500 px-5 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading
              ? 'Processing face and saving enrollment...'
              : 'Register and enroll student'}
          </button>
        </form>
      </div>
    </div>
  )
}