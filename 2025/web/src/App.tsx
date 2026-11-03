// src/App.tsx
import { Routes, Route, Link, NavLink } from "react-router-dom";
import Home from "@/pages/Home";
import VerifyPhoto from "@/pages/VerifyPhoto"; // ⬅️ 교체: 기존 PhotoVerify 대신
import Result from "@/pages/Result";
import Enroll from "@/pages/Enroll";

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white text-slate-800">
      {/* 헤더 */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur border-b">
        <div className="max-w-screen-xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="text-xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-indigo-600 to-emerald-600 bg-clip-text text-transparent">
              AegisSign
            </span>
          </Link>
          <nav className="flex items-center gap-6 text-sm">
            <NavLink
              to="/"
              className={({ isActive }) =>
                isActive ? "text-slate-900 font-semibold" : "text-slate-600 hover:text-slate-900"
              }
            >
              Home
            </NavLink>

            <NavLink
              to="/enroll"
              className={({ isActive }) =>
                isActive
                  ? "text-slate-900 font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }
            >
              Enroll
            </NavLink>

            <NavLink
              to="/photo"
              className={({ isActive }) =>
                isActive ? "text-slate-900 font-semibold" : "text-slate-600 hover:text-slate-900"
              }
            >
              Verify by Photo
            </NavLink>

            <span className="text-slate-300">/</span>
            <span className="text-slate-400">Verify in Real-Time</span>
          </nav>
        </div>
      </header>

      {/* 페이지 */}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/enroll" element={<Enroll />} />
        <Route path="/photo" element={<VerifyPhoto />} /> {/* ⬅️ 여기만 교체 */}
        <Route path="/result" element={<Result />} />
      </Routes>

      {/* 푸터 */}
      <footer className="border-t mt-16">
        <div className="max-w-screen-xl mx-auto px-6 py-10 text-xs text-slate-500 text-center">
          © {new Date().getFullYear()} AegisSign — K-DS 해커톤 팀 “미운네살”
        </div>
      </footer>
    </div>
  );
}
