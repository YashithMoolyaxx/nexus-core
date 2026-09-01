import React, { useState, useEffect, useRef } from "react";
import api from "./api";
import {
  Layers,
  Cpu,
  LogOut,
  Shield,
  User as UserIcon,
  Play,
  Plus,
  Terminal,
  Zap,
  ArrowRight,
  FileText,
  Radio,
  AlertTriangle,
  Save,
  GitCommit,
  CheckCircle2,
  Clock,
  Building2,
  Server,
  Check,
  ArrowLeftRight,
  Lock
} from "lucide-react";

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("nexus_access_token") || null);
  const [user, setUser] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [activeUsers, setActiveUsers] = useState([]);
  const [conflictModal, setConflictModal] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [wsStatus, setWsStatus] = useState("DISCONNECTED");
  const [loading, setLoading] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [errorMessage, setErrorMessage] = useState("");

  const [authForm, setAuthForm] = useState({
    username: "",
    email: "",
    password: "",
    full_name: "",
    role: "developer",
  });

  const [newDocTitle, setNewDocTitle] = useState("");
  const [editorContent, setEditorContent] = useState("");
  const [editorTitle, setEditorTitle] = useState("");
  const [recordCount, setRecordCount] = useState(15000);
  const [taskResult, setTaskResult] = useState(null);
  const [polling, setPolling] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const socketRef = useRef(null);

  useEffect(() => {
    if (token) {
      fetchUserData();
      fetchTenants();
      fetchDocuments();
      fetchTelemetry();
      initWebSocket();
      const interval = setInterval(fetchTelemetry, 6000);
      return () => clearInterval(interval);
    }
    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, [token]);

  const addAuditLog = (action, detail) => {
    const timestamp = new Date().toLocaleTimeString();
    setAuditLogs((prev) => [{ timestamp, action, detail }, ...prev.slice(0, 19)]);
  };

  const initWebSocket = () => {
    if (socketRef.current) socketRef.current.close();
    setWsStatus("CONNECTING");

    const wsUrl = `ws://localhost:8000/api/v1/ws/workspace?token=${token}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setWsStatus("CONNECTED");
      addAuditLog("WS_CONNECTED", "Established persistent Redis Pub/Sub bridge");
    };

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      if (payload.event === "PRESENCE_SYNC") {
        setActiveUsers(payload.data.active_users || []);
      }

      if (payload.event === "DOCUMENT_CREATED") {
        setDocuments((prev) => [payload.data, ...prev.filter((d) => d.id !== payload.data.id)]);
        addAuditLog("PUB_SUB_DISPATCH", `New RLS Document: "${payload.data.title}"`);
      }

      if (payload.event === "DOCUMENT_UPDATED") {
        const updated = payload.data;
        setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
        addAuditLog("PUB_SUB_SYNC", `Doc "${updated.title}" mutated to v${updated.version}`);

        setSelectedDoc((curr) => {
          if (curr && curr.id === updated.id) {
            setEditorTitle(updated.title);
            setEditorContent(updated.content);
            return updated;
          }
          return curr;
        });
      }
    };

    ws.onclose = () => setWsStatus("DISCONNECTED");

    const heartbeatTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "HEARTBEAT" }));
      }
    }, 10000);

    ws.onclose = () => clearInterval(heartbeatTimer);
  };

  const fetchUserData = async () => {
    try {
      const res = await api.get("/users/me");
      setUser(res.data);
    } catch {
      handleLogout();
    }
  };

  const fetchTenants = async () => {
    try {
      const res = await api.get("/auth/tenants");
      setTenants(res.data);
    } catch (err) {
      console.error("Failed to load tenants", err);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await api.get("/documents/");
      setDocuments(res.data);
      if (res.data.length > 0) {
        selectDocument(res.data[0]);
      } else {
        setSelectedDoc(null);
      }
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  const fetchTelemetry = async () => {
    try {
      const res = await api.get("/metrics/system-telemetry");
      setTelemetry(res.data);
    } catch (err) {
      console.error("Telemetry failed", err);
    }
  };

  const handleSwitchTenant = async (tenantId) => {
    try {
      await api.post(`/auth/switch-tenant/${tenantId}`);
      addAuditLog("RLS_TENANT_SWITCH", `Active isolation context switched to Tenant: ${tenantId}`);
      await fetchUserData();
      await fetchDocuments();
      initWebSocket();
    } catch (err) {
      alert("Failed to switch tenant scope.");
    }
  };

  const selectDocument = (doc) => {
    setSelectedDoc(doc);
    setEditorTitle(doc.title);
    setEditorContent(doc.content);
    setConflictModal(null);
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage("");

    try {
      if (authMode === "register") {
        if (authForm.password.length < 8) {
          setErrorMessage("Password must be at least 8 characters long.");
          setLoading(false);
          return;
        }

        await api.post("/auth/register", {
          email: authForm.email.trim(),
          username: authForm.username.trim(),
          full_name: authForm.full_name.trim() || null,
          password: authForm.password,
          role: authForm.role,
        });
      }

      const loginRes = await api.post("/auth/login", {
        username_or_email: authForm.username.trim() || authForm.email.trim(),
        password: authForm.password,
      });

      const accessToken = loginRes.data.access_token;
      localStorage.setItem("nexus_access_token", accessToken);
      setToken(accessToken);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setErrorMessage(typeof detail === "string" ? detail : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("nexus_access_token");
    setToken(null);
    setUser(null);
    setDocuments([]);
    setSelectedDoc(null);
    setActiveUsers([]);
  };

  const handleCreateDocument = async (e) => {
    e.preventDefault();
    if (!newDocTitle.trim()) return;
    try {
      const res = await api.post("/documents/", {
        title: newDocTitle.trim(),
        content: "# Architectural Specification\n\nIsolate under PostgreSQL Row Level Security.",
      });
      setNewDocTitle("");
      selectDocument(res.data);
      addAuditLog("DOC_CREATED", `Created RLS Document ID: ${res.data.id}`);
    } catch (err) {
      if (err.response?.status === 403) {
        alert(err.response.data.detail);
        addAuditLog("RBAC_DENIED", "Create Document rejected: Viewer role does not possess write privileges.");
      } else {
        alert(err.response?.data?.detail || "Failed to create document.");
      }
    }
  };

  const handleSaveDocument = async (overrideVersion = null) => {
    if (!selectedDoc) return;
    setIsSaving(true);
    try {
      const res = await api.put(`/documents/${selectedDoc.id}`, {
        title: editorTitle,
        content: editorContent,
        version: overrideVersion !== null ? overrideVersion : selectedDoc.version,
      });
      setSelectedDoc(res.data);
      setConflictModal(null);
      addAuditLog("OCC_COMMIT", `Committed state increment -> v${res.data.version}`);
    } catch (err) {
      if (err.response?.status === 409) {
        const serverDoc = (await api.get(`/documents/${selectedDoc.id}`)).data;
        setConflictModal({
          serverVersion: serverDoc.version,
          serverContent: serverDoc.content,
          serverTitle: serverDoc.title,
          localContent: editorContent,
          localTitle: editorTitle,
        });
        addAuditLog("OCC_409_COLLISION", `Concurrent race collision (Local: v${selectedDoc.version} vs Server: v${serverDoc.version})`);
      } else if (err.response?.status === 403) {
        alert(err.response.data.detail);
        addAuditLog("RBAC_DENIED", "Commit rejected: Viewer role is read-only.");
      } else {
        alert(err.response?.data?.detail || "Save failed.");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const triggerCeleryAnalytics = async () => {
    try {
      setPolling(true);
      setTaskResult({ status: "ENQUEUED" });
      const res = await api.post("/tasks/run-analytics", { record_count: Number(recordCount) });
      addAuditLog("CELERY_TASK_ENQUEUED", `Job ID: ${res.data.task_id} (${recordCount.toLocaleString()} records)`);
      pollTaskStatus(res.data.task_id);
    } catch (err) {
      setPolling(false);
      if (err.response?.status === 403) {
        alert(err.response.data.detail);
        addAuditLog("RBAC_DENIED", "Compute batch rejected: Only Administrators can trigger Celery compute.");
      }
    }
  };

  const pollTaskStatus = (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/tasks/status/${taskId}`);
        setTaskResult(res.data);
        if (res.data.status === "SUCCESS" || res.data.status === "FAILURE") {
          setPolling(false);
          addAuditLog("CELERY_TASK_FINISHED", `Job ${taskId} -> ${res.data.status}`);
          clearInterval(interval);
        }
      } catch {
        setPolling(false);
        clearInterval(interval);
      }
    }, 1000);
  };

  const isViewer = user?.role === "viewer";
  const isAdmin = user?.role === "admin";

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-rose-50 flex items-center justify-center p-4 text-purple-950">
        <div className="w-full max-w-md bg-white/85 backdrop-blur-xl border border-purple-200 p-8 rounded-3xl shadow-xl shadow-purple-900/5">
          <div className="flex items-center gap-3.5 mb-6">
            <div className="p-3 bg-gradient-to-tr from-purple-600 via-pink-500 to-rose-400 rounded-2xl text-white shadow-md shadow-pink-500/20">
              <Cpu size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-purple-900 via-pink-800 to-rose-900 bg-clip-text text-transparent">
                  Nexus Core
                </h1>
                <span className="text-[10px] font-mono bg-purple-100 text-purple-700 border border-purple-200 px-2 py-0.5 rounded-full font-bold">
                  v2.0
                </span>
              </div>
              <p className="text-xs text-purple-700/70 font-medium">Distributed State & RBAC Collaboration Mesh</p>
            </div>
          </div>

          {errorMessage && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
              <AlertTriangle size={15} className="shrink-0 text-rose-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleAuth} className="space-y-3.5">
            {authMode === "register" && (
              <>
                <div>
                  <label className="block text-xs font-semibold text-purple-900 mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Alex Turing"
                    className="w-full bg-purple-50/50 border border-purple-200 rounded-xl px-3.5 py-2 text-sm text-purple-950 placeholder-purple-300 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition"
                    value={authForm.full_name}
                    onChange={(e) => setAuthForm({ ...authForm, full_name: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-purple-900 mb-1">Email Address</label>
                  <input
                    type="email"
                    required
                    placeholder="alex@nexuscore.io"
                    className="w-full bg-purple-50/50 border border-purple-200 rounded-xl px-3.5 py-2 text-sm text-purple-950 placeholder-purple-300 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition"
                    value={authForm.email}
                    onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-purple-900 mb-1">Assigned RBAC Privilege</label>
                  <select
                    className="w-full bg-purple-50/70 border border-purple-200 rounded-xl px-3.5 py-2 text-xs font-semibold text-purple-950 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition cursor-pointer"
                    value={authForm.role}
                    onChange={(e) => setAuthForm({ ...authForm, role: e.target.value })}
                  >
                    <option value="developer">Developer — Read/Write Docs, OCC Commits</option>
                    <option value="admin">Administrator — Full Access + Celery Batch Compute</option>
                    <option value="viewer">Viewer — Read-Only Workspace Observation</option>
                  </select>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-semibold text-purple-900 mb-1">
                {authMode === "register" ? "Username" : "Username or Email"}
              </label>
              <input
                type="text"
                required
                placeholder={authMode === "register" ? "alexdev" : "username or email"}
                className="w-full bg-purple-50/50 border border-purple-200 rounded-xl px-3.5 py-2 text-sm text-purple-950 placeholder-purple-300 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition"
                value={authForm.username}
                onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-purple-900 mb-1">Password</label>
              <input
                type="password"
                required
                placeholder="••••••••••••"
                className="w-full bg-purple-50/50 border border-purple-200 rounded-xl px-3.5 py-2 text-sm text-purple-950 placeholder-purple-300 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-gradient-to-r from-purple-600 via-pink-600 to-rose-500 hover:from-purple-500 hover:via-pink-500 hover:to-rose-400 text-white font-bold rounded-xl text-sm transition shadow-lg shadow-pink-500/20 flex items-center justify-center gap-2 disabled:opacity-50 mt-2 cursor-pointer"
            >
              <span>{loading ? "Authenticating..." : authMode === "login" ? "Enter Workspace" : "Provision Account"}</span>
              <ArrowRight size={16} />
            </button>
          </form>

          <div className="mt-5 pt-4 border-t border-purple-100 text-center">
            <button
              onClick={() => {
                setAuthMode(authMode === "login" ? "register" : "login");
                setErrorMessage("");
              }}
              className="text-xs text-purple-700 hover:text-pink-600 font-medium transition cursor-pointer"
            >
              {authMode === "login" ? "Need a new account? Register with Role" : "Already provisioned? Sign In"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#faf5ff] via-[#fdf4f8] to-[#fff1f2] text-purple-950 flex flex-col antialiased">
      {conflictModal && (
        <div className="fixed inset-0 z-50 bg-purple-950/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-white border-2 border-rose-300 rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <AlertTriangle size={24} />
              <div>
                <h3 className="font-extrabold text-base text-rose-900">
                  Optimistic Concurrency Conflict (HTTP 409)
                </h3>
                <p className="text-xs text-rose-700">
                  Another operator committed changes while you were editing. Choose how to resolve this collision:
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-purple-50/70 p-3 rounded-2xl border border-purple-200">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold text-purple-900">Your Local Version</span>
                  <span className="text-[10px] font-mono bg-purple-200 px-1.5 rounded">v{selectedDoc.version}</span>
                </div>
                <pre className="text-[11px] font-mono text-purple-900 bg-white p-2.5 rounded-xl border border-purple-100 h-36 overflow-y-auto">
                  {conflictModal.localContent}
                </pre>
              </div>

              <div className="bg-rose-50/70 p-3 rounded-2xl border border-rose-200">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold text-rose-900">Committed Server State</span>
                  <span className="text-[10px] font-mono bg-rose-200 px-1.5 rounded">v{conflictModal.serverVersion}</span>
                </div>
                <pre className="text-[11px] font-mono text-rose-900 bg-white p-2.5 rounded-xl border border-rose-100 h-36 overflow-y-auto">
                  {conflictModal.serverContent}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                onClick={() => {
                  setEditorContent(conflictModal.serverContent);
                  setEditorTitle(conflictModal.serverTitle);
                  setSelectedDoc((d) => ({ ...d, version: conflictModal.serverVersion }));
                  setConflictModal(null);
                  addAuditLog("CONFLICT_RESOLVED", "Accepted incoming server version");
                }}
                className="px-4 py-2 bg-purple-100 hover:bg-purple-200 text-purple-900 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer"
              >
                <Check size={14} /> Accept Server Version (v{conflictModal.serverVersion})
              </button>
              <button
                onClick={() => handleSaveDocument(conflictModal.serverVersion)}
                className="px-4 py-2 bg-gradient-to-r from-rose-600 to-pink-600 text-white rounded-xl text-xs font-bold transition shadow-md shadow-pink-500/20 flex items-center gap-1.5 cursor-pointer"
              >
                <ArrowLeftRight size={14} /> Force Overwrite & Increment
              </button>
            </div>
          </div>
        </div>
      )}

      <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-xl border-b border-purple-200/70 px-8 py-3.5 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-gradient-to-tr from-purple-600 via-pink-500 to-rose-400 rounded-xl text-white shadow-md shadow-pink-500/10">
            <Cpu size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm tracking-tight bg-gradient-to-r from-purple-900 to-pink-900 bg-clip-text text-transparent">
                Nexus Core Mesh
              </span>
              <span className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                wsStatus === "CONNECTED"
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                  : "bg-amber-100 text-amber-800 border border-amber-300"
              }`}>
                <Radio size={10} className={wsStatus === "CONNECTED" ? "animate-pulse" : ""} />
                WS: {wsStatus}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 bg-purple-50/80 border border-purple-200 px-3 py-1 rounded-xl">
            <Building2 size={13} className="text-purple-600" />
            <span className="text-xs font-semibold text-purple-900">RLS Tenant:</span>
            <select
              className="bg-transparent text-xs font-mono font-bold text-purple-950 focus:outline-none cursor-pointer"
              value={user?.tenant_id || ""}
              onChange={(e) => handleSwitchTenant(e.target.value)}
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id} className="bg-white text-purple-950">
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-pink-50/80 border border-pink-200/80 px-3.5 py-1.5 rounded-xl">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold text-pink-900">Active Operators:</span>
            <div className="flex items-center gap-1.5 ml-0.5">
              {activeUsers.map((u) => (
                <span
                  key={u.user_id}
                  className="text-[11px] bg-white text-purple-900 border border-pink-200 px-2 py-0.5 rounded-md font-mono font-bold shadow-xs"
                >
                  {u.username}
                </span>
              ))}
            </div>
          </div>

          {user && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 bg-purple-50/80 border border-purple-200/80 px-3.5 py-1.5 rounded-xl">
                <Shield
                  size={14}
                  className={
                    isAdmin ? "text-amber-500" : isViewer ? "text-slate-400" : "text-purple-600"
                  }
                />
                <span
                  className={`text-xs font-mono font-extrabold uppercase px-1.5 py-0.5 rounded ${
                    isAdmin
                      ? "bg-amber-100 text-amber-800"
                      : isViewer
                      ? "bg-slate-100 text-slate-700"
                      : "bg-purple-100 text-purple-800"
                  }`}
                >
                  {user.role}
                </span>
                <span className="text-purple-300">|</span>
                <UserIcon size={14} className="text-purple-400" />
                <span className="text-xs font-semibold text-purple-950">{user.username}</span>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-xs text-rose-700 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 border border-rose-200 px-3 py-1.5 rounded-xl font-semibold transition cursor-pointer"
              >
                <LogOut size={14} />
                Logout
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white/85 backdrop-blur-md border border-purple-200/70 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Layers size={16} className="text-purple-600" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-purple-900">Tenant Docs (RLS)</h2>
              </div>
              <span className="text-[10px] font-mono bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-bold">
                Count: {documents.length}
              </span>
            </div>

            <form onSubmit={handleCreateDocument} className="space-y-2 mb-4">
              <input
                type="text"
                disabled={isViewer}
                placeholder={isViewer ? "Viewers cannot create docs" : "New doc title..."}
                className="w-full bg-purple-50/40 border border-purple-200 rounded-xl px-3 py-2 text-xs text-purple-950 placeholder-purple-300 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition disabled:opacity-50"
                value={newDocTitle}
                onChange={(e) => setNewDocTitle(e.target.value)}
              />
              <button
                type="submit"
                disabled={isViewer}
                className="w-full py-2 bg-gradient-to-r from-purple-600 via-pink-600 to-rose-500 hover:from-purple-500 hover:via-pink-500 hover:to-rose-400 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 shadow-md shadow-pink-500/15 transition cursor-pointer disabled:opacity-40"
              >
                {isViewer ? <Lock size={14} /> : <Plus size={14} />}
                {isViewer ? "Read-Only (Viewer)" : "Create RLS Document"}
              </button>
            </form>

            <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
              {documents.length === 0 ? (
                <div className="text-center py-6 text-xs text-purple-400 border border-dashed border-purple-200 rounded-xl">
                  No documents in this RLS tenant.
                </div>
              ) : (
                documents.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => selectDocument(doc)}
                    className={`w-full text-left p-2.5 rounded-xl text-xs transition flex items-center justify-between border cursor-pointer ${
                      selectedDoc?.id === doc.id
                        ? "bg-purple-100 border-purple-300 text-purple-950 font-bold shadow-xs"
                        : "bg-white/70 border-transparent text-purple-800 hover:bg-purple-50 hover:border-purple-200"
                    }`}
                  >
                    <div className="truncate font-semibold">{doc.title}</div>
                    <span className="text-[10px] font-mono bg-white text-pink-700 border border-purple-200 px-1.5 py-0.5 rounded font-bold shadow-xs ml-2">
                      v{doc.version}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>

          {telemetry && (
            <div className="bg-white/85 backdrop-blur-md border border-purple-200/70 rounded-2xl p-4 shadow-sm space-y-3">
              <div className="flex items-center gap-2">
                <Server size={16} className="text-purple-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-purple-900">Cluster Telemetry</h3>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="bg-purple-50/70 p-2 rounded-xl border border-purple-100">
                  <span className="text-purple-400 block text-[9px]">POSTGRES RTT</span>
                  <strong className="text-purple-950">{telemetry.metrics.database_latency_ms} ms</strong>
                </div>
                <div className="bg-pink-50/70 p-2 rounded-xl border border-pink-100">
                  <span className="text-pink-400 block text-[9px]">REDIS CLIENTS</span>
                  <strong className="text-pink-950">{telemetry.metrics.redis_connected_clients} active</strong>
                </div>
                <div className="bg-pink-50/70 p-2 rounded-xl border border-pink-100">
                  <span className="text-pink-400 block text-[9px]">PUB/SUB MESH</span>
                  <strong className="text-pink-950">{telemetry.metrics.active_pubsub_channels} channels</strong>
                </div>
                <div className="bg-purple-50/70 p-2 rounded-xl border border-purple-100">
                  <span className="text-purple-400 block text-[9px]">CACHE HIT</span>
                  <strong className="text-purple-950">{telemetry.metrics.cache_hit_ratio}%</strong>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="lg:col-span-2 space-y-4">
          {selectedDoc ? (
            <div className="bg-white/85 backdrop-blur-md border border-purple-200/70 rounded-2xl p-6 shadow-sm flex flex-col h-[740px]">
              <div className="flex items-center justify-between gap-3 mb-4">
                <input
                  type="text"
                  disabled={isViewer}
                  className="flex-1 bg-purple-50/40 border border-purple-200 rounded-xl px-4 py-2.5 text-sm font-bold text-purple-950 focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition disabled:opacity-60"
                  value={editorTitle}
                  onChange={(e) => setEditorTitle(e.target.value)}
                />
                <div className="flex items-center gap-1.5 bg-purple-100/70 border border-purple-200 px-3 py-2 rounded-xl text-xs font-mono font-bold text-purple-900">
                  <GitCommit size={14} className="text-pink-600" />
                  <span>v{selectedDoc.version}</span>
                </div>
                <button
                  onClick={() => handleSaveDocument()}
                  disabled={isSaving || isViewer}
                  className="px-5 py-2.5 bg-gradient-to-r from-purple-600 via-pink-600 to-rose-500 hover:from-purple-500 hover:via-pink-500 hover:to-rose-400 text-white font-bold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-pink-500/20 transition cursor-pointer disabled:opacity-40"
                >
                  {isViewer ? <Lock size={14} /> : <Save size={14} />}
                  {isViewer ? "Read-Only" : isSaving ? "Saving..." : "Atomic Commit"}
                </button>
              </div>

              <textarea
                disabled={isViewer}
                className="flex-1 w-full bg-purple-50/30 border border-purple-200/80 rounded-xl p-4 text-xs font-mono text-purple-950 placeholder-purple-300 resize-none focus:outline-none focus:bg-white focus:ring-2 focus:ring-pink-400/40 focus:border-pink-500 transition leading-relaxed disabled:opacity-60"
                value={editorContent}
                onChange={(e) => setEditorContent(e.target.value)}
                placeholder="Write system architecture specifications..."
              />
            </div>
          ) : (
            <div className="bg-white/60 border border-dashed border-purple-200 rounded-2xl h-[740px] flex flex-col items-center justify-center text-xs text-purple-400 gap-2">
              <FileText size={24} className="text-purple-300" />
              <span>Select or create a document to test real-time RLS collaboration.</span>
            </div>
          )}
        </div>

        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white/85 backdrop-blur-md border border-purple-200/70 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Zap size={16} className="text-amber-500" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-purple-900">Vector Batch Engine</h3>
              </div>
              {!isAdmin && (
                <span className="text-[10px] font-mono bg-rose-100 text-rose-700 px-1.5 py-0.5 rounded font-bold">
                  Admin Only
                </span>
              )}
            </div>
            <p className="text-[11px] text-purple-700/70 mb-3 leading-relaxed">
              Celery task analyzing multi-variate statistical distributions in background worker pools.
            </p>

            <div className="space-y-2.5">
              <input
                type="number"
                disabled={!isAdmin}
                min="1000"
                max="100000"
                value={recordCount}
                onChange={(e) => setRecordCount(e.target.value)}
                className="w-full bg-purple-50/40 border border-purple-200 rounded-xl px-3 py-1.5 text-xs font-mono text-purple-950 focus:outline-none disabled:opacity-50"
              />
              <button
                onClick={triggerCeleryAnalytics}
                disabled={polling || !isAdmin}
                className="w-full py-2 bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-400 hover:to-rose-400 text-white font-bold rounded-xl text-xs transition shadow-md shadow-rose-500/20 flex items-center justify-center gap-1.5 disabled:opacity-40 cursor-pointer"
              >
                {!isAdmin ? <Lock size={12} /> : <Play size={12} fill="currentColor" />}
                {!isAdmin ? "Admin Required" : polling ? "Executing Worker..." : "Dispatch Celery Job"}
              </button>
            </div>

            {taskResult?.result && (
              <div className="mt-3 p-2.5 bg-purple-50/70 border border-purple-200 rounded-xl font-mono text-[10px] space-y-1">
                <div className="flex justify-between">
                  <span className="text-purple-500">Processed:</span>
                  <strong className="text-purple-950">{taskResult.result.processed_records.toLocaleString()}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-purple-500">Duration:</span>
                  <strong className="text-emerald-700">{taskResult.result.execution_time_sec}s</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-purple-500">Throughput:</span>
                  <strong className="text-pink-600">{taskResult.result.throughput_records_per_sec.toLocaleString()} r/s</strong>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white/85 backdrop-blur-md border border-purple-200/70 rounded-2xl p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Terminal size={14} className="text-purple-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-purple-900">Live Event Stream</h3>
            </div>
            <div className="space-y-1.5 max-h-44 overflow-y-auto font-mono text-[10px] pr-1">
              {auditLogs.map((log, idx) => (
                <div key={idx} className="p-1.5 bg-purple-50/60 rounded border border-purple-100 leading-tight">
                  <span className="text-purple-400 mr-1.5">[{log.timestamp}]</span>
                  <span className="font-bold text-pink-700 mr-1">{log.action}:</span>
                  <span className="text-purple-900">{log.detail}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}