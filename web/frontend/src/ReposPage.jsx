import { useState, useEffect, useCallback } from "react";
import { useAuth } from "./AuthContext";
import { listRepos, scanRepo, getScan, scanAll, getBatchStatus } from "./api";
import ReactMarkdown from "react-markdown";

const POLL_INTERVAL = 2000;
const MAX_POLLS = 120;

function ScoreBadge({ score }) {
  if (score == null) return null;
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
    <span className={`${color} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>
      {score} {label}
    </span>
  );
}

function VisibilityBadge({ isPrivate }) {
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
        isPrivate
          ? "bg-yellow-900/50 text-yellow-400 border border-yellow-700"
          : "bg-green-900/50 text-green-400 border border-green-700"
      }`}
    >
      {isPrivate ? "Private" : "Public"}
    </span>
  );
}

export default function ReposPage() {
  const { user } = useAuth();
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // scanId -> scan result
  const [scanResults, setScanResults] = useState({});
  // scanId -> "scanning" | "complete" | "error"
  const [scanStatuses, setScanStatuses] = useState({});
  // Batch state
  const [batchId, setBatchId] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);
  const [batchRunning, setBatchRunning] = useState(false);
  // Selected scan to view
  const [selectedScan, setSelectedScan] = useState(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    listRepos()
      .then((data) => setRepos(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    // Recover active batch on refresh
    const savedBatch = localStorage.getItem("anchormd_batch_id");
    if (savedBatch) {
      setBatchId(savedBatch);
      setBatchRunning(true);
      pollBatch(savedBatch);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pollScan = useCallback(async (scanId, repoUrl) => {
    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
      try {
        const data = await getScan(scanId);
        if (data.status === "complete") {
          setScanResults((prev) => ({ ...prev, [repoUrl]: data }));
          setScanStatuses((prev) => ({ ...prev, [repoUrl]: "complete" }));
          return;
        }
        if (data.status === "error") {
          setScanStatuses((prev) => ({ ...prev, [repoUrl]: "error" }));
          return;
        }
      } catch {
        // Retry.
      }
    }
    setScanStatuses((prev) => ({ ...prev, [repoUrl]: "error" }));
  }, []);

  const handleScanOne = async (repo) => {
    setScanStatuses((prev) => ({ ...prev, [repo.html_url]: "scanning" }));
    try {
      const data = await scanRepo(repo.html_url);
      if (data.status === "complete") {
        setScanResults((prev) => ({ ...prev, [repo.html_url]: data }));
        setScanStatuses((prev) => ({ ...prev, [repo.html_url]: "complete" }));
      } else {
        pollScan(data.scan_id, repo.html_url);
      }
    } catch {
      setScanStatuses((prev) => ({ ...prev, [repo.html_url]: "error" }));
    }
  };

  const handleScanAll = async () => {
    if (!user) return;
    setBatchRunning(true);
    try {
      const data = await scanAll(user.username);
      setBatchId(data.batch_id);
      localStorage.setItem("anchormd_batch_id", data.batch_id);
      // Mark all as scanning.
      const statuses = {};
      repos.forEach((r) => {
        statuses[r.html_url] = "scanning";
      });
      setScanStatuses(statuses);
      // Poll batch status.
      pollBatch(data.batch_id);
    } catch (err) {
      setError(err.message);
      setBatchRunning(false);
    }
  };

  const pollBatch = async (bid) => {
    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
      try {
        const data = await getBatchStatus(bid);
        setBatchStatus(data);
        // Update individual scan statuses from batch data.
        const newStatuses = {};
        const newResults = {};
        for (const scan of data.scans) {
          newStatuses[scan.repo_url] = scan.status === "pending" ? "scanning" : scan.status;
          if (scan.status === "complete" && scan.score != null) {
            newResults[scan.repo_url] = scan;
          }
        }
        setScanStatuses((prev) => ({ ...prev, ...newStatuses }));
        setScanResults((prev) => ({ ...prev, ...newResults }));

        if (data.completed >= data.repo_count) {
          setBatchRunning(false);
          localStorage.removeItem("anchormd_batch_id");
          return;
        }
      } catch {
        // Retry.
      }
    }
    setBatchRunning(false);
  };

  const handleViewResult = async (repoUrl) => {
    const existing = scanResults[repoUrl];
    if (existing && existing.content) {
      setSelectedScan(existing);
      return;
    }
    // Need to fetch full scan result.
    if (existing && existing.scan_id) {
      try {
        const full = await getScan(existing.scan_id);
        setScanResults((prev) => ({ ...prev, [repoUrl]: full }));
        setSelectedScan(full);
      } catch {
        // ignore
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-8 h-8 border-4 border-gray-700 border-t-anchor-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 mt-6">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  // If viewing a specific scan result.
  if (selectedScan) {
    return (
      <div className="pb-12">
        <button
          onClick={() => {
            setSelectedScan(null);
            setShowRaw(false);
          }}
          className="text-gray-400 hover:text-gray-200 text-sm mb-4 inline-flex items-center gap-1"
        >
          &larr; Back to repos
        </button>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <ScoreBadge score={selectedScan.score} />
            <span className="text-gray-300 text-sm font-medium">{selectedScan.repo_url}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="text-gray-400 hover:text-gray-200 text-sm px-3 py-1.5 border border-gray-700 rounded-md"
            >
              {showRaw ? "Preview" : "Raw"}
            </button>
            <button
              onClick={() => {
                if (selectedScan.content) {
                  navigator.clipboard.writeText(selectedScan.content);
                }
              }}
              className="bg-anchor-600 hover:bg-anchor-700 text-white text-sm px-4 py-1.5 rounded-md font-medium"
            >
              Copy
            </button>
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
          {showRaw ? (
            <pre className="p-6 text-sm text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">
              {selectedScan.content}
            </pre>
          ) : (
            <div className="p-6 markdown-output">
              <ReactMarkdown>{selectedScan.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="pb-12">
      <div className="flex items-center justify-between mb-6 mt-6">
        <h2 className="text-xl font-bold text-white">
          Your Repositories ({repos.length})
        </h2>
        <div className="flex items-center gap-3">
          {batchRunning && batchStatus && (
            <span className="text-gray-400 text-sm">
              {batchStatus.completed}/{batchStatus.repo_count} complete
            </span>
          )}
          <button
            onClick={handleScanAll}
            disabled={batchRunning}
            className="bg-anchor-600 hover:bg-anchor-700 disabled:bg-gray-700 disabled:text-gray-500
                       text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
          >
            {batchRunning ? "Scanning..." : "Scan All"}
          </button>
        </div>
      </div>

      {batchRunning && (
        <div className="mb-6">
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div
              className="bg-anchor-500 h-2 rounded-full transition-all duration-500"
              style={{
                width: batchStatus
                  ? `${(batchStatus.completed / batchStatus.repo_count) * 100}%`
                  : "0%",
              }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {repos.map((repo) => {
          const status = scanStatuses[repo.html_url];
          const result = scanResults[repo.html_url];
          return (
            <div
              key={repo.full_name}
              className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 flex flex-col gap-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <a
                    href={repo.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-white font-medium hover:text-anchor-400 truncate block"
                  >
                    {repo.name}
                  </a>
                  <div className="flex items-center gap-2 mt-1">
                    <VisibilityBadge isPrivate={repo.private} />
                    {repo.language && (
                      <span className="text-gray-500 text-xs">{repo.language}</span>
                    )}
                    {repo.stargazers_count > 0 && (
                      <span className="text-gray-500 text-xs">
                        &#9733; {repo.stargazers_count}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mt-auto">
                {status === "complete" && result ? (
                  <div className="flex items-center gap-2">
                    <ScoreBadge score={result.score} />
                    <button
                      onClick={() => handleViewResult(repo.html_url)}
                      className="text-anchor-400 hover:text-anchor-300 text-xs underline"
                    >
                      View
                    </button>
                  </div>
                ) : status === "scanning" ? (
                  <div className="flex items-center gap-2 text-gray-400 text-xs">
                    <div className="w-3 h-3 border-2 border-gray-600 border-t-anchor-500 rounded-full animate-spin" />
                    Scanning...
                  </div>
                ) : status === "error" ? (
                  <span className="text-red-400 text-xs">Error</span>
                ) : (
                  <span />
                )}

                {status !== "scanning" && (
                  <button
                    onClick={() => handleScanOne(repo)}
                    className="text-gray-400 hover:text-white text-xs px-3 py-1.5
                               border border-gray-700 rounded-md transition-colors"
                  >
                    Scan
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
