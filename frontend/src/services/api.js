const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
)
  .trim()
  .replace(/\/+$/, '')

function getErrorMessage(data, status) {
  if (typeof data?.detail === 'string') {
    return data.detail
  }

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item) => {
        const location = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== 'body').join(' → ')
          : ''

        return location
          ? `${location}: ${item.msg || 'Invalid value'}`
          : item.msg || 'Invalid value'
      })
      .join('; ')
  }

  if (typeof data?.message === 'string') {
    return data.message
  }

  if (typeof data === 'string' && data.trim()) {
    return data
  }

  return `Backend returned HTTP ${status}`
}

async function apiRequest(endpoint, options = {}) {
  const isFormData =
    typeof FormData !== 'undefined' &&
    options.body instanceof FormData

  const headers = new Headers(options.headers || {})

  if (
    options.body &&
    !isFormData &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }

  let response

  const url = `${API_BASE_URL}${endpoint}`

  try {
    response = await fetch(url, {
      ...options,
      headers,
    })
  } catch (error) {
    if (error.name === 'AbortError') {
      throw error
    }

    throw new Error(
      `Unable to connect to backend: ${url}. ` +
      'Check the backend server and VITE_API_BASE_URL.'
    )
  }

  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type') || ''

  let data = null

  if (
    contentType.includes('application/json') ||
    contentType.includes('+json')
  ) {
    data = await response.json().catch(() => null)
  } else {
    data = await response.text().catch(() => '')
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(data, response.status))
  }

  return data
}

// ---------------------------------------------------------
// HEALTH
// ---------------------------------------------------------

export async function getBackendHealth() {
  return apiRequest('/health')
}

export async function getRouteCheck() {
  return apiRequest('/api/route-check')
}

// ---------------------------------------------------------
// STUDENTS
// ---------------------------------------------------------

export async function getStudents({
  limit = 100,
  offset = 0,
  activeOnly = false,
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    active_only: String(activeOnly),
  })

  return apiRequest(`/api/students/?${params.toString()}`)
}

export async function getStudentById(studentId) {
  return apiRequest(
    `/api/students/${encodeURIComponent(studentId)}`
  )
}

export async function getStudentByRollNo(rollNo) {
  return apiRequest(
    `/api/students/roll-no/${encodeURIComponent(rollNo)}`
  )
}

export async function registerStudent(studentData) {
  return apiRequest('/api/students/', {
    method: 'POST',
    body: JSON.stringify(studentData),
  })
}

export async function updateStudent(studentId, studentData) {
  return apiRequest(
    `/api/students/${encodeURIComponent(studentId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(studentData),
    }
  )
}

export async function updateStudentStatus(studentId, isActive) {
  return apiRequest(
    `/api/students/${encodeURIComponent(studentId)}/status`,
    {
      method: 'PATCH',
      body: JSON.stringify({
        is_active: isActive,
      }),
    }
  )
}

// ---------------------------------------------------------
// STUDENT FACE ENROLLMENT
// ---------------------------------------------------------

export async function enrollStudent({
  name,
  roll_no,
  branch,
  role = 'student',
  year_of_study,
  source_type = 'id_card',
  image,
}) {
  if (!name?.trim()) {
    throw new Error('Name is required.')
  }

  if (!roll_no?.trim()) {
    throw new Error('Roll number / ID is required.')
  }

  if (!branch?.trim()) {
    throw new Error('Branch / Department is required.')
  }

  if (name.trim().length > 150) {
    throw new Error('Name must not exceed 150 characters.')
  }

  if (roll_no.trim().length > 50) {
    throw new Error('Roll number / ID must not exceed 50 characters.')
  }

  if (branch.trim().length > 100) {
    throw new Error('Branch / Department must not exceed 100 characters.')
  }

  const normalizedRole = (role || 'student').trim().toLowerCase()

  if (!['student', 'faculty', 'staff', 'admin'].includes(normalizedRole)) {
    throw new Error('Invalid role specified.')
  }

  if (!['id_card', 'face'].includes(source_type)) {
    throw new Error('Invalid enrollment source type.')
  }

  if (normalizedRole === 'student') {
    if (
      year_of_study === '' ||
      year_of_study === null ||
      year_of_study === undefined
    ) {
      throw new Error('Year of study is required for students.')
    }

    const year = Number(year_of_study)

    if (!Number.isInteger(year) || year < 1 || year > 4) {
      throw new Error('Year of study must be between 1 and 4.')
    }
  }

  if (!(image instanceof File)) {
    throw new Error('Please select or capture an image.')
  }

  const allowedTypes = [
    'image/jpeg',
    'image/png',
    'image/webp',
  ]

  if (!allowedTypes.includes(image.type)) {
    throw new Error('Only JPEG, PNG, and WebP images are supported.')
  }

  if (image.size === 0) {
    throw new Error('The selected image is empty.')
  }

  if (image.size > 5 * 1024 * 1024) {
    throw new Error('Image size must not exceed 5 MB.')
  }

  const formData = new FormData()

  formData.append('name', name.trim())
  formData.append('roll_no', roll_no.trim())
  formData.append('branch', branch.trim())
  formData.append('role', normalizedRole)
  formData.append('source_type', source_type)
  formData.append('image', image, image.name || 'enrollment-image.jpg')

  if (
    normalizedRole === 'student' &&
    year_of_study !== '' &&
    year_of_study !== null &&
    year_of_study !== undefined
  ) {
    formData.append('year_of_study', String(year_of_study))
  }

  return apiRequest('/api/enrollment/students', {
    method: 'POST',
    body: formData,
  })
}

// ---------------------------------------------------------
// DASHBOARD
// ---------------------------------------------------------

export async function getDashboardSummary() {
  return apiRequest('/api/dashboard/summary')
}

export async function getDashboardActivity(days = 7) {
  const safeDays = Math.max(
    1,
    Math.min(365, Number(days) || 7)
  )

  return apiRequest(
    `/api/dashboard/activity?days=${safeDays}`
  )
}

// ---------------------------------------------------------
// RECOGNITION HISTORY
// ---------------------------------------------------------

export async function getRecognitionHistory({
  startDate = '',
  endDate = '',
  search = '',
  studentId = '',
  limit = 20,
  offset = 0,
} = {}) {
  const params = new URLSearchParams()

  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  if (search) params.set('search', search)
  if (studentId) params.set('student_id', studentId)

  params.set('limit', String(limit))
  params.set('offset', String(offset))

  return apiRequest(
    `/api/history/events?${params.toString()}`
  )
}

export async function getRecognitionHistorySummary() {
  return apiRequest('/api/history/summary')
}

// ---------------------------------------------------------
// SYSTEM MONITORING
// ---------------------------------------------------------

export async function getSystemMonitoring() {
  return apiRequest('/api/monitoring/status')
}

// ---------------------------------------------------------
// EXPORT
// ---------------------------------------------------------

export { API_BASE_URL }