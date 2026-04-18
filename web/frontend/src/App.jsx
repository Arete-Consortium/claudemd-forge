import { useState, useCallback, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "./AuthContext";
import { getGitHubLoginUrl, createDeepScanCheckout, getDeepScanReport, getFixReport, pushPR, getCursorRules, getCopilotInstructions, getWindsurfRules } from "./api";
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
    <div className="bg-gradient-to-r from-anchor-900/80 to-anchor-800/60 border-2 border-anchor-500/60 rounded-lg p-6 mt-4">
      <div className="flex flex-col gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-anchor-400 text-xl">&#128270;</span>
            <h3 className="text-white font-bold text-xl">
              Unlock the Deep Report
            </h3>
            <span className="bg-anchor-600/30 text-anchor-300 text-xs font-semibold px-2 py-0.5 rounded-full border border-anchor-500/40">
              $19 one-time
            </span>
          </div>
          <p className="text-gray-300 text-sm leading-relaxed">
            Your free scan found the basics. The deep report adds{" "}
            <span className="text-white font-medium">architecture recommendations</span>,{" "}
            <span className="text-white font-medium">security review</span>,{" "}
            <span className="text-white font-medium">dependency analysis</span>, and{" "}
            <span className="text-white font-medium">actionable fix priorities</span>{" "}
            — delivered to your inbox.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@email.com"
            className="bg-gray-900 border border-gray-600 rounded-md px-4 py-2.5 text-white text-sm
                       placeholder-gray-500 focus:outline-none focus:border-anchor-400 focus:ring-1
                       focus:ring-anchor-400/50 w-full sm:w-64"
          />
          <button
            onClick={handleCheckout}
            disabled={submitting || !email.trim()}
            className="bg-anchor-500 hover:bg-anchor-600 disabled:bg-gray-700 disabled:text-gray-500
                       text-white font-bold px-6 py-2.5 rounded-md transition-colors text-sm
                       whitespace-nowrap shadow-lg shadow-anchor-500/20"
          >
            {submitting ? "Redirecting to checkout..." : "Get Deep Report"}
          </button>
        </div>
      </div>
      {ctaError && (
        <p className="text-red-400 text-sm mt-2">{ctaError}</p>
      )}
    </div>
  );
}

function GradeBadge({ grade, size = "md" }) {
  const colors = {
    A: "bg-green-600 text-white",
    B: "bg-blue-600 text-white",
    C: "bg-yellow-600 text-black",
    D: "bg-orange-600 text-white",
    F: "bg-red-600 text-white",
  };
  const sizes = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-3 py-1",
    lg: "text-2xl px-4 py-2 font-bold",
  };
  return (
    <span className={`${colors[grade] || "bg-gray-600 text-white"} ${sizes[size]} rounded-md font-bold`}>
      {grade}
    </span>
  );
}

