
import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity,
  Clock3,
  LayoutDashboard,
  ScanFace,
  Settings,
  Users,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Live Recognition', path: '/recognition', icon: ScanFace },
  { name: 'Students', path: '/students', icon: Users },
  { name: 'Recognition History', path: '/history', icon: Clock3 },
  { name: 'System Monitoring', path: '/monitoring', icon: Activity },
]

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 md:flex">
      <aside className="flex w-full flex-col border-b border-slate-800 bg-slate-900 md:fixed md:inset-y-0 md:w-64 md:border-b-0 md:border-r">
        <div className="flex items-center gap-3 border-b border-slate-800 px-6 py-5">
          <div className="rounded-xl bg-blue-600 p-2">
            <ScanFace size={23} />
          </div>

          <div>
            <h1 className="text-sm font-bold tracking-wide">VISION ID</h1>
            <p className="text-xs text-slate-400">Recognition System</p>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto p-3 md:flex-1 md:flex-col">
          <p className="hidden px-3 pb-2 pt-4 text-xs font-semibold uppercase tracking-widest text-slate-500 md:block">
            Workspace
          </p>

          {navigation.map(({ name, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-3 rounded-lg px-3 py-3 text-sm transition ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              <span>{name}</span>
            </NavLink>
          ))}
        </nav>

        <div className="hidden border-t border-slate-800 p-4 md:block">
          <div className="rounded-lg bg-slate-800/70 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
              <Settings size={15} />
              AI Recognition Platform
            </div>
            <p className="mt-2 text-xs text-slate-500">
              YOLO11 · DeepFace · ArcFace
            </p>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 md:ml-64">
        <header className="flex min-h-16 items-center justify-between border-b border-slate-800 bg-slate-900/70 px-5 md:px-8">
          <div>
            <p className="text-sm font-semibold">Student Recognition</p>
            <p className="text-xs text-slate-500">
              AI-powered real-time monitoring
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-300">
            <span className="h-2 w-2 rounded-full bg-blue-400" />
            Development
          </div>
        </header>

        <div className="p-5 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
