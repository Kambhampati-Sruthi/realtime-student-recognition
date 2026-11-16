
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function getRecognitionWebSocketURL() {
  const url = new URL(API_BASE_URL)

  url.protocol =
    url.protocol === 'https:' ? 'wss:' : 'ws:'

  url.pathname = '/api/recognition/ws'
  url.search = ''
  url.hash = ''

  return url.toString()
}

export function connectRecognitionSocket({
  onMessage,
  onStatus,
  onError,
}) {
  let manuallyClosed = false

  const socket = new WebSocket(
    getRecognitionWebSocketURL()
  )

  // This controls incoming binary messages, not outgoing Blob frames.
  socket.binaryType = 'arraybuffer'

  socket.onopen = () => {
    onStatus?.('connected')
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      onMessage?.(data)

    } catch (error) {

      console.error(
        '[WEBSOCKET] Invalid server response:',
        error
      )

      onError?.(
        'The server returned an invalid recognition response.'
      )
    }
  }

  socket.onerror = (event) => {

    console.error(
      '[WEBSOCKET] Connection error:',
      event
    )

    onStatus?.('error')

    onError?.(
      'Unable to communicate with the recognition server.'
    )
  }

  socket.onclose = (event) => {

    console.warn(
      '[WEBSOCKET] Closed:',
      {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
        manuallyClosed,
      }
    )

    onStatus?.('disconnected')

    if (event.code === 1013) {

      onError?.(
        'Another camera session is already active.'
      )

    } else if (
      !manuallyClosed &&
      event.code !== 1000
    ) {

      onError?.(
        `Recognition connection interrupted (code ${event.code}).`
      )
    }
  }

  function sendFrame(blob) {

    if (!(blob instanceof Blob)) {
      return false
    }

    if (socket.readyState !== WebSocket.OPEN) {
      return false
    }

    // Single-flight processing should keep this buffer small.
    if (socket.bufferedAmount > 512 * 1024) {
      return false
    }

    socket.send(blob)

    return true
  }

  function close() {

    manuallyClosed = true

    if (
      socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING
    ) {

      socket.close(
        1000,
        'Camera stopped by user.'
      )
    }
  }

  return {
    socket,
    sendFrame,
    close,
  }
}
