import { useEffect, useState } from 'react';
import { BrainCircuit, Calculator, Network, Save, Users } from 'lucide-react';
import { ragApiRequest } from './api';
import KnowledgeGraph from './KnowledgeGraph.jsx';

export default function AdvancedPanel({ onClose, privacyMode, setPrivacyMode, onAgentResult, onWorkspaceSelect, onPromptSelected }) {
  const [memory, setMemory] = useState('');
  const [graph, setGraph] = useState({ nodes: [] });
  const [workspaces, setWorkspaces] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [automations, setAutomations] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [explorerQuery, setExplorerQuery] = useState('');
  const [sourceChunks, setSourceChunks] = useState([]);
  const [activity, setActivity] = useState({});
  const [quality, setQuality] = useState({ freshness: [], duplicate_sources: [] });
  const [agentQuestion, setAgentQuestion] = useState('');
  const [expression, setExpression] = useState('');
  const [status, setStatus] = useState('');

  const refresh = async () => {
    try {
      const [memoryData, graphData, workspaceData, qualityData, documentData, automationData, promptData] = await Promise.all([
        ragApiRequest('/api/memory'), ragApiRequest('/api/knowledge-graph'), ragApiRequest('/api/workspaces'), ragApiRequest('/api/source-quality'), ragApiRequest('/api/documents'), ragApiRequest('/api/automations'), ragApiRequest('/api/prompts'),
      ]);
      setMemory((memoryData.items || []).join('\n'));
      setGraph(graphData);
      setWorkspaces(workspaceData.workspaces || []);
      setQuality(qualityData);
      setDocuments(documentData.documents || []); setAutomations(automationData.automations || []); setPrompts(promptData.prompts || []);
    } catch (error) { setStatus(error.message); }
  };
  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!workspaces.length) return undefined;
    let alive = true;
    const loadActivity = async () => {
      const entries = await Promise.all(workspaces.map(async (workspace) => {
        try { return [workspace.id, await ragApiRequest(`/api/workspaces/${workspace.id}/events`)]; } catch { return [workspace.id, null]; }
      }));
      if (alive) setActivity(Object.fromEntries(entries));
    };
    void loadActivity();
    const timer = window.setInterval(loadActivity, 15000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [workspaces]);

  const saveMemory = async () => {
    try {
      const data = await ragApiRequest('/api/memory', { method: 'PUT', body: JSON.stringify({ items: memory.split('\n') }) });
      setMemory(data.items.join('\n')); setStatus('Memory saved.');
    } catch (error) { setStatus(error.message); }
  };

  const runAgent = async () => {
    try {
      const plan = await ragApiRequest('/api/agent/plan', { method: 'POST', body: JSON.stringify({ question: agentQuestion || expression || 'Help me' }) });
      if (!expression) { setStatus(`Plan: ${plan.steps.map((step) => step.tool).join(' → ')}`); return; }
      if (!window.confirm(`Approve calculator execution for: ${expression}?`)) return;
      const result = await ragApiRequest('/api/agent/execute', { method: 'POST', body: JSON.stringify({ question: agentQuestion || expression, expression }) });
      onAgentResult?.(`Agent calculator result: ${result.expression} = ${result.result}`);
      setStatus('Approved agent result added to chat.');
    } catch (error) { setStatus(error.message); }
  };

  const compareDocuments = async () => {
    const left = window.prompt(`First document:\n${documents.map((document) => document.name).join('\n')}`)?.trim(); if (!left) return;
    const right = window.prompt('Second document')?.trim(); if (!right) return;
    try {
      const result = await ragApiRequest('/api/agent/execute', { method: 'POST', body: JSON.stringify({ question: 'Compare documents', left_document: left, right_document: right }) });
      onAgentResult?.(`Document comparison (${result.changed_lines} changed lines):\n\n\`\`\`diff\n${result.changes.join('\n')}\n\`\`\``);
    } catch (error) { setStatus(error.message); }
  };

  const generateReport = async () => {
    const topic = window.prompt('Report topic')?.trim(); if (!topic) return;
    try { const result = await ragApiRequest('/api/agent/report', { method: 'POST', body: JSON.stringify({ question: topic }) }); onAgentResult?.(result.response); } catch (error) { setStatus(error.message); }
  };

  const createWorkspace = async () => {
    const name = window.prompt('Workspace name')?.trim(); if (!name) return;
    try { await ragApiRequest('/api/workspaces', { method: 'POST', body: JSON.stringify({ name }) }); await refresh(); } catch (error) { setStatus(error.message); }
  };

  const inviteMember = async (workspace) => {
    const accountId = window.prompt('Account ID to invite')?.trim(); if (!accountId) return;
    const role = window.prompt('Role: viewer or editor', 'viewer')?.trim() || 'viewer';
    try {
      await ragApiRequest(`/api/workspaces/${workspace.id}/members`, { method: 'POST', body: JSON.stringify({ account_id: accountId, role }) });
      setStatus('Member invited.'); await refresh();
    } catch (error) { setStatus(error.message); }
  };

  const addComment = async (workspace) => {
    const message = window.prompt(`Comment in ${workspace.name}`)?.trim(); if (!message) return;
    try {
      await ragApiRequest(`/api/workspaces/${workspace.id}/comments`, { method: 'POST', body: JSON.stringify({ message }) });
      setStatus('Comment added.'); await refresh();
    } catch (error) { setStatus(error.message); }
  };

  const shareDocument = async (workspace) => {
    const filename = window.prompt(`Document to share in ${workspace.name}:\n${documents.map((document) => document.name).join('\n')}`)?.trim(); if (!filename) return;
    try { await ragApiRequest(`/api/workspaces/${workspace.id}/documents/${encodeURIComponent(filename)}`, { method: 'POST' }); setStatus('Document shared and workspace index refreshed.'); await refresh(); } catch (error) { setStatus(error.message); }
  };

  const createAutomation = async () => {
    const name = window.prompt('Automation name', 'Index and notify on upload')?.trim(); if (!name) return;
    try { await ragApiRequest('/api/automations', { method: 'POST', body: JSON.stringify({ name, actions: ['auto_index', 'notify'] }) }); setStatus('Automation created.'); await refresh(); } catch (error) { setStatus(error.message); }
  };

  const createPrompt = async () => {
    const title = window.prompt('Template name')?.trim(); if (!title) return;
    const text = window.prompt('Grounded prompt text')?.trim(); if (!text) return;
    try { await ragApiRequest('/api/prompts', { method: 'POST', body: JSON.stringify({ title, text }) }); setStatus('Prompt template saved.'); await refresh(); } catch (error) { setStatus(error.message); }
  };

  const exploreSources = async () => {
    if (!explorerQuery.trim()) return;
    try { const data = await ragApiRequest('/api/source-explorer', { method: 'POST', body: JSON.stringify({ query: explorerQuery }) }); setSourceChunks(data.chunks || []); } catch (error) { setStatus(error.message); }
  };

  return <section className="advanced-panel" aria-label="Advanced workspace">
    <div className="document-manager-header"><div><span>Advanced</span><strong>AI workspace</strong></div><button className="icon-button" type="button" onClick={onClose}>×</button></div>
    <label className="checkbox-field"><input type="checkbox" checked={privacyMode} onChange={(event) => setPrivacyMode(event.target.checked)} /> Privacy mode: route new requests locally</label>
    <div className="advanced-section"><strong><BrainCircuit size={15} /> Long-term memory</strong><textarea aria-label="Long-term memory" value={memory} onChange={(event) => setMemory(event.target.value)} placeholder="One preference or fact per line" rows={3} /><button className="secondary-button" type="button" onClick={saveMemory}><Save size={14} /> Save memory</button></div>
    <div className="advanced-section"><strong><Calculator size={15} /> Controlled agent</strong><input aria-label="Agent goal" value={agentQuestion} onChange={(event) => setAgentQuestion(event.target.value)} placeholder="Goal (optional)" /><input aria-label="Approved calculation" value={expression} onChange={(event) => setExpression(event.target.value)} placeholder="Approved calculation, e.g. (12 * 9) / 3" /><button className="secondary-button" type="button" onClick={runAgent}>Plan / execute</button><button className="secondary-button" type="button" onClick={compareDocuments}>Compare documents</button><button className="secondary-button" type="button" onClick={generateReport}>Generate cited report</button></div>
    <div className="advanced-section"><strong><Network size={15} /> Knowledge graph</strong><small>{graph.nodes?.length || 0} entities indexed</small><KnowledgeGraph graph={graph} /></div>
    <div className="advanced-section"><strong>Source quality</strong><small>{quality.freshness?.length || 0} tracked source version(s) · {quality.duplicate_sources?.length || 0} duplicate-name warning(s)</small></div>
    <div className="advanced-section"><strong><Users size={15} /> Shared workspaces</strong><button className="secondary-button" type="button" onClick={createWorkspace}>Create workspace</button>{workspaces.map((workspace) => <div className="workspace-row" key={workspace.id}><small>{workspace.name} · {Object.keys(workspace.members).length} member(s) · {workspace.comments.length} comment(s) · {Object.keys(activity[workspace.id]?.presence || {}).length} active</small><button type="button" onClick={() => onWorkspaceSelect?.(workspace)}>Use in chat</button><button type="button" onClick={() => inviteMember(workspace)}>Invite</button><button type="button" onClick={() => addComment(workspace)}>Comment</button><button type="button" onClick={() => shareDocument(workspace)}>Share doc</button></div>)}</div>
    <div className="advanced-section"><strong>Automations</strong><button className="secondary-button" type="button" onClick={createAutomation}>Create upload automation</button><small>{automations.length} automation(s) configured</small></div>
    <div className="advanced-section"><strong>Prompt library</strong><button className="secondary-button" type="button" onClick={createPrompt}>Save prompt template</button>{prompts.map((prompt) => <button className="prompt-template" type="button" key={prompt.id} onClick={() => onPromptSelected?.(prompt.text)}>{prompt.title}</button>)}</div>
    <div className="advanced-section"><strong>Source explorer</strong><input aria-label="Search indexed sources" value={explorerQuery} onChange={(event) => setExplorerQuery(event.target.value)} placeholder="Search indexed source passages" /><button className="secondary-button" type="button" onClick={exploreSources}>Inspect retrieved sources</button>{sourceChunks.map((chunk) => <small className="source-explorer" key={chunk.chunk_id}><strong>{chunk.source}</strong> · {Math.round(chunk.score * 100)}%<br />{chunk.excerpt}</small>)}</div>
    {status ? <p className="document-status" role="status">{status}</p> : null}
  </section>;
}
