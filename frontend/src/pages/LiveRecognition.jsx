
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  Camera,
  CameraOff,
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  ScanFace,
  Wifi,
  WifiOff,
} from 'lucide-react'

import { connectRecognitionSocket } from '../services/recognition'


export default function LiveRecognition() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)

  const streamRef = useRef(null)
  const socketRef = useRef(null)
  const captureIntervalRef = useRef(null)
  const sendingRef = useRef(false)

  const [cameraActive, setCameraActive] = useState(false)
  const [connecting, setConnecting] = useState(false)

  const [connectionStatus, setConnectionStatus] =
    useState('disconnected')

  const [people, setPeople] = useState([])
  const [processingTime, setProcessingTime] = useState(null)
  const [error, setError] = useState('')

  const [sessionId, setSessionId] = useState(null)

  const startFrameCapture = useCallback(() => {
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current)
    }

    captureIntervalRef.current = setInterval(() => {
      const video = videoRef.current
      const canvas = canvasRef.current
      const connection = socketRef.current

      if (
        !video ||
        !canvas ||
        !connection ||
        video.readyState < 2 ||
        sendingRef.current
      ) {
        return
      }

      const context = canvas.getContext('2d')

      if (!context) {
        return
      }

      const width = video.videoWidth
      const height = video.videoHeight

      if (!width || !height) {
        return
      }

      // Resize the transmitted frame to reduce CPU and
      // network workload. Recognition thresholds remain unchanged.
      const maxWidth = 640
      const scale = Math.min(1, maxWidth / width)

      canvas.width = Math.round(width * scale)
      canvas.height = Math.round(height * scale)

      context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
      )

      sendingRef.current = true

      canvas.toBlob(
        (blob) => {
          try {
            if (blob) {
              connection.sendFrame(blob)
            }
          } finally {
            sendingRef.current = false
          }
        },
        'image/jpeg',
        0.72
      )
    }, 500)
  }, [])


  const stopCamera = useCallback(() => {
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current)
      captureIntervalRef.current = null
    }

    sendingRef.current = false

    if (socketRef.current) {
      socketRef.current.close()
      socketRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop()
      })

      streamRef.current = null
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setCameraActive(false)
    setConnecting(false)
    setConnectionStatus('disconnected')
    setPeople([])
    setProcessingTime(null)
    setSessionId(null)
  }, [])


  const startCamera = async () => {
    try {
      setError('')
      setConnecting(true)
      setPeople([])

      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          'Camera access is unavailable. Use localhost or HTTPS.'
        )
      }

      const stream =
        await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
          audio: false,
        })

      streamRef.current = stream

      if (!videoRef.current) {
        throw new Error('Camera preview is unavailable.')
      }

      videoRef.current.srcObject = stream

      await videoRef.current.play()

      setCameraActive(true)

      const connection = connectRecognitionSocket({
        onStatus: (status) => {
          setConnectionStatus(status)

          if (status === 'connected') {
            setConnecting(false)
            setError('')
            startFrameCapture()
          }

          if (status === 'disconnected') {
            setConnecting(false)
          }
        },

        onMessage: (data) => {
          if (data.type === 'connected') {
            setSessionId(data.session_id)
            return
          }

          if (data.type === 'recognition_result') {
            setPeople(data.people || [])
            setProcessingTime(data.processing_ms)
            return
          }

          if (data.type === 'error') {
            setError(data.message)
          }
        },

        onError: (message) => {
          setError(message)
        },
      })

      socketRef.current = connection

      // A failed connection should not leave the webcam running.
      connection.socket.addEventListener(
        'close',
        () => {
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => {
              track.stop()
            })

            streamRef.current = null
          }

          if (captureIntervalRef.current) {
            clearInterval(captureIntervalRef.current)
            captureIntervalRef.current = null
          }

          setCameraActive(false)
          setConnecting(false)
          setPeople([])
        },
        { once: true }
      )

    } catch (err) {
      console.error('Camera startup failed:', err)

      setError(
        err.message || 'Unable to start the camera.'
      )

      stopCamera()
    }
  }


  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [stopCamera])


  const recognizedPeople = people.filter(
    (person) => person.status === 'recognized'
  )

  const unknownPeople = people.filter(
    (person) => person.status === 'unknown'
  )

  const pendingPeople = people.filter(
    (person) => person.status === 'pending'
  )


  return (
    <div className="space-y-6">

      {/* Page heading */}
      <div>
        <div className="flex items-center gap-2 text-blue-400">
          <ScanFace size={20} />
          <span className="text-sm font-medium">
            AI Vision System
          </span>
        </div>

        <h2 className="mt-2 text-2xl font-bold text-white">
          Live Recognition
        </h2>

        <p className="mt-2 text-sm text-slate-400">
          Real-time student detection and face recognition.
        </p>
      </div>


      {/* Camera and recognition status */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

        <StatusCard
          label="Camera"
          value={cameraActive ? 'Active' : 'Stopped'}
          active={cameraActive}
        />

        <StatusCard
          label="Connection"
          value={connectionStatus}
          active={connectionStatus === 'connected'}
        />

        <StatusCard
          label="People detected"
          value={String(people.length)}
        />

        <StatusCard
          label="Recognized"
          value={String(recognizedPeople.length)}
          active={recognizedPeople.length > 0}
        />

      </div>


      {/* Camera section */}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,1fr)]">

        <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">

          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
            <div>
              <h3 className="font-semibold text-white">
                Camera Preview
              </h3>

              <p className="mt-1 text-xs text-slate-500">
                Browser camera with AI detection overlay
              </p>
            </div>

            <div className="flex items-center gap-2 text-xs">
              {connectionStatus === 'connected' ? (
                <>
                  <Wifi size={15} className="text-green-400" />
                  <span className="text-green-400">
                    Connected
                  </span>
                </>
              ) : (
                <>
                  <WifiOff size={15} className="text-slate-500" />
                  <span className="text-slate-400">
                    Disconnected
                  </span>
                </>
              )}
            </div>
          </div>


          <div className="relative aspect-video overflow-hidden bg-black">

            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="absolute inset-0 h-full w-full object-contain"
            />

            <canvas
              ref={canvasRef}
              className="hidden"
            />

            {/* Detection overlays */}
            <div className="pointer-events-none absolute inset-0">
              {people.map((person, index) => {
                const [x1, y1, x2, y2] = person.bbox

                const frameWidth =
                  canvasRef.current?.width || 640

                const frameHeight =
                  canvasRef.current?.height || 480

                const left = `${(x1 / frameWidth) * 100}%`
                const top = `${(y1 / frameHeight) * 100}%`
                const width = `${((x2 - x1) / frameWidth) * 100}%`
                const height = `${((y2 - y1) / frameHeight) * 100}%`

                const recognized =
                  person.status === 'recognized'

                const borderColor = recognized
                  ? 'border-green-400'
                  : 'border-yellow-400'

                return (
                  <div
                    key={person.track_id ?? `person-${index}`}
                    className={`absolute border-2 ${borderColor}`}
                    style={{
                      left,
                      top,
                      width,
                      height,
                    }}
                  >
                    <span
                      className={`absolute -top-6 left-0 whitespace-nowrap rounded px-2 py-1 text-xs font-semibold ${
                        recognized
                          ? 'bg-green-500 text-white'
                          : 'bg-yellow-500 text-black'
                      }`}
                    >
                      {recognized
                        ? person.student.name
                        : `Track ${person.track_id ?? 'Pending'}`}
                    </span>
                  </div>
                )
              })}
            </div>


            {!cameraActive && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center">
                <CameraOff
                  size={42}
                  className="text-slate-600"
                />

                <p className="font-medium text-slate-300">
                  Camera is not running
                </p>

                <p className="text-xs text-slate-500">
                  Start the camera to begin recognition.
                </p>
              </div>
            )}

          </div>


          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 p-4">

            <div className="text-xs text-slate-500">
              {processingTime !== null
                ? `Backend processing: ${processingTime} ms`
                : 'Waiting for camera frames'}
            </div>

            {!cameraActive ? (
              <button
                onClick={startCamera}
                disabled={connecting}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
              >
                {connecting ? (
                  <LoaderCircle
                    size={17}
                    className="animate-spin"
                  />
                ) : (
                  <Camera size={17} />
                )}

                {connecting ? 'Connecting...' : 'Start Camera'}
              </button>
            ) : (
              <button
                onClick={stopCamera}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-500"
              >
                <CameraOff size={17} />
                Stop Camera
              </button>
            )}

          </div>
        </section>


        {/* Recognition results */}
        <section className="rounded-xl border border-slate-800 bg-slate-900">

          <div className="border-b border-slate-800 px-5 py-4">
            <h3 className="font-semibold text-white">
              Recognition Results
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              Confirmed identities from the active camera
            </p>
          </div>


          <div className="max-h-[520px] space-y-3 overflow-y-auto p-4">

            {recognizedPeople.length === 0 &&
              pendingPeople.length === 0 &&
              unknownPeople.length === 0 && (
                <div className="py-12 text-center">
                  <ScanFace
                    size={36}
                    className="mx-auto text-slate-600"
                  />

                  <p className="mt-3 text-sm text-slate-400">
                    No people detected yet
                  </p>
                </div>
              )}


            {people.map((person, index) => (
              <div
                key={person.track_id ?? `result-${index}`}
                className="rounded-lg border border-slate-800 bg-slate-950 p-4"
              >

                <div className="flex items-center justify-between gap-2">

                  <span className="text-xs text-slate-500">
                    Track #{person.track_id ?? 'Pending'}
                  </span>

                  {person.status === 'recognized' ? (
                    <span className="flex items-center gap-1 text-xs text-green-400">
                      <CircleCheck size={14} />
                      Recognized
                    </span>
                  ) : person.status === 'pending' ? (
                    <span className="text-xs text-yellow-400">
                      Confirming identity
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-slate-400">
                      <CircleAlert size={14} />
                      Unknown / Not confirmed
                    </span>
                  )}

                </div>


                {person.student && (
                  <div className="mt-4 space-y-2">

                    <h4 className="text-lg font-semibold text-white">
                      {person.student.name}
                    </h4>

                    <DetailRow
                      label="Roll number"
                      value={person.student.roll_no}
                    />

                    <DetailRow
                      label="Branch"
                      value={person.student.branch || 'Not specified'}
                    />

                    <DetailRow
                      label="Role"
                      value={person.student.role || 'Student'}
                    />

                  </div>
                )}

                {person.similarity !== null &&
                  person.similarity !== undefined && (
                    <p className="mt-3 text-xs text-slate-500">
                      Similarity: {person.similarity.toFixed(4)}
                    </p>
                  )}

              </div>
            ))}

          </div>
        </section>

      </div>


      {/* Error message */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-300">
          <CircleAlert size={18} className="mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}


      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-3">

        <SummaryCard
          label="Recognized students"
          value={recognizedPeople.length}
        />

        <SummaryCard
          label="Pending confirmation"
          value={pendingPeople.length}
        />

        <SummaryCard
          label="Unknown / unconfirmed"
          value={unknownPeople.length}
        />

      </div>

      {sessionId && (
        <p className="text-xs text-slate-600">
          Session: {sessionId}
        </p>
      )}

    </div>
  )
}


function StatusCard({ label, value, active = false }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className={`mt-2 text-lg font-semibold ${
        active ? 'text-green-400' : 'text-white'
      }`}>
        {value}
      </p>
    </div>
  )
}


function DetailRow({ label, value }) {
  return (
    <div className="flex justify-between gap-3 text-sm">
      <span className="text-slate-500">
        {label}
      </span>

      <span className="text-right text-slate-300">
        {value}
      </span>
    </div>
  )
}


function SummaryCard({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className="mt-2 text-2xl font-bold text-white">
        {value}
      </p>
    </div>
  )
}
