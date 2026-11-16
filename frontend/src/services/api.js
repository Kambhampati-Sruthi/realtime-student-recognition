
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

// ---------------------------------------------------------
// COMMON API REQUEST HANDLER
// ---------------------------------------------------------

async function apiRequest(endpoint, options = {}) {
  const isFormData =
    typeof FormData !== 'undefined' &&
    options.body instanceof FormData

  const headers = {
    ...(!isFormData && options.body
      ? { 'Content-Type': 'application/json' }
      : {}),
    ...options.headers,
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  // Handle empty responses safely.
  if (response.status === 204) {
    if (!response.ok) {
      throw new Error(`Backend returned HTTP ${response.status}`)
    }

    return null
  }

  const contentType = response.headers.get('content-type') || ''

  let data

  if (contentType.includes('application/json')) {
    data = await response.json().catch(() => null)
  } else {
    data = await response.text().catch(() => '')
  }

  if (!response.ok) {
    const message =
      typeof data?.detail === 'string'
        ? data.detail
        : typeof data?.message === 'string'
          ? data.message
          : typeof data === 'string' && data
            ? data
            : `Backend returned HTTP ${response.status}`

    throw new Error(message)
  }

  return data
}


// ---------------------------------------------------------
// BACKEND HEALTH
// ---------------------------------------------------------

export async function getBackendHealth() {
  return apiRequest('/health')
}


// ---------------------------------------------------------
// STUDENT MANAGEMENT
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
  year_of_study,
  source_type = 'id_card',
  image,
}) {
  if (!name?.trim()) {
    throw new Error('Student name is required.')
  }

  if (!roll_no?.trim()) {
    throw new Error('Roll number is required.')
  }

  if (!branch?.trim()) {
    throw new Error('Branch is required.')
  }

  if (!image) {
    throw new Error('Student image is required.')
  }

  if (!['id_card', 'face'].includes(source_type)) {
    throw new Error('Invalid enrollment source type.')
  }

  const formData = new FormData()

  formData.append('name', name.trim())
  formData.append('roll_no', roll_no.trim())
  formData.append('branch', branch.trim())
  formData.append('source_type', source_type)
  formData.append('image', image)

  if (year_of_study !== '' && year_of_study != null) {
    formData.append('year_of_study', String(year_of_study))
  }

  // Do not manually set Content-Type.
  // The browser supplies the multipart/form-data boundary.
  //
  // This endpoint matches:
  // backend/app/api/routes/enrollment.py
  //
  // POST /api/enrollment/students

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
  const safeDays = Math.max(1, Math.min(365, Number(days) || 7))

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
