import React, { useState, useEffect } from "react";
import api from "./api";
import {
  Activity,
  Layers,
  Cpu,
  Database,
  CheckCircle2,
  Clock,
  LogOut,
  Shield,
  User as UserIcon,
  Play,
  RefreshCw,
  Plus,
  Terminal,
  Zap,
  ArrowRight,
  Sparkles,
  Server
} from "lucide-react";

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("nexus_access_token") || null);
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [authMode, setAuthMode] = useState("login"); // "login" | "register"

  const [authForm, setAuthForm] = useState({
    username: "",
    email: "",
    password: "",
    full_name: "",
  });

  const [newProject, setNewProject] = useState({ title: "", description: "" });
  const [recordCount, setRecordCount] = useState(10000);
  const [activeTask, setActiveTask] = useState(null);
  const [taskResult, setTaskResult] = useState(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    if (token) {
      fetchUserData();
      fetchProjects();
    }
  }, [token]);

  const fetchUserData = async () => {
    try {
      const res = await api.get("/users/me");
      setUser(res.data);
    } catch (err) {
      handleLogout();
    }
  };

  const fetchProjects = async () => {
    try {
      const res = await api.get("/projects/?page=1&size=20");
      setProjects(res.data.items || []);
    } catch (err) {
      console.error("Failed to load projects", err);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (authMode === "register") {
        if (authForm.password.length < 8) {
          alert("Validation Error: Password must be at least 8 characters long.");
          setLoading(false);
          return;
        }

        await api.post("/auth/register", {
          email: authForm.email,
          username: authForm.username,
          full_name: authForm.full_name || null,
          password: authForm.password,
          role: "developer",
        });
        alert("Account registered successfully! Signing in...");
      }

      const loginRes = await api.post("/auth/login", {
        username_or_email: authForm.username || authForm.email,
        password: authForm.password,
      });

      const accessToken = loginRes.data.access_token;
      localStorage.setItem("nexus_access_token", accessToken);
      setToken(accessToken);
    } catch (err) {
      if (err.response?.status === 422) {
        const errorData = err.response.data;
        let msg = "Validation Error:";
        if (errorData.details && Array.isArray(errorData.details)) {
          msg += "\n" + errorData.details.map((d) => `• ${d.loc[d.loc.length - 1]}: ${d.msg}`).join("\n");
        } else {
          msg += "\n" + JSON.stringify(errorData);
        }
        alert(msg);
      } else {
        alert(err.response?.data?.detail || "Authentication request failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("nexus_access_token");
    setToken(null);
    setUser(null);
    setProjects([]);
    setActiveTask(null);
    setTaskResult(null);
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProject.title.trim()) return;
    try {
      await api.post("/projects/", newProject);
      setNewProject({ title: "", description: "" });
      fetchProjects();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to create project");
    }
  };

  const triggerCeleryAnalytics = async () => {
    try {
      setPolling(true);
      const res = await api.post("/tasks/run-analytics", { record_count: Number(recordCount) });
      setActiveTask(res.data.task_id);
      setTaskResult({ status: "ENQUEUED", message: res.data.message });
      pollTaskStatus(res.data.task_id);
    } catch (err) {
      setPolling(false);
      alert(err.response?.data?.detail || "Failed to trigger background task");
    }
  };

  const pollTaskStatus = (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/tasks/status/${taskId}`);
        setTaskResult(res.data);
        if (res.data.status === "SUCCESS" || res.data.status === "FAILURE") {
          setPolling(false);
          clearInterval(interval);
        }
      } catch (err) {
        setPolling(false);
        clearInterval(interval);
      }
    }, 1200);
  };

  // --- Auth View ---
  if (!token) {
    return (
      <div className="relative min-h-screen bg-[#030712] flex items-center justify-center p-4 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/20 rounded-full blur-[128px] pointer-events-none" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-600/20 rounded-full blur-[128px] pointer-events-none" />

        <div className="relative w-full max-w-md bg-gray-900/60 backdrop-blur-xl border border-gray-800/80 p-8 rounded-2xl shadow-2xl shadow-black/80">
          <div className="flex items-center gap-3 mb-8">
            <div className="p-3 bg-gradient-to-tr from-blue-600 to-cyan-500 rounded-xl text-white shadow-lg shadow-blue-500/30">
              <Cpu size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-white">Nexus Core</h1>
                <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-mono font-medium">v1.0</span>
              </div>
              <p className="text-xs text-gray-400 font-medium mt-0.5">High-Performance Asynchronous Control</p>
            </div>
          </div>

          <form onSubmit={handleAuth} className="space-y-4">
            {authMode === "register" && (
              <>
                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1.5">Full Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Turing"
                    className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-3.5 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                    value={authForm.full_name}
                    onChange={(e) => setAuthForm({ ...authForm, full_name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1.5">Email Address</label>
                  <input
                    type="email"
                    required
                    placeholder="alex@nexuscore.io"
                    className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-3.5 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                    value={authForm.email}
                    onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                  />
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                {authMode === "register" ? "Username (min 3 chars)" : "Username or Email"}
              </label>
              <input
                type="text"
                required
                placeholder="nexusdev"
                className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-3.5 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                value={authForm.username}
                onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                Password {authMode === "register" && "(min 8 chars)"}
              </label>
              <input
                type="password"
                required
                placeholder="••••••••••••"
                className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-3.5 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold rounded-xl text-sm transition shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 group disabled:opacity-50"
            >
              <span>{loading ? "Authenticating..." : authMode === "login" ? "Enter Dashboard" : "Register Credentials"}</span>
              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition" />
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-800/80 text-center">
            <button
              onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}
              className="text-xs text-gray-400 hover:text-cyan-400 font-medium transition"
            >
              {authMode === "login" ? "Need a platform account? Create one" : "Existing operator? Sign In"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // --- Main Dashboard ---
  return (
    <div className="min-h-screen bg-[#030712] text-gray-100 flex flex-col antialiased">
      {/* Top Header */}
      <header className="sticky top-0 z-50 bg-gray-950/70 backdrop-blur-xl border-b border-gray-800/80 px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-blue-600 to-cyan-500 rounded-lg text-white shadow-md shadow-blue-500/20">
            <Cpu size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-tight text-white">Nexus Core Control</span>
              <span className="inline-flex items-center gap-1 text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Live Engine
              </span>
            </div>
          </div>
        </div>

        {user && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2.5 bg-gray-900/90 px-3 py-1.5 rounded-xl border border-gray-800">
              <Shield size={14} className="text-cyan-400" />
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-cyan-300">{user.role}</span>
              <span className="text-gray-700">|</span>
              <UserIcon size={14} className="text-gray-400" />
              <span className="text-xs font-medium text-gray-200">{user.username}</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 px-3 py-1.5 rounded-xl font-medium transition"
            >
              <LogOut size={14} />
              Logout
            </button>
          </div>
        )}
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Projects Management */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-gray-900/50 backdrop-blur border border-gray-800/80 rounded-2xl p-6 shadow-xl relative overflow-hidden">
            <div className="flex items-center gap-2 mb-4">
              <Layers size={18} className="text-blue-400" />
              <h2 className="text-sm font-semibold text-white">Create Relational Resource</h2>
            </div>
            <form onSubmit={handleCreateProject} className="space-y-3">
              <input
                type="text"
                placeholder="Cluster / Service Title (e.g. Distributed Analytics Hub)"
                className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
                value={newProject.title}
                onChange={(e) => setNewProject({ ...newProject, title: e.target.value })}
              />
              <textarea
                placeholder="Architecture description, workload limits, or endpoints..."
                rows={2}
                className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
                value={newProject.description}
                onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
              />
              <button
                type="submit"
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-2 shadow-lg shadow-blue-600/20"
              >
                <Plus size={14} />
                Persist Resource
              </button>
            </form>
          </div>

          <div className="bg-gray-900/50 backdrop-blur border border-gray-800/80 rounded-2xl p-6 shadow-xl">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Database size={18} className="text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">Managed Workloads ({projects.length})</h3>
              </div>
              <button
                onClick={fetchProjects}
                className="p-1.5 text-gray-400 hover:text-white bg-gray-800/50 hover:bg-gray-800 rounded-lg transition"
              >
                <RefreshCw size={14} />
              </button>
            </div>

            {projects.length === 0 ? (
              <div className="text-center py-10 border border-dashed border-gray-800 rounded-xl text-xs text-gray-500 font-medium">
                No active workloads found. Deploy one using the form above.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {projects.map((p) => (
                  <div key={p.id} className="p-4 bg-gray-950/60 border border-gray-800/90 rounded-xl flex flex-col justify-between hover:border-gray-700 transition">
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="text-sm font-semibold text-gray-100">{p.title}</h4>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono uppercase">
                          {p.status}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 line-clamp-2 mt-1">{p.description || "No specifications defined."}</p>
                    </div>
                    <div className="mt-4 pt-3 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-gray-500 font-mono">
                      <span>ID: {p.id.slice(0, 8)}...</span>
                      <span>{new Date(p.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Col: Async Celery Task Executor */}
        <div className="space-y-6">
          <div className="bg-gray-900/50 backdrop-blur border border-gray-800/80 rounded-2xl p-6 shadow-xl">
            <div className="flex items-center gap-2 mb-2">
              <Zap size={18} className="text-amber-400" />
              <h3 className="text-sm font-semibold text-white">Celery Async Task Engine</h3>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed mb-5">
              Dispatches background batch jobs directly into Redis without blocking FastAPI request threads.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-300 mb-1.5">Batch Simulation Volume</label>
                <input
                  type="number"
                  min="500"
                  max="50000"
                  value={recordCount}
                  onChange={(e) => setRecordCount(e.target.value)}
                  className="w-full bg-gray-950/70 border border-gray-800 rounded-xl px-4 py-2.5 text-sm font-mono text-amber-300 focus:outline-none focus:border-amber-400 transition"
                />
              </div>

              <button
                onClick={triggerCeleryAnalytics}
                disabled={polling}
                className="w-full py-3 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-gray-950 font-bold rounded-xl text-xs transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <Play size={14} fill="currentColor" />
                {polling ? "Worker Processing..." : "Dispatch Celery Task"}
              </button>
            </div>

            {/* Live Polling Terminal */}
            {taskResult && (
              <div className="mt-6 bg-black/60 border border-gray-800 rounded-xl p-4 font-mono text-xs space-y-2">
                <div className="flex items-center justify-between pb-2 border-b border-gray-800 text-gray-400">
                  <span className="flex items-center gap-1.5 text-[11px]">
                    <Terminal size={12} /> Execution Monitor
                  </span>
                  <span className={`text-[11px] font-semibold flex items-center gap-1 ${
                    taskResult.status === "SUCCESS" ? "text-emerald-400" : "text-amber-400"
                  }`}>
                    {taskResult.status === "SUCCESS" ? <CheckCircle2 size={12} /> : <Clock size={12} className="animate-spin" />}
                    {taskResult.status}
                  </span>
                </div>

                <div className="text-[11px] text-gray-400">
                  <span className="text-gray-600">Task: </span>{activeTask}
                </div>

                {taskResult.result && (
                  <pre className="mt-2 text-[11px] text-emerald-400 overflow-x-auto bg-gray-950/80 p-2.5 rounded-lg border border-emerald-500/20">
                    {JSON.stringify(taskResult.result, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}