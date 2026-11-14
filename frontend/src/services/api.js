
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(
      data?.detail || `Backend returned HTTP ${response.status}`
    )
  }

  return data
}


// Backend health check.
export async function getBackendHealth() {
  return apiRequest('/health')
}


// Retrieve all students.
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

  return apiRequest(`/api/students/?${params}`)
}


// Retrieve one student using UUID.
export async function getStudentById(studentId) {
  return apiRequest(`/api/students/${encodeURIComponent(studentId)}`)
}


// Find student using roll number.
export async function getStudentByRollNo(rollNo) {
  return apiRequest(
    `/api/students/roll-no/${encodeURIComponent(rollNo)}`
  )
}


// Register a new student.
export async function registerStudent(studentData) {
  return apiRequest('/api/students/', {
    method: 'POST',
    body: JSON.stringify(studentData),
  })
}


// Update student details.
export async function updateStudent(studentId, studentData) {
  return apiRequest(
    `/api/students/${encodeURIComponent(studentId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(studentData),
    }
  )
}


// Activate or deactivate a student.
export async function updateStudentStatus(studentId, isActive) {
  return apiRequest(
    `/api/students/${encodeURIComponent(studentId)}/status`,
    {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    }
  )
}


export { API_BASE_URL }
