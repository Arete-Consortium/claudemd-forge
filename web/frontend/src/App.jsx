import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";

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

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

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
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
      } else {
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
      // Fallback for non-HTTPS.
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
          </div>
          <a
            href="https://github.com/Arete-Consortium/anchormd"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-gray-200 text-sm transition-colors"
          >
            GitHub
          </a>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-5xl mx-auto px-4 w-full">
        {/* Hero */}
        {!result && (
          <div className="text-center pt-16 pb-10">
            <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
              GitHub URL in.{" "}
              <span className="text-anchor-400">CLAUDE.md</span> out.
            </h1>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              Paste a public GitHub repo URL and get a production-ready AI agent
              context file in seconds. No sign-up required.
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
            {/* Result header */}
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

            {/* Content */}
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
              <div className="text-anchor-400 text-2xl mb-3">&#128279;</div>
              <h3 className="text-white font-semibold mb-2">Shareable</h3>
              <p className="text-gray-400 text-sm">
                Every scan gets a unique link you can share with your team or
                bookmark for later.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-6 mt-auto">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between text-gray-500 text-sm">
          <span>anchormd &copy; {new Date().getFullYear()}</span>
          <div className="flex gap-4">
            <a
              href="https://pypi.org/project/anchormd/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              PyPI
            </a>
            <a
              href="https://github.com/Arete-Consortium/anchormd"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
