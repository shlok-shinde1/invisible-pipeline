import { useEffect, useState } from "react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE;

console.log("API_BASE:", API_BASE);

function getNodeColor(risk) {
  if (risk === "high") return "#fee2e2";
  if (risk === "medium") return "#fef3c7";
  return "#dcfce7";
}

function getRiskLabel(score) {
  if (score >= 70) return "High";
  if (score >= 35) return "Medium";
  return "Low";
}

function transformGraph(apiGraph, selectedNodeId) {
  const nodes = apiGraph.nodes.map((node, index) => ({
    id: node.id,
    position: {
      x: (index % 3) * 320,
      y: Math.floor(index / 3) * 160,
    },
    data: {
      label: `${node.label}\nRisk: ${node.risk.toUpperCase()}`,
    },
    style: {
      background: getNodeColor(node.risk),
      border:
        node.id === selectedNodeId
          ? "4px solid #2563eb"
          : node.risk === "high"
          ? "3px solid #dc2626"
          : node.risk === "medium"
          ? "2px solid #f59e0b"
          : "1px solid #111827",
      boxShadow:
        node.risk === "high"
          ? "0 0 12px rgba(220,38,38,0.6)"
          : node.risk === "medium"
          ? "0 0 8px rgba(245,158,11,0.5)"
          : "none",
      borderRadius: 12,
      padding: 12,
      width: 240,
      whiteSpace: "pre-line",
    },
  }));

  const edges = apiGraph.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.label,
  }));

  return { nodes, edges };
}

function getFixSuggestion(finding, nodeLabel) {
  const title = finding.title.toLowerCase();

  if (title.includes("unpinned")) {
    const match = nodeLabel.match(/uses:\s*([^\s]+)/i);

    if (match) {
      const action = match[1];

      return `Fix:
Replace:
${action}

With a pinned commit SHA:
${action.split("@")[0]}@<commit-sha>

Why:
Version tags like @v4 can change. Pinning ensures security and reproducibility.`;
    }

    return "Pin this GitHub Action to a full commit SHA.";
  }

  if (title.includes("third-party")) {
    return `Fix:
- Verify the repository owner
- Check stars, forks, and last update
- Prefer official actions (actions/*)

Why:
Unverified actions can execute malicious code in your pipeline.`;
  }

  if (title.includes("secret") || title.includes("credential")) {
    return `Fix:
- Remove secrets from logs
- Use GitHub masked secrets
- Avoid echoing tokens

Why:
Secrets in logs can be exposed publicly.`;
  }

  if (title.includes("external")) {
    return `Fix:
- Verify the external endpoint
- Avoid downloading arbitrary scripts
- Use checksums if needed

Why:
External calls can introduce supply chain risks.`;
  }

  if (title.includes("dangerous shell")) {
    return `Fix:
- Avoid chmod 777 or rm -rf
- Scope permissions narrowly

Why:
Overly permissive commands can compromise environments.`;
  }

  return "Review this step manually.";
}

