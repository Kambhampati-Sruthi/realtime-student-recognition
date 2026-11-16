
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
  RefreshCw,
} from 'lucide-react'

import { connectRecognitionSocket } from '../services/recognition'

export default function LiveRecognition() {
  // ---------------------------------------------------------
  // REFERENCES
  // ---------------------------------------------------------

  const videoRef = useRef(null)
  const canvasRef = useRef(null)

  const streamRef = useRef(null)
  const socketRef = useRef(null)

  const captureIntervalRef = useRef(null)
  const responseTimeoutRef = useRef(null)

  // True while one frame is waiting for its response.
  const sendingRef = useRef(false)

  // Prevents manual camera shutdown from showing errors.
  const manualStopRef = useRef(false)

  // ---------------------------------------------------------
  // STATE
  // ---------------------------------------------------------

  const [cameraActive, setCameraActive] = useState(false)
  const [connecting, setConnecting] = useState(false)

  const [connectionStatus, setConnectionStatus] =
    useState('disconnected')

  const [people, setPeople] = useState([])

  const [processingTime, setProcessingTime] = useState(null)

  const [frameSize, setFrameSize] = useState({
    width: 640,
    height: 480,
  })

  const [error, setError] = useState('')
  const [sessionId, setSessionId] = useState(null)

  // ---------------------------------------------------------
  // CLEAR RESPONSE TIMEOUT
  // ---------------------------------------------------------

  const clearResponseTimeout = useCallback(() => {
    if (responseTimeoutRef.current !== null) {
      clearTimeout(responseTimeoutRef.current)
      responseTimeoutRef.current = null
    }
  }, [])

  // ---------------------------------------------------------
  // STOP FRAME CAPTURE
  // ---------------------------------------------------------

  const stopFrameCapture = useCallback(() => {
    if (captureIntervalRef.current !== null) {
      clearInterval(captureIntervalRef.current)
      captureIntervalRef.current = null
    }

    clearResponseTimeout()

    sendingRef.current = false
  }, [clearResponseTimeout])

  // ---------------------------------------------------------
  // SEND CAMERA FRAMES
  // SINGLE-FLIGHT REQUEST-RESPONSE PROCESSING
  // ---------------------------------------------------------

  const startFrameCapture = useCallback(() => {
    stopFrameCapture()

    captureIntervalRef.current = setInterval(() => {
      const video = videoRef.current
      const canvas = canvasRef.current
      const connection = socketRef.current

      // -----------------------------------------------
      // VALIDATE CAMERA AND CONNECTION
      // -----------------------------------------------

      if (
        !video ||
        !canvas ||
        !connection ||
        video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
        connection.socket.readyState !== WebSocket.OPEN ||
        sendingRef.current
      ) {
        return
      }

      const videoWidth = video.videoWidth
      const videoHeight = video.videoHeight

      if (!videoWidth || !videoHeight) {
        return
      }

      const context = canvas.getContext('2d')

      if (!context) {
        return
      }

      // -----------------------------------------------
      // RESIZE FRAME
      // -----------------------------------------------

      const maxWidth = 640

      const scale = Math.min(
        1,
        maxWidth / videoWidth
      )

      const width = Math.round(videoWidth * scale)
      const height = Math.round(videoHeight * scale)

      canvas.width = width
      canvas.height = height

      context.drawImage(
        video,
        0,
        0,
        width,
        height
      )

      // -----------------------------------------------
      // CONVERT FRAME TO JPEG
      // -----------------------------------------------

      canvas.toBlob(
        (blob) => {
          if (
            !blob ||
            socketRef.current !== connection ||
            connection.socket.readyState !== WebSocket.OPEN
          ) {
            return
          }

          // Prevent another frame from being sent
          // until this frame receives its response.
          sendingRef.current = true

          const sent = connection.sendFrame(blob)

          if (!sent) {
            sendingRef.current = false
            return
          }

          // -------------------------------------------
          // RESPONSE TIMEOUT
          // -------------------------------------------

          clearResponseTimeout()

          responseTimeoutRef.current = setTimeout(() => {
            if (socketRef.current !== connection) {
              return
            }

            sendingRef.current = false
            responseTimeoutRef.current = null

            setError(
              'Recognition response timed out. Check the backend terminal and connection.'
            )

          }, 20000)
        },
        'image/jpeg',
        0.72
      )
    }, 250)

  }, [stopFrameCapture, clearResponseTimeout])

  // ---------------------------------------------------------
  // CONNECT WEBSOCKET
  // ---------------------------------------------------------

  const connectSocket = useCallback(() => {
    // Close previous connection safely.
    const previousConnection = socketRef.current

    socketRef.current = null

    if (previousConnection) {
      previousConnection.close()
    }

    stopFrameCapture()

    setConnecting(true)
    setError('')
    setConnectionStatus('connecting')

    let activeSocket = null

    try {
      const connection = connectRecognitionSocket({

        // ---------------------------------------------
        // CONNECTION STATUS
        // ---------------------------------------------

        onStatus: (status) => {
          if (
            activeSocket &&
            socketRef.current?.socket !== activeSocket
          ) {
            return
          }

          setConnectionStatus(status)

          if (status === 'connected') {
            // Wait for the backend session initialization
            // message before starting camera frame capture.
            setConnecting(false)
          }

          if (status === 'disconnected') {
            setConnecting(false)
            stopFrameCapture()

            if (!manualStopRef.current) {
              setError(
                'Recognition server disconnected. Your camera preview remains active. Click Reconnect to continue.'
              )
            }
          }

          if (status === 'error') {
            setConnecting(false)
          }
        },

        // ---------------------------------------------
        // BACKEND MESSAGES
        // ---------------------------------------------

        onMessage: (data) => {
          if (
            activeSocket &&
            socketRef.current?.socket !== activeSocket
          ) {
            return
          }

          // Every server response completes the outstanding
          // request, including a frame-processing error.
          if (data.type !== 'connected') {
            sendingRef.current = false
            clearResponseTimeout()
          }

          // -------------------------------------------
          // SESSION CONNECTED
          // -------------------------------------------

          if (data.type === 'connected') {
            setSessionId(data.session_id || null)

            setConnecting(false)
            setConnectionStatus('connected')
            setError('')

            // Start sending frames only after the backend
            // has initialized its recognition session.
            startFrameCapture()

            return
          }

          // -------------------------------------------
          // RECOGNITION RESULTS
          // -------------------------------------------

          if (data.type === 'recognition_result') {
            const receivedPeople = Array.isArray(data.people)
              ? data.people
              : []

            setPeople(receivedPeople)

            setProcessingTime(
              typeof data.processing_ms === 'number'
                ? data.processing_ms
                : null
            )

            if (
              typeof data.frame_width === 'number' &&
              typeof data.frame_height === 'number' &&
              data.frame_width > 0 &&
              data.frame_height > 0
            ) {
              setFrameSize({
                width: data.frame_width,
                height: data.frame_height,
              })
            }

            setError('')

            return
          }

          // -------------------------------------------
          // BACKEND ERROR
          // -------------------------------------------

          if (data.type === 'error') {
            setError(
              data.message ||
              'Recognition backend reported an error.'
            )

            return
          }

          console.warn(
            '[RECOGNITION] Unknown backend message:',
            data
          )
        },

        // ---------------------------------------------
        // CONNECTION ERROR
        // ---------------------------------------------

        onError: (message) => {
          if (
            activeSocket &&
            socketRef.current?.socket !== activeSocket
          ) {
            return
          }

          setError(message)
        },
      })

      activeSocket = connection.socket
      socketRef.current = connection

    } catch (err) {
      console.error(
        '[WEBSOCKET] Connection failed:',
        err
      )

      setConnecting(false)
      setConnectionStatus('error')

      setError(
        err.message ||
        'Unable to connect to the recognition server.'
      )
    }

  }, [startFrameCapture, stopFrameCapture, clearResponseTimeout])

  // ---------------------------------------------------------
  // START CAMERA
  // ---------------------------------------------------------

  const startCamera = async () => {
    try {
      manualStopRef.current = false

      setError('')
      setPeople([])
      setProcessingTime(null)
      setSessionId(null)

      setConnecting(true)

      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          'Camera access is unavailable. Use localhost or HTTPS.'
        )
      }

      // -----------------------------------------------
      // REQUEST CAMERA PERMISSION
      // -----------------------------------------------

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      })

      streamRef.current = stream

      const video = videoRef.current

      if (!video) {
        throw new Error(
          'Camera preview element is unavailable.'
        )
      }

      video.srcObject = stream

      await video.play()

      setCameraActive(true)

      // -----------------------------------------------
      // CONNECT BACKEND
      // -----------------------------------------------

      connectSocket()

    } catch (err) {
      console.error(
        '[CAMERA] Startup failed:',
        err
      )

      setError(
        err.message ||
        'Unable to start the camera.'
      )

      stopCamera()
    }
  }

  // ---------------------------------------------------------
  // STOP CAMERA
  // ---------------------------------------------------------

  const stopCamera = useCallback(() => {
    manualStopRef.current = true

    stopFrameCapture()

    // Close WebSocket.
    const connection = socketRef.current

    socketRef.current = null

    if (connection) {
      connection.close()
    }

    // Stop camera tracks.
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop()
      })

      streamRef.current = null
    }

    // Clear video preview.
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    sendingRef.current = false

    setCameraActive(false)
    setConnecting(false)
    setConnectionStatus('disconnected')

    setPeople([])
    setProcessingTime(null)
    setSessionId(null)

  }, [stopFrameCapture])

  // ---------------------------------------------------------
  // RECONNECT
  // ---------------------------------------------------------

  const reconnectSocket = useCallback(() => {
    if (!streamRef.current) {
      setError(
        'Camera is not active. Start the camera first.'
      )

      return
    }

    manualStopRef.current = false

    setError('')
    setPeople([])
    setProcessingTime(null)
    setSessionId(null)

    connectSocket()

  }, [connectSocket])

  // ---------------------------------------------------------
  // COMPONENT CLEANUP
  // ---------------------------------------------------------

  useEffect(() => {
    return () => {
      manualStopRef.current = true

      if (captureIntervalRef.current !== null) {
        clearInterval(captureIntervalRef.current)
      }

      if (responseTimeoutRef.current !== null) {
        clearTimeout(responseTimeoutRef.current)
      }

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
    }
  }, [])

  // ---------------------------------------------------------
  // RECOGNITION COUNTS
  // ---------------------------------------------------------

  const recognizedPeople = people.filter(
    (person) => person.status === 'recognized'
  )

  const pendingPeople = people.filter(
    (person) => person.status === 'pending'
  )

  const unknownPeople = people.filter(
    (person) => person.status === 'unknown'
  )

  const trackingPeople = people.filter(
    (person) => person.status === 'tracking'
  )

  const frameAspectRatio =
    frameSize.width > 0 && frameSize.height > 0
      ? `${frameSize.width} / ${frameSize.height}`
      : '4 / 3'

  // ---------------------------------------------------------
  // USER INTERFACE
  // ---------------------------------------------------------

  return (
    <div className="space-y-6">

      {/* PAGE HEADER */}

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

      {/* STATUS CARDS */}

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

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,1fr)]">

        {/* ----------------------------------------------- */}
        {/* CAMERA PREVIEW */}
        {/* ----------------------------------------------- */}

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
                  <Wifi
                    size={15}
                    className="text-green-400"
                  />

                  <span className="text-green-400">
                    Connected
                  </span>
                </>
              ) : (
                <>
                  <WifiOff
                    size={15}
                    className="text-slate-500"
                  />

                  <span className="text-slate-400">
                    {connectionStatus}
                  </span>
                </>
              )}

            </div>

          </div>

          {/* VIDEO AND DETECTION OVERLAY */}

          <div
            className="relative mx-auto w-full overflow-hidden bg-black"
            style={{ aspectRatio: frameAspectRatio }}
          >

            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="absolute inset-0 h-full w-full object-fill"
            />

            <canvas
              ref={canvasRef}
              className="hidden"
            />

            {/* DETECTION BOXES */}

            <div className="pointer-events-none absolute inset-0">

              {people.map((person, index) => {

                if (
                  !Array.isArray(person.bbox) ||
                  person.bbox.length !== 4
                ) {
                  return null
                }

                const [x1, y1, x2, y2] = person.bbox

                const left =
                  (x1 / frameSize.width) * 100

                const top =
                  (y1 / frameSize.height) * 100

                const width =
                  ((x2 - x1) / frameSize.width) * 100

                const height =
                  ((y2 - y1) / frameSize.height) * 100

                const recognized =
                  person.status === 'recognized'

                const pending =
                  person.status === 'pending'

                const tracking =
                  person.status === 'tracking'

                const borderColor = recognized
                  ? 'border-green-400'
                  : pending
                    ? 'border-yellow-400'
                    : 'border-red-400'

                const label = recognized
                  ? person.student?.name || 'Recognized'
                  : pending
                    ? `Confirming: ${person.track_id ?? 'Track'}`
                    : tracking
                      ? `Tracking: ${person.track_id ?? 'Pending'}`
                      : `Unknown: ${person.track_id ?? 'Pending'}`

                return (
                  <div
                    key={person.track_id ?? `person-${index}`}
                    className={`absolute border-2 ${borderColor}`}
                    style={{
                      left: `${left}%`,
                      top: `${top}%`,
                      width: `${width}%`,
                      height: `${height}%`,
                    }}
                  >

                    <span
                      className={`absolute -top-7 left-0 whitespace-nowrap rounded px-2 py-1 text-xs font-semibold ${
                        recognized
                          ? 'bg-green-500 text-white'
                          : pending
                            ? 'bg-yellow-400 text-black'
                            : 'bg-red-500 text-white'
                      }`}
                    >
                      {label}
                    </span>

                  </div>
                )
              })}

            </div>

            {/* CAMERA NOT ACTIVE */}

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

          {/* CAMERA CONTROLS */}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 p-4">

            <div className="text-xs text-slate-500">

              {processingTime !== null
                ? `Backend processing: ${processingTime} ms`
                : 'Waiting for camera frames'}

            </div>

            <div className="flex flex-wrap gap-2">

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

                  {connecting
                    ? 'Connecting...'
                    : 'Start Camera'}

                </button>

              ) : connectionStatus !== 'connected' ? (

                <button
                  onClick={reconnectSocket}
                  disabled={connecting}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
                >

                  {connecting ? (
                    <LoaderCircle
                      size={17}
                      className="animate-spin"
                    />
                  ) : (
                    <RefreshCw size={17} />
                  )}

                  {connecting
                    ? 'Connecting...'
                    : 'Reconnect'}

                </button>

              ) : null}

              {cameraActive && (
                <button
                  onClick={stopCamera}
                  className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-500"
                >

                  <CameraOff size={17} />

                  Stop Camera

                </button>
              )}

            </div>

          </div>

        </section>

        {/* ----------------------------------------------- */}
        {/* RECOGNITION RESULTS */}
        {/* ----------------------------------------------- */}

        <section className="rounded-xl border border-slate-800 bg-slate-900">

          <div className="border-b border-slate-800 px-5 py-4">

            <h3 className="font-semibold text-white">
              Recognition Results
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              Live identities and recognition status
            </p>

          </div>

          <div className="max-h-[520px] space-y-3 overflow-y-auto p-4">

            {people.length === 0 && (
              <div className="py-12 text-center">

                <ScanFace
                  size={36}
                  className="mx-auto text-slate-600"
                />

                <p className="mt-3 text-sm text-slate-400">
                  No people detected yet
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  Results will appear when the backend processes a frame.
                </p>

              </div>
            )}

            {people.map((person, index) => {

              const recognized =
                person.status === 'recognized'

              const pending =
                person.status === 'pending'

              const tracking =
                person.status === 'tracking'

              return (
                <div
                  key={person.track_id ?? `result-${index}`}
                  className="rounded-lg border border-slate-800 bg-slate-950 p-4"
                >

                  {/* TRACK STATUS */}

                  <div className="flex items-center justify-between gap-2">

                    <span className="text-xs text-slate-500">
                      Track #{person.track_id ?? 'Pending'}
                    </span>

                    {recognized ? (
                      <span className="flex items-center gap-1 text-xs text-green-400">

                        <CircleCheck size={14} />

                        Recognized

                      </span>
                    ) : pending ? (
                      <span className="text-xs text-yellow-400">
                        Confirming identity
                      </span>
                    ) : tracking ? (
                      <span className="text-xs text-blue-400">
                        Tracking person
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-slate-400">

                        <CircleAlert size={14} />

                        Unknown / Not confirmed

                      </span>
                    )}

                  </div>

                  {/* CONFIRMED STUDENT DETAILS */}

                  {person.student && (
                    <div className="mt-4 space-y-2">

                      <h4 className="text-lg font-semibold text-white">
                        {person.student.name || 'Unknown student'}
                      </h4>

                      <DetailRow
                        label="Roll number"
                        value={person.student.roll_no || '—'}
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

                  {/* PENDING CANDIDATE */}

                  {pending && (
                    <div className="mt-3 rounded-md border border-yellow-800/50 bg-yellow-950/20 p-3">

                      <p className="text-xs font-medium text-yellow-400">
                        Candidate:
                        {' '}
                        {person.last_candidate || 'Awaiting confirmation'}
                      </p>

                      {person.votes !== undefined && (
                        <p className="mt-2 text-xs text-yellow-300">
                          Confirmation votes:
                          {' '}
                          {person.votes}
                          {' / '}
                          {person.required_votes ?? 3}
                        </p>
                      )}

                    </div>
                  )}

                  {/* FACE STATUS */}

                  {person.face_status && (
                    <p className="mt-2 text-xs text-slate-500">
                      Face status: {person.face_status}
                    </p>
                  )}

                  {/* SIMILARITY */}

                  {person.similarity !== null &&
                    person.similarity !== undefined && (
                      <p className="mt-2 text-xs text-slate-500">
                        Similarity:
                        {' '}
                        {Number(person.similarity).toFixed(4)}
                      </p>
                    )}

                  {/* MATCH MARGIN */}

                  {person.margin !== null &&
                    person.margin !== undefined && (
                      <p className="mt-1 text-xs text-slate-500">
                        Match margin:
                        {' '}
                        {Number(person.margin).toFixed(4)}
                      </p>
                    )}

                  {/* VOTES */}

                  {person.votes !== undefined && !pending && (
                    <p className="mt-1 text-xs text-slate-500">
                      Valid votes: {person.votes}
                    </p>
                  )}

                  {/* FACE ERROR */}

                  {person.face_error && (
                    <p className="mt-2 break-words text-xs text-red-400">
                      {person.face_error}
                    </p>
                  )}

                </div>
              )
            })}

          </div>

        </section>

      </div>

      {/* ERROR MESSAGE */}

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-300">

          <CircleAlert
            size={18}
            className="mt-0.5 shrink-0"
          />

          <p>{error}</p>

        </div>
      )}

      {/* SUMMARY */}

      <div className="grid gap-4 sm:grid-cols-4">

        <SummaryCard
          label="Recognized students"
          value={recognizedPeople.length}
        />

        <SummaryCard
          label="Pending confirmation"
          value={pendingPeople.length}
        />

        <SummaryCard
          label="Tracking"
          value={trackingPeople.length}
        />

        <SummaryCard
          label="Unknown / unconfirmed"
          value={unknownPeople.length}
        />

      </div>

      {/* SESSION ID */}

      {sessionId && (
        <p className="text-xs text-slate-600">
          Session: {sessionId}
        </p>
      )}

    </div>
  )
}

// =========================================================
// STATUS CARD
// =========================================================

function StatusCard({
  label,
  value,
  active = false,
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">

      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p
        className={`mt-2 text-lg font-semibold ${
          active ? 'text-green-400' : 'text-white'
        }`}
      >
        {value}
      </p>

    </div>
  )
}

// =========================================================
// STUDENT DETAIL ROW
// =========================================================

function DetailRow({
  label,
  value,
}) {
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

// =========================================================
// SUMMARY CARD
// =========================================================

function SummaryCard({
  label,
  value,
}) {
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
