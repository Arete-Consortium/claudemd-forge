import { useState, useCallback, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "./AuthContext";
import { getGitHubLoginUrl, createDeepScanCheckout, getDeepScanReport, getFixReport } from "./api";
import ReposPage from "./ReposPage";
import AdminPage from "./AdminPage";

const POLL_INTERVAL = 1500;
const MAX_POLLS = 60;

function ScoreBadge({ score }) {
  let color = "bg-red-500";
  let label = "Poor";
  if (score >= 80) {
    color = "bg-green-500";
    label = "Excellent";
  } else if (score >= 60) {
    color = "bg-anchor-500";
    label = "Good";
  } else if (score >= 40) {
    color = "bg-yellow-500";
    label = "Fair";
  }

  return (
    <span
      className={`${color} text-white text-sm font-bold px-3 py-1 rounded-full inline-flex items-center gap-1.5`}
    >
      {score}/100
      <span className="text-xs font-normal opacity-90">{label}</span>
    </span>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center gap-4 py-12">
      <div className="relative">
        <div className="w-12 h-12 border-4 border-gray-700 border-t-anchor-500 rounded-full animate-spin" />
      </div>
      <div className="text-center">
        <p className="text-gray-300 font-medium">Generating CLAUDE.md...</p>
        <p className="text-gray-500 text-sm mt-1">
          Cloning repo, scanning codebase, analyzing patterns
        </p>
      </div>
    </div>
  );
}

function GitHubIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function PriorityBadge({ priority }) {
  const colors = {
    high: "bg-red-500/20 text-red-400 border-red-500/30",
    medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    low: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  };
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded border ${colors[priority] || colors.low}`}
    >
      {priority.toUpperCase()}
    </span>
  );
}

function DeepScanCTA({ repoUrl, onCheckout }) {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [ctaError, setCtaError] = useState(null);

  const handleCheckout = async () => {
    if (!email.trim()) return;
    setSubmitting(true);
    setCtaError(null);
    try {
      const data = await onCheckout(repoUrl, email.trim());
      window.location.href = data.checkout_url;
    } catch (err) {
      setCtaError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-gradient-to-r from-anchor-900/50 to-anchor-800/30 border border-anchor-700/50 rounded-lg p-6 mt-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex-1">
          <h3 className="text-white font-semibold text-lg mb-1">
            Want deeper analysis?
          </h3>
          <p className="text-gray-400 text-sm">
            Get a full audit report with architecture recommendations, security
            review, and actionable improvements for{" "}
            <span className="text-white font-medium">$29</span> (one-time).
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@email.com"
            className="bg-gray-900 border border-gray-700 rounded-md px-3 py-2 text-white text-sm
                       placeholder-gray-500 focus:outline-none focus:border-anchor-500 w-full sm:w-52"
          />
          <button
            onClick={handleCheckout}
            disabled={submitting || !email.trim()}
            className="bg-anchor-600 hover:bg-anchor-700 disabled:bg-gray-700 disabled:text-gray-500
                       text-white font-semibold px-5 py-2 rounded-md transition-colors text-sm
                       whitespace-nowrap"
          >
            {submitting ? "Redirecting..." : "Get Deep Report"}
          </button>
        </div>
      </div>
      {ctaError && (
        <p className="text-red-400 text-sm mt-2">{ctaError}</p>
      )}
    </div>
  );
}

function DeepScanReportView({ report }) {
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!report?.content) return;
    try {
      await navigator.clipboard.writeText(report.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = report.content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (report.status === "pending" || report.status === "awaiting_payment") {
    return (
      <div className="pt-12">
        <LoadingSpinner />
        <p className="text-center text-gray-400 text-sm mt-4">
          {report.status === "awaiting_payment"
            ? "Waiting for payment confirmation..."
            : "Deep scan in progress..."}
        </p>
      </div>
    );
  }

  if (report.status === "error") {
    return (
      <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 mt-8">
        <p className="text-red-400 text-sm">Deep scan failed: {report.error || "Unknown error"}</p>
      </div>
    );
  }

  return (
    <div className="pb-12 pt-6">
      <div className="flex items-center gap-3 mb-6">
        <span className="bg-anchor-600 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide">
          Deep Scan
        </span>
        <ScoreBadge score={report.score} />
        <span className="text-gray-400 text-sm">
          {report.files_scanned} files scanned
        </span>
      </div>

      {/* Recommendations */}
      {report.recommendations && report.recommendations.length > 0 && (
        <div className="mb-8">
          <h2 className="text-white text-xl font-semibold mb-4">
            Recommendations
          </h2>
          <div className="space-y-3">
            {report.recommendations.map((rec, i) => (
              <div
                key={i}
                className="bg-gray-900 border border-gray-700 rounded-lg p-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <PriorityBadge priority={rec.priority} />
                  <h3 className="text-white font-medium">{rec.title}</h3>
                </div>
                <p className="text-gray-400 text-sm">{rec.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Generated CLAUDE.md */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-white text-xl font-semibold">
            Generated CLAUDE.md
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5
                         border border-gray-700 rounded-md transition-colors"
            >
              {showRaw ? "Preview" : "Raw"}
            </button>
            <button
              onClick={handleCopy}
              className={`text-sm px-4 py-1.5 rounded-md font-medium transition-colors ${
                copied
                  ? "bg-green-600 text-white"
                  : "bg-anchor-600 hover:bg-anchor-700 text-white"
              }`}
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
          {showRaw ? (
            <pre className="p-6 text-sm text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">
              {report.content}
            </pre>
          ) : (
            <div className="p-6 markdown-output">
              <ReactMarkdown>{report.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { user, loading: authLoading, logout } = useAuth();
  const [page, setPage] = useState("home"); // "home" | "repos" | "admin"
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [deepReport, setDeepReport] = useState(null);
  const [deepLoading, setDeepLoading] = useState(false);
  const [fixDownloading, setFixDownloading] = useState(false);

  // Check for ?deep_scan= parameter on load.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const deepScanId = params.get("deep_scan");
    if (deepScanId) {
      setDeepLoading(true);
      const pollDeep = async () => {
        for (let i = 0; i < MAX_POLLS; i++) {
          try {
            const data = await getDeepScanReport(deepScanId);
            if (data.status === "complete" || data.status === "error") {
              setDeepReport(data);
              setDeepLoading(false);
              return;
            }
          } catch {
            // Report endpoint may 404 briefly while scan starts.
          }
          await new Promise((r) => setTimeout(r, POLL_INTERVAL));
        }
        setDeepReport({ status: "error", error: "Timed out waiting for deep scan results." });
        setDeepLoading(false);
      };
      pollDeep();
    }
  }, []);

  const pollForResult = useCallback(async (scanId) => {
    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
      try {
        const res = await fetch(`/api/scan/${scanId}`);
        if (!res.ok) continue;
        const data = await res.json();
        if (data.status === "complete") {
          setResult(data);
          setLoading(false);
          return;
        }
        if (data.status === "error") {
          setError(data.error || "Scan failed");
          setLoading(false);
          return;
        }
      } catch {
        // Retry on network error.
      }
    }
    setError("Scan timed out. The repository may be too large.");
    setLoading(false);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);
    setCopied(false);

    try {
      const headers = { "Content-Type": "application/json" };
      const token = localStorage.getItem("anchormd_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/scan", {
        method: "POST",
        headers,
        body: JSON.stringify({ repo_url: url.trim() }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();

      if (data.status === "complete") {
        setResult(data);
        setLoading(false);
        window.history.replaceState({}, "", `?scan=${data.scan_id}`);
      } else {
        // Persist scan ID to URL so refresh can recover
        window.history.replaceState({}, "", `?scan=${data.scan_id}`);
        pollForResult(data.scan_id);
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result?.content) return;
    try {
      await navigator.clipboard.writeText(result.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = result.content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleShare = () => {
    if (!result?.scan_id) return;
    const shareUrl = `${window.location.origin}?scan=${result.scan_id}`;
    navigator.clipboard.writeText(shareUrl);
  };

  const handleDownloadFixReport = async () => {
    if (!result?.scan_id) return;
    setFixDownloading(true);
    try {
      const data = await getFixReport(result.scan_id);
      const blob = new Blob([data.markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const repoName = (result.repo_url || "").split("/").pop()?.replace(".git", "") || "repo";
      a.href = url;
      a.download = `${repoName}-fix-report.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setFixDownloading(false);
    }
  };

  const handleLogin = async () => {
    try {
      const data = await getGitHubLoginUrl();
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
    }
  };

  // On load, check for ?scan= parameter.
  useState(() => {
    const params = new URLSearchParams(window.location.search);
    const scanId = params.get("scan");
    if (scanId) {
      setLoading(true);
      fetch(`/api/scan/${scanId}`)
        .then((r) => r.json())
        .then((data) => {
          if (data.status === "complete") {
            setResult(data);
            setUrl(data.repo_url);
          } else if (data.status === "error") {
            setError(data.error || "Scan failed");
          } else {
            pollForResult(scanId);
          }
        })
        .catch(() => setError("Could not load scan"))
        .finally(() => {
          if (!loading) setLoading(false);
        });
    }
  });

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setPage("home");
                setResult(null);
                setError(null);
              }}
              className="flex items-center gap-3"
            >
              <svg
                className="w-7 h-7 text-anchor-500"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="5" r="3" />
                <line x1="12" y1="8" x2="12" y2="22" />
                <path d="M5 12H2a10 10 0 0 0 20 0h-3" />
              </svg>
              <span className="text-xl font-bold text-white tracking-tight">
                anchormd
              </span>
            </button>

            {/* Nav links for authenticated users */}
            {user && (
              <nav className="hidden sm:flex items-center gap-1 ml-6">
                <button
                  onClick={() => setPage("home")}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    page === "home"
                      ? "text-white bg-gray-800"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  Scan
                </button>
                <button
                  onClick={() => setPage("repos")}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    page === "repos"
                      ? "text-white bg-gray-800"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  Repos
                </button>
                {user.is_admin && (
                  <button
                    onClick={() => setPage("admin")}
                    className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                      page === "admin"
                        ? "text-white bg-gray-800"
                        : "text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    Admin
                  </button>
                )}
              </nav>
            )}
          </div>

          <div className="flex items-center gap-3">
            <a
              href="https://github.com/Arete-Consortium/anchormd"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-gray-200 text-sm transition-colors"
            >
              GitHub
            </a>

            {authLoading ? (
              <div className="w-5 h-5 border-2 border-gray-600 border-t-anchor-500 rounded-full animate-spin" />
            ) : user ? (
              <div className="flex items-center gap-2">
                <img
                  src={user.avatar_url}
                  alt={user.username}
                  className="w-7 h-7 rounded-full border border-gray-700"
                />
                <span className="text-gray-300 text-sm hidden sm:inline">
                  {user.username}
                </span>
                <button
                  onClick={logout}
                  className="text-gray-500 hover:text-gray-300 text-xs ml-1"
                >
                  Logout
                </button>
              </div>
            ) : (
              <button
                onClick={handleLogin}
                className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-white
                           text-sm px-3 py-1.5 rounded-md border border-gray-700 transition-colors"
              >
                <GitHubIcon />
                Sign in
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-5xl mx-auto px-4 w-full">
        {/* Deep Scan Report View */}
        {(deepReport || deepLoading) ? (
          deepLoading ? (
            <div className="pt-12">
              <LoadingSpinner />
              <p className="text-center text-gray-400 text-sm mt-4">
                Loading deep scan report...
              </p>
            </div>
          ) : (
            <DeepScanReportView report={deepReport} />
          )
        ) : page === "repos" && user ? (
          <ReposPage />
        ) : page === "admin" && user?.is_admin ? (
          <AdminPage />
        ) : (
          <>
            {/* Hero */}
            {!result && (
              <div className="text-center pt-16 pb-10">
                <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
                  GitHub URL in.{" "}
                  <span className="text-anchor-400">CLAUDE.md</span> out.
                </h1>
                <p className="text-gray-400 text-lg max-w-2xl mx-auto">
                  Paste a public GitHub repo URL and get a production-ready AI
                  agent context file in seconds.
                  {!user && " Sign in to scan private repos."}
                </p>
              </div>
            )}

            {/* Input Form */}
            <form
              onSubmit={handleSubmit}
              className={`${result ? "pt-6 pb-4" : "pb-8"}`}
            >
              <div className="flex gap-3">
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white
                             placeholder-gray-500 focus:outline-none focus:border-anchor-500 focus:ring-1
                             focus:ring-anchor-500 transition-colors"
                  disabled={loading}
                  required
                />
                <button
                  type="submit"
                  disabled={loading || !url.trim()}
                  className="bg-anchor-600 hover:bg-anchor-700 disabled:bg-gray-700 disabled:text-gray-500
                             text-white font-semibold px-6 py-3 rounded-lg transition-colors
                             disabled:cursor-not-allowed whitespace-nowrap"
                >
                  {loading ? "Scanning..." : "Generate"}
                </button>
              </div>
            </form>

            {/* Error */}
            {error && (
              <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 mb-6">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            {/* Loading */}
            {loading && <LoadingSpinner />}

            {/* Result */}
            {result && (
              <div className="pb-12">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    <ScoreBadge score={result.score} />
                    <span className="text-gray-400 text-sm">
                      {result.files_scanned} files scanned
                      {result.languages &&
                        Object.keys(result.languages).length > 0 && (
                          <span>
                            {" "}
                            &middot;{" "}
                            {Object.keys(result.languages)
                              .slice(0, 3)
                              .join(", ")}
                          </span>
                        )}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowRaw(!showRaw)}
                      className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5
                                 border border-gray-700 rounded-md transition-colors"
                    >
                      {showRaw ? "Preview" : "Raw"}
                    </button>
                    <button
                      onClick={handleShare}
                      className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5
                                 border border-gray-700 rounded-md transition-colors"
                    >
                      Share Link
                    </button>
                    {result.score < 100 && (
                      <button
                        onClick={handleDownloadFixReport}
                        disabled={fixDownloading}
                        className="text-sm px-4 py-1.5 rounded-md font-medium transition-colors
                                   bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-700
                                   disabled:text-gray-500 text-white"
                      >
                        {fixDownloading ? "Generating..." : "Fix Report"}
                      </button>
                    )}
                    <button
                      onClick={handleCopy}
                      className={`text-sm px-4 py-1.5 rounded-md font-medium transition-colors ${
                        copied
                          ? "bg-green-600 text-white"
                          : "bg-anchor-600 hover:bg-anchor-700 text-white"
                      }`}
                    >
                      {copied ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
                  {showRaw ? (
                    <pre className="p-6 text-sm text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">
                      {result.content}
                    </pre>
                  ) : (
                    <div className="p-6 markdown-output">
                      <ReactMarkdown>{result.content}</ReactMarkdown>
                    </div>
                  )}
                </div>

                {/* Deep Scan CTA — shown after free scan completes */}
                {result.scan_type !== "deep" && (
                  <DeepScanCTA
                    repoUrl={result.repo_url}
                    onCheckout={createDeepScanCheckout}
                  />
                )}
              </div>
            )}

            {/* Features (only on landing) */}
            {!result && !loading && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-8 pb-16">
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                  <div className="text-anchor-400 text-2xl mb-3">&#9889;</div>
                  <h3 className="text-white font-semibold mb-2">Instant</h3>
                  <p className="text-gray-400 text-sm">
                    Scans your repo, detects languages, frameworks, patterns, and
                    generates a complete CLAUDE.md in seconds.
                  </p>
                </div>
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                  <div className="text-anchor-400 text-2xl mb-3">&#128270;</div>
                  <h3 className="text-white font-semibold mb-2">Smart Analysis</h3>
                  <p className="text-gray-400 text-sm">
                    8 analyzers detect your tech stack, coding standards,
                    anti-patterns, dependencies, and domain context.
                  </p>
                </div>
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                  <div className="text-anchor-400 text-2xl mb-3">&#128274;</div>
                  <h3 className="text-white font-semibold mb-2">Private Repos</h3>
                  <p className="text-gray-400 text-sm">
                    Sign in with GitHub to scan private repositories and manage
                    all your repos from one dashboard.
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-6 mt-auto">
        <div className="max-w-5xl mx-auto px-4 text-center text-gray-500 text-sm">
          <div className="flex items-center justify-center gap-4 mb-2">
            <a
              href="https://github.com/Arete-Consortium/anchormd"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              GitHub
            </a>
            <span className="text-gray-700">&middot;</span>
            <a
              href="https://pypi.org/project/anchormd/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              PyPI
            </a>
            <span className="text-gray-700">&middot;</span>
            <a
              href="https://github.com/Arete-Consortium/anchormd/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              Issues
            </a>
            <span className="text-gray-700">&middot;</span>
            <a
              href="https://discord.gg/fdzQkrt8"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              Discord
            </a>
          </div>
          <span>
            Built by{" "}
            <a
              href="https://aretedriver.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              AreteDriver
            </a>
            {" "}&middot; anchormd &copy; {new Date().getFullYear()}
          </span>
        </div>
      </footer>
    </div>
  );
}