export default function App() {
  const [dashboard, setDashboard] = useState([]);
  const [rawGraph, setRawGraph] = useState(null);
  const [findings, setFindings] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [repoInput, setRepoInput] = useState("facebook/react");
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);

  async function loadDashboard() {
    const res = await fetch(`${API_BASE}/dashboard`);
    const data = await res.json();
    setDashboard(data);
  }

  async function loadGraph(repo = "facebook/react") {
    try {
      setLoading(true);

      const res = await fetch(`${API_BASE}/graph/${repo}`);
      const data = await res.json();

      if (!res.ok) {
        alert(data.detail || "Scan failed");
        return;
      }

      if (data.message) {
        alert(data.message);
        return;
      }

      setRawGraph(data);
      setFindings(data.findings || []);
      setSelectedNode(null);
      setSelectedNodeId(null);

      await loadDashboard();
    } catch (error) {
      console.error(error);
      alert("Something went wrong while scanning this repo.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSavedGraph(scanId) {
    setLoading(true);

    const res = await fetch(`${API_BASE}/dashboard/${scanId}/graph`);
    const data = await res.json();

    if (data.message) {
      alert(data.message);
      setLoading(false);
      return;
    }

    setRawGraph(data);
    setFindings(data.findings || []);
    setSelectedNode(null);
    setSelectedNodeId(null);
    setLoading(false);
  }

  async function handleScan() {
    const cleanedRepo = repoInput.trim();

    if (!cleanedRepo.includes("/")) {
      alert("Use format: owner/repo");
      return;
    }

    await loadGraph(cleanedRepo);
  }

  useEffect(() => {
    async function init() {
      const res = await fetch(`${API_BASE}/dashboard`);
      const data = await res.json();

      setDashboard(data);

      if (data.length > 0) {
        await loadSavedGraph(data[0].id);
      } else {
        setLoading(false);
      }
    }

    init();
  }, []);

  const graph = rawGraph ? transformGraph(rawGraph, selectedNodeId) : null;

  const selectedFindings = selectedNode
    ? findings.filter((finding) => finding.node_id === selectedNode.id)
    : [];

  return (
    <div className="page">
      <aside className="sidebar">
        <h1>Invisible Pipeline</h1>
        <p>CI/CD risk dashboard</p>

        <div className="scan-input">
          <input
            value={repoInput}
            onChange={(e) => setRepoInput(e.target.value)}
            placeholder="owner/repo"
          />
          <button onClick={handleScan}>Scan</button>
        </div>

        {selectedNode && (
          <div className="node-inspector">
            <h2>Selected Node</h2>
            <strong>{selectedNode.data.label}</strong>

            <h3>Related Findings</h3>

            {selectedFindings.length === 0 ? (
              <p>No findings tied to this node.</p>
            ) : (
              selectedFindings.map((finding, index) => (
                <div key={index} className={`finding ${finding.severity}`}>
                  <strong>{finding.title}</strong>
                  <span>{finding.severity}</span>
                  <p>{finding.description}</p>
                  <p>
                    <pre className="fix-box">
                      {getFixSuggestion(finding, selectedNode.data.label)}
                    </pre>
                    <button
                      className="copy-fix-button"
                      onClick={() =>
                        navigator.clipboard.writeText(
                          getFixSuggestion(finding, selectedNode.data.label)
                        )
                      }
                    >
                      Copy Fix
                    </button> 
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        <h2>Recent Scans</h2>
        {dashboard.map((scan) => (
          <div
            key={scan.id}
            className="scan-card"
            onClick={() => loadSavedGraph(scan.id)}
          >
            <strong>{scan.repo}</strong>
            <p>
              Risk Score: {scan.risk_score}/100{" "}
              <strong>{getRiskLabel(scan.risk_score)}</strong>
            </p>
            <p>Findings: {scan.finding_count}</p>

            {scan.risk_breakdown && (
              <div className="risk-breakdown">
                {Object.entries(scan.risk_breakdown)
                  .filter(([_, count]) => count > 0)
                  .map(([key, count]) => (
                    <span key={key} className={`risk-badge ${key}`}>
                      {key.replaceAll("_", " ")} · {count}
                    </span>
                  ))}
              </div>
            )}

            <small>{new Date(scan.created_at).toLocaleString()}</small>
          </div>
        ))}

        <h2>Findings</h2>
        {findings.map((finding, index) => (
          <div
            key={index}
            className={`finding ${finding.severity}`}
            onClick={() => setSelectedNodeId(finding.node_id)}
            style={{ cursor: finding.node_id ? "pointer" : "default" }}
          >
            <strong>{finding.title}</strong>
            <span>{finding.severity}</span>
            <p>{finding.description}</p>
          </div>
        ))}
      </aside>

      <main className="graph">
        {loading || !graph ? (
          <div className="loading">Loading pipeline graph...</div>
        ) : (
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            fitView
            onNodeClick={(_, node) => {
              setSelectedNode(node);
              setSelectedNodeId(node.id);
            }}
          >
            <Background />
            <Controls />
          </ReactFlow>
        )}
      </main>
    </div>
  );
}
