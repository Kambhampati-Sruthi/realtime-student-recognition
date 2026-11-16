import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import Students from './pages/Students'
import LiveRecognition from './pages/LiveRecognition'
import StudentEnrollment from './pages/StudentEnrollment'
import History from './pages/History'
import Monitoring from './pages/Monitoring'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Main application layout */}
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />

          <Route
            path="recognition"
            element={<LiveRecognition />}
          />

          <Route
            path="students"
            element={<Students />}
          />

          <Route
            path="history"
            element={<History />}
          />

          <Route
            path="monitoring"
            element={<Monitoring />}
          />
        </Route>

        {/* Enrollment remains outside the main layout */}
        <Route
          path="/enrollment"
          element={<StudentEnrollment />}
        />
      </Routes>
    </BrowserRouter>
  )
}