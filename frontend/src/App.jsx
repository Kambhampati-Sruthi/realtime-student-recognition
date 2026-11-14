
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import Students from './pages/Students'
import LiveRecognition from './pages/LiveRecognition'


function ModulePage({ title, description }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900 p-8">
      <p className="text-sm text-blue-400">Application module</p>

      <h2 className="mt-2 text-2xl font-bold text-white">
        {title}
      </h2>

      <p className="mt-3 text-sm text-slate-400">
        {description}
      </p>

      <div className="mt-8 rounded-lg border border-dashed border-slate-700 p-8 text-center">
        <p className="font-medium text-slate-300">
          Module foundation created
        </p>

        <p className="mt-2 text-sm text-slate-500">
          Full functionality will be implemented in subsequent milestones.
        </p>
      </div>
    </section>
  )
}


export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>

          <Route
            index
            element={<Dashboard />}
          />

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
            element={
              <ModulePage
                title="Recognition History"
                description="Review recognition events, sessions and timestamps."
              />
            }
          />

          <Route
            path="monitoring"
            element={
              <ModulePage
                title="System Monitoring"
                description="Monitor backend, models, camera connections and inference performance."
              />
            }
          />

        </Route>
      </Routes>
    </BrowserRouter>
  )
}
