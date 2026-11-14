
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'


function getRecognitionWebSocketURL() {
  const url = new URL(API_BASE_URL)

  url.protocol =
    url.protocol === 'https:' ? 'wss:' : 'ws:'

  url.pathname = '/api/recognition/ws'
  url.search = ''

  return url.toString()
}


export function connectRecognitionSocket({
  onMessage,
  onStatus,
  onError,
}) {
  const socket = new WebSocket(
    getRecognitionWebSocketURL()
  )

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
        'Invalid recognition response:',
        error
      )

      onError?.('Invalid response received from backend.')
    }
  }

  socket.onerror = () => {
    onStatus?.('error')
    onError?.('Unable to communicate with the recognition server.')
  }

  socket.onclose = (event) => {
    onStatus?.('disconnected')

    if (event.code === 1013) {
      onError?.('Another camera session is already active.')
    }
  }

  function sendFrame(blob) {
    if (
      socket.readyState !== WebSocket.OPEN ||
      socket.bufferedAmount > 1500000
    ) {
      return false
    }

    socket.send(blob)

    return true
  }

  function close() {
    if (
      socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING
    ) {
      socket.close()
    }
  }

  return {
    socket,
    sendFrame,
    close,
  }
}