function SeverityBadge({ severity }) {
  const colors = {
    critical: "bg-red-600 text-white",
    high: "bg-orange-600 text-white",
    medium: "bg-yellow-600 text-black",
    low: "bg-blue-600 text-white",
    unknown: "bg-gray-600 text-white",
  };
  return (
    <span className={`${colors[severity] || colors.unknown} text-xs px-2 py-0.5 rounded font-semibold uppercase`}>
      {severity}
    </span>
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
            : "Running deep analysis (LLM review, dependency audit, scoring)..."}
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

  const scores = report.category_scores;
  const llm = report.llm_analysis;
  const deps = report.dependency_audit;
  const debt = report.tech_debt;
  const compliance = report.compliance;
  const hygiene = report.hygiene;
  const history = report.history;

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

      {/* Category Scorecard */}
      {scores && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-white text-xl font-semibold">Health Scorecard</h2>
            <GradeBadge grade={scores.grade} size="md" />
            <span className="text-gray-400 text-sm">{scores.overall}/100 overall</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {Object.entries(scores.categories || {}).map(([key, cat]) => (
              <div key={key} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-300 text-sm font-medium">{cat.label}</span>
                  <GradeBadge grade={cat.grade} size="sm" />
                </div>
                <div className="text-2xl font-bold text-white mb-1">{cat.score}</div>
                <p className="text-gray-500 text-xs">{cat.details}</p>
              </div>
            ))}
          {/* Scan History Comparison */}
          {history && (
            <div className="mt-4 bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-gray-400 text-sm font-medium">vs previous scan</span>
                <span className="text-gray-500 text-xs">
                  {history.previous_date ? new Date(history.previous_date).toLocaleDateString() : ""}
                </span>
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-1">
                  <span className="text-gray-400 text-sm">Overall:</span>
                  <span className="text-white font-bold">{history.previous_score}</span>
                  <span className="text-gray-500">→</span>
                  <span className="text-white font-bold">{scores.overall}</span>
                  {scores.overall > history.previous_score ? (
                    <span className="text-green-400 text-sm font-medium">+{scores.overall - history.previous_score}</span>
                  ) : scores.overall < history.previous_score ? (
                    <span className="text-red-400 text-sm font-medium">{scores.overall - history.previous_score}</span>
                  ) : (
                    <span className="text-gray-500 text-sm">=</span>
                  )}
                </div>
                {Object.entries(history.previous_categories || {}).map(([key, prev]) => {
                  const curr = scores.categories?.[key];
                  if (!curr) return null;
                  const diff = curr.score - prev.score;
                  if (diff === 0) return null;
                  return (
                    <div key={key} className="flex items-center gap-1">
                      <span className="text-gray-500 text-xs">{curr.label}:</span>
                      <span className={`text-xs font-medium ${diff > 0 ? "text-green-400" : "text-red-400"}`}>
                        {diff > 0 ? `+${diff}` : diff}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          </div>
        </div>
      )}

      {/* Compliance Checklist */}
      {compliance && compliance.checks && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-white text-xl font-semibold">Compliance Checklist</h2>
            <span className="text-gray-400 text-sm">{compliance.passed}/{compliance.total} passed</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {compliance.checks.map((check, i) => (
              <div
                key={i}
                className={`rounded-lg p-3 border ${
                  check.found
                    ? "bg-green-950/20 border-green-800/40"
                    : "bg-red-950/20 border-red-800/40"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={check.found ? "text-green-400" : "text-red-400"}>
                    {check.found ? "\u2713" : "\u2717"}
                  </span>
                  <span className="text-gray-300 text-sm">{check.label}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tech Debt Findings */}
      {debt && debt.total_signals > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-white text-xl font-semibold">Tech Debt</h2>
            <span className="text-gray-400 text-sm">{debt.total_signals} signals found</span>
          </div>
          {debt.critical && debt.critical.length > 0 && (
            <div className="mb-3">
              <h3 className="text-red-400 text-sm font-semibold uppercase tracking-wide mb-2">Critical ({debt.critical.length})</h3>
              <div className="space-y-1">
                {debt.critical.slice(0, 10).map((s, i) => (
                  <div key={i} className="bg-red-950/20 border border-red-800/30 rounded px-3 py-2 text-sm">
                    <span className="text-gray-400 font-mono text-xs">{s.file}{s.line ? `:${s.line}` : ""}</span>
                    <span className="text-gray-300 ml-2">{s.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {debt.high && debt.high.length > 0 && (
            <div className="mb-3">
              <h3 className="text-orange-400 text-sm font-semibold uppercase tracking-wide mb-2">High ({debt.high.length})</h3>
              <div className="space-y-1">
                {debt.high.slice(0, 10).map((s, i) => (
                  <div key={i} className="bg-orange-950/20 border border-orange-800/30 rounded px-3 py-2 text-sm">
                    <span className="text-gray-400 font-mono text-xs">{s.file}{s.line ? `:${s.line}` : ""}</span>
                    <span className="text-gray-300 ml-2">{s.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {debt.medium && debt.medium.length > 0 && (
            <div className="mb-3">
              <h3 className="text-yellow-400 text-sm font-semibold uppercase tracking-wide mb-2">Medium ({debt.medium.length})</h3>
              <div className="space-y-1">
                {debt.medium.slice(0, 5).map((s, i) => (
                  <div key={i} className="bg-yellow-950/20 border border-yellow-800/30 rounded px-3 py-2 text-sm">
                    <span className="text-gray-400 font-mono text-xs">{s.file}{s.line ? `:${s.line}` : ""}</span>
                    <span className="text-gray-300 ml-2">{s.message}</span>
                  </div>
                ))}
                {debt.medium.length > 5 && (
                  <p className="text-gray-500 text-xs pl-3">+ {debt.medium.length - 5} more</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Dependency Audit */}
      {deps && !deps.error && (
        <div className="mb-8">
          <h2 className="text-white text-xl font-semibold mb-4">Dependency Audit</h2>
          {deps.vulnerabilities && deps.vulnerabilities.length > 0 ? (
            <>
              <div className="bg-red-950/30 border border-red-800/50 rounded-lg p-3 mb-3">
                <p className="text-red-400 text-sm font-medium">
                  {deps.vulnerabilities.length} vulnerabilit{deps.vulnerabilities.length === 1 ? "y" : "ies"} found in {deps.total_packages} packages
                </p>
              </div>
              <div className="space-y-2">
                {deps.vulnerabilities.map((v, i) => (
                  <div key={i} className="bg-gray-900 border border-gray-700 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <SeverityBadge severity={v.severity} />
                      <span className="text-white font-medium">{v.package}</span>
                      <span className="text-gray-500 text-sm">{v.version}</span>
                      <span className="text-gray-500 text-xs">{v.cve_id}</span>
                    </div>
                    <p className="text-gray-400 text-sm">{v.summary}</p>
                    {v.fix_version && (
                      <p className="text-green-400 text-xs mt-1">Fix available: upgrade to {v.fix_version}</p>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="bg-green-950/30 border border-green-800/50 rounded-lg p-4">
              <p className="text-green-400 text-sm font-medium">
                No known vulnerabilities found across {deps.total_packages} packages
              </p>
            </div>
          )}
        </div>
      )}

      {/* LLM Analysis */}
      {llm && !llm.error && (
        <div className="mb-8">
          <h2 className="text-white text-xl font-semibold mb-4">AI Analysis</h2>

          {llm.architecture && (
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-5 mb-3">
              <h3 className="text-anchor-400 font-semibold text-sm uppercase tracking-wide mb-2">Architecture Review</h3>
              <div className="text-gray-300 text-sm leading-relaxed markdown-output">
                <ReactMarkdown>{llm.architecture}</ReactMarkdown>
              </div>
            </div>
          )}

          {llm.security && (
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-5 mb-3">
              <h3 className="text-anchor-400 font-semibold text-sm uppercase tracking-wide mb-2">Security Review</h3>
              <div className="text-gray-300 text-sm leading-relaxed markdown-output">
                <ReactMarkdown>{llm.security}</ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Context Hygiene */}
      {hygiene && !hygiene.error && hygiene.total_issues > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-white text-xl font-semibold">CLAUDE.md Quality</h2>
            <GradeBadge grade={hygiene.grade} size="sm" />
            <span className="text-gray-400 text-sm">{hygiene.total_issues} issue{hygiene.total_issues !== 1 ? "s" : ""} found</span>
          </div>
          <div className="space-y-2">
            {hygiene.contradictions && hygiene.contradictions.map((c, i) => (
              <div key={`c-${i}`} className="bg-red-950/20 border border-red-800/30 rounded-lg p-3">
                <span className="text-red-400 text-xs font-semibold uppercase mr-2">Contradiction</span>
                <span className="text-gray-300 text-sm">{c.description}</span>
              </div>
            ))}
            {hygiene.staleness && hygiene.staleness.map((s, i) => (
              <div key={`s-${i}`} className="bg-yellow-950/20 border border-yellow-800/30 rounded-lg p-3">
                <span className="text-yellow-400 text-xs font-semibold uppercase mr-2">Stale</span>
                <span className="text-gray-300 text-sm">{s.reasons?.join(", ") || "Potentially outdated content"}</span>
              </div>
            ))}
            {hygiene.deadweight && hygiene.deadweight.map((d, i) => (
              <div key={`d-${i}`} className="bg-gray-800 border border-gray-700 rounded-lg p-3">
                <span className="text-gray-400 text-xs font-semibold uppercase mr-2">Deadweight</span>
                <span className="text-gray-300 text-sm">{d.reason}</span>
                {d.tokens_recoverable > 0 && (
                  <span className="text-gray-500 text-xs ml-2">({d.tokens_recoverable} tokens recoverable)</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations with Code Snippets */}
      {report.recommendations && report.recommendations.length > 0 && (
        <div className="mb-8">
          <h2 className="text-white text-xl font-semibold mb-4">
            Priority Actions
          </h2>
          <div className="space-y-4">
            {report.recommendations.map((rec, i) => (
              <div
                key={i}
                className="bg-gray-900 border border-gray-700 rounded-lg p-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <PriorityBadge priority={rec.priority} />
                  <h3 className="text-white font-medium">{rec.title}</h3>
                  {rec.file && (
                    <span className="text-gray-500 text-xs font-mono">{rec.file}</span>
                  )}
                </div>
                <p className="text-gray-400 text-sm mb-3">{rec.description}</p>
                {(rec.code_before || rec.code_after) && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
                    {rec.code_before && (
                      <div>
                        <span className="text-red-400 text-xs font-semibold uppercase">Before</span>
                        <pre className="mt-1 bg-red-950/20 border border-red-800/20 rounded p-3 text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap">
                          {rec.code_before}
                        </pre>
                      </div>
                    )}
                    {rec.code_after && (
                      <div>
                        <span className="text-green-400 text-xs font-semibold uppercase">After</span>
                        <pre className="mt-1 bg-green-950/20 border border-green-800/20 rounded p-3 text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap">
                          {rec.code_after}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
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
  const { user, loading: authLoading, logout, logoutEverywhere } = useAuth();
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
  const [prPushing, setPrPushing] = useState(false);
  const [prUrl, setPrUrl] = useState(null);

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

  const handlePushPR = async () => {
    if (!result?.scan_id) return;
    setPrPushing(true);
    setPrUrl(null);
    try {
      const data = await pushPR(result.scan_id);
      setPrUrl(data.pr_url);
    } catch (err) {
      setError(err.message);
    } finally {
      setPrPushing(false);
    }
  };

  const handleDownloadRulesFile = async (fetcher, filename) => {
    if (!result?.scan_id) return;
    try {
      const data = await fetcher(result.scan_id);
      const blob = new Blob([data.content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDownloadCursorRules = () =>
    handleDownloadRulesFile(getCursorRules, ".cursorrules");
  const handleDownloadCopilotInstructions = () =>
    handleDownloadRulesFile(getCopilotInstructions, "copilot-instructions.md");
  const handleDownloadWindsurfRules = () =>
    handleDownloadRulesFile(getWindsurfRules, ".windsurfrules");

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
                setDeepReport(null);
                setDeepLoading(false);
                window.history.replaceState({}, "", window.location.pathname);
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
                <button
                  onClick={() => {
                    if (
                      window.confirm(
                        "Sign out of every device? All active sessions will be revoked.",
                      )
                    ) {
                      logoutEverywhere();
                    }
                  }}
                  className="text-gray-600 hover:text-red-400 text-xs"
                  title="Revoke every active session for your account"
                >
                  Everywhere
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
                <p className="text-gray-400 text-lg max-w-2xl mx-auto mb-4">
                  Paste a public GitHub repo URL and get a production-ready AI
                  agent context file in seconds.
                  {!user && " Sign in to scan private repos."}
                </p>
                <div className="flex items-center justify-center gap-3 text-gray-500 text-sm">
                  <span>Works with</span>
                  <span className="text-gray-300 font-medium">Claude Code</span>
                  <span>&middot;</span>
                  <span className="text-gray-300 font-medium">Cursor</span>
                  <span>&middot;</span>
                  <span className="text-gray-300 font-medium">Copilot</span>
                  <span>&middot;</span>
                  <span className="text-gray-300 font-medium">Windsurf</span>
                </div>
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
                    <button
                      onClick={handleDownloadCursorRules}
                      className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5
                                 border border-gray-700 rounded-md transition-colors"
                    >
                      .cursorrules
                    </button>
                    <button
                      onClick={handleDownloadCopilotInstructions}
                      className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5
                                 border border-gray-700 rounded-md transition-colors"
                    >
                      Copilot
                    </button>
                    <button
                      onClick={handleDownloadWindsurfRules}
                      className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5
                                 border border-gray-700 rounded-md transition-colors"
                    >
                      .windsurfrules
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
                    {user && (
                      prUrl ? (
                        <a
                          href={prUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm px-4 py-1.5 rounded-md font-medium bg-green-600
                                     hover:bg-green-700 text-white transition-colors"
                        >
                          View PR
                        </a>
                      ) : (
                        <button
                          onClick={handlePushPR}
                          disabled={prPushing}
                          className="text-sm px-4 py-1.5 rounded-md font-medium transition-colors
                                     bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700
                                     disabled:text-gray-500 text-white"
                        >
                          {prPushing ? "Creating PR..." : "Push to Repo"}
                        </button>
                      )
                    )}
                  </div>
                </div>

                {/* Deep Scan CTA — shown above results for visibility */}
                {result.scan_type !== "deep" && (
                  <DeepScanCTA
                    repoUrl={result.repo_url}
                    onCheckout={createDeepScanCheckout}
                  />
                )}

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
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-8 pb-8">
                  <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                    <div className="text-anchor-400 text-2xl mb-3">&#9889;</div>
                    <h3 className="text-white font-semibold mb-2">Instant Scan</h3>
                    <p className="text-gray-400 text-sm">
                      Paste a URL, get a scored CLAUDE.md in 30 seconds. 8 analyzers
                      detect your actual code patterns, not templates.
                    </p>
                  </div>
                  <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                    <div className="text-anchor-400 text-2xl mb-3">&#128295;</div>
                    <h3 className="text-white font-semibold mb-2">Fix Report</h3>
                    <p className="text-gray-400 text-sm">
                      Score under 100? Download a fix report with gap analysis,
                      copy-paste templates, and a Claude Code prompt to auto-fix.
                    </p>
                  </div>
                  <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                    <div className="text-anchor-400 text-2xl mb-3">&#128640;</div>
                    <h3 className="text-white font-semibold mb-2">Push to Repo</h3>
                    <p className="text-gray-400 text-sm">
                      One click creates a PR with your CLAUDE.md. Also exports
                      to .cursorrules, .github/copilot-instructions.md, and
                      .windsurfrules.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pb-16">
                  <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                    <div className="text-anchor-400 text-2xl mb-3">&#128274;</div>
                    <h3 className="text-white font-semibold mb-2">Private Repos</h3>
                    <p className="text-gray-400 text-sm">
                      Sign in with GitHub to scan private repos and batch-scan
                      your entire account.
                    </p>
                  </div>
                  <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                    <div className="text-anchor-400 text-2xl mb-3">&#9889;</div>
                    <h3 className="text-white font-semibold mb-2">Smart Caching</h3>
                    <p className="text-gray-400 text-sm">
                      Re-scans skip repos that already scored 100 and have no new
                      pushes. Only scan what changed.
                    </p>
                  </div>
                  <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
                    <div className="text-anchor-400 text-2xl mb-3">&#128187;</div>
                    <h3 className="text-white font-semibold mb-2">CLI Too</h3>
                    <p className="text-gray-400 text-sm">
                      <code className="text-anchor-300 text-xs">pip install anchormd</code>
                      {" "}&mdash; run locally in any project directory.
                      Pro tier for init, diff, and tech debt.
                    </p>
                  </div>
                </div>
              </>

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
