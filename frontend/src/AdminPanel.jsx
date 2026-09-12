import { useEffect, useState } from 'react';
import { AlertTriangle, Boxes, Gauge, Play, ShieldCheck } from 'lucide-react';
import { ragApiRequest } from './api';

function TimelineChart({ label, data, valueKey, format }) {
  const max = Math.max(1, ...data.map((day) => day[valueKey]));
  return (
    <div className="admin-chart" role="img" aria-label={`${label}: ${data.map((day) => `${day.date} ${day[valueKey]}`).join(', ')}`}>
      <strong>{label}</strong>
      <div className="admin-chart-bars">
        {data.map((day) => (
          <div className="admin-chart-col" key={day.date} title={`${day.date}: ${format(day[valueKey])}`}>
            <div className="admin-chart-bar" style={{ height: `${Math.max(4, Math.round((day[valueKey] / max) * 100))}%` }} />
            <small>{day.date.slice(8)}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AdminPanel({ onClose }) {
  const [accounts, setAccounts] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [chroma, setChroma] = useState(null);
  const [quotas, setQuotas] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [runStatus, setRunStatus] = useState('');
  const [status, setStatus] = useState('Loading audit overview…');

  useEffect(() => {
    Promise.all([
      ragApiRequest('/api/admin/overview'),
      ragApiRequest('/api/admin/metrics'),
      ragApiRequest('/api/admin/metrics/timeline?days=14'),
      ragApiRequest('/api/admin/evaluation'),
      ragApiRequest('/api/admin/chroma'),
      ragApiRequest('/api/admin/quotas'),
      ragApiRequest('/api/admin/anomalies?days=30'),
    ])
      .then(([overview, metricData, timelineData, evaluationData, chromaData, quotaData, anomalyData]) => {
        setAccounts(overview.accounts || []);
        setMetrics(metricData);
        setTimeline(timelineData.days || []);
        setEvaluation(evaluationData);
        setChroma(chromaData);
        setQuotas(quotaData);
        setAnomalies(anomalyData.anomalies || []);
        setStatus('');
      })
      .catch((error) => setStatus(error.message));
  }, []);

  const runEvaluation = async () => {
    const accountId = accounts[0]?.account_id;
    if (!accountId) { setRunStatus('Upload and index documents before running retrieval evaluation.'); return; }
    setRunStatus('Running retrieval evaluation…');
    try {
      const result = await ragApiRequest(`/api/admin/evaluation/run?account_id=${encodeURIComponent(accountId)}`, { method: 'POST' });
      const prior = result.history?.[1];
      const regression = prior ? ` Previous run: ${prior.passed}/${prior.total}.` : '';
      setRunStatus(`Retrieval evaluation: ${result.passed}/${result.total} checks passed for account ${accountId}.${regression}`);
    } catch (error) {
      setRunStatus(error.message);
    }
  };

  return (
    <section className="document-manager" aria-label="Administrator overview">
      <div className="document-manager-header"><div><span>Administrator</span><strong>Document audit</strong></div><button className="icon-button" type="button" onClick={onClose}>×</button></div>
      {status ? <p className="document-status">{status}</p> : null}
      {anomalies.length ? (
        <div className="anomaly-alerts">
          <strong><AlertTriangle size={14} /> Anomaly alerts</strong>
          {anomalies.map((anomaly, index) => (
            <p key={`${anomaly.type}-${index}`}>{anomaly.detail}</p>
          ))}
        </div>
      ) : null}
      {metrics ? <div className="admin-metrics"><span>{metrics.answers} answers</span><span>{metrics.average_latency_ms} ms avg.</span><span>{Math.round(metrics.average_confidence * 100)}% confidence</span></div> : null}
      {timeline.length ? (
        <div className="admin-charts">
          <TimelineChart label="Answers per day" data={timeline} valueKey="answers" format={(value) => `${value} answers`} />
          <TimelineChart label="Avg. latency (ms) per day" data={timeline} valueKey="average_latency_ms" format={(value) => `${value} ms`} />
        </div>
      ) : null}
      {chroma ? (
        <div className="admin-chroma">
          <strong><Boxes size={14} /> Vector stores (Chroma)</strong>
          {chroma.connected ? (
            <>
              <div className="admin-metrics"><span>{chroma.total_chunks} chunks total</span><span>{(chroma.directory_size_bytes / (1024 * 1024)).toFixed(1)} MB on disk</span></div>
              {chroma.collections.length ? <div className="chroma-collections">{chroma.collections.map((collection) => <span key={collection.name} className="chroma-chip">{collection.name.replace(/^ai_chatbot_knowledge_base_/, '')}: {collection.chunks}</span>)}</div> : <p className="document-status">No collections found.</p>}
            </>
          ) : <p className="document-status">Chroma unavailable: {chroma.error}</p>}
        </div>
      ) : null}
      {quotas ? (
        <div className="admin-chroma">
          <strong><Gauge size={14} /> Rate limits</strong>
          <div className="admin-metrics"><span>{quotas.limit} requests / {quotas.window_seconds}s per account</span><span>{quotas.accounts.length} account(s) with activity</span></div>
          {quotas.accounts.length ? (
            <div className="quota-account-chips">
              {quotas.accounts.map((account) => {
                const used = account.active_requests / quotas.limit;
                return (
                  <span className={`quota-chip ${used >= 0.8 ? 'quota-chip-hot' : ''}`} key={account.account_id}>
                    Account {account.account_id}: {account.remaining} remaining
                    <span className="quota-bar"><span className="quota-bar-fill" style={{ width: `${Math.min(100, Math.round(used * 100))}%` }} /></span>
                  </span>
                );
              })}
            </div>
          ) : <p className="document-status">No active accounts in this window.</p>}
        </div>
      ) : null}
      {evaluation ? <p className="document-status">Evaluation: {evaluation.total_cases} cases · security guards {evaluation.guard_passed}/{evaluation.guard_total}</p> : null}
      <button className="secondary-button" type="button" onClick={runEvaluation}><Play size={14} /> Run retrieval evaluation</button>
      {runStatus ? <p className="document-status">{runStatus}</p> : null}
      {metrics?.failed_reviews?.length ? <div className="review-queue"><strong>Needs review</strong>{metrics.failed_reviews.map((item, index) => <p key={`${item.message_id}-${index}`}>Q: {item.question}<br />A: {item.response}</p>)}</div> : null}
      {metrics?.weak_queries?.length ? (
        <div className="weak-queries">
          <strong>Low-confidence queries — consider adding documents</strong>
          {metrics.weak_queries.map((query, index) => <p key={`${query}-${index}`}>“{query}”</p>)}
        </div>
      ) : null}
      <div className="document-list">
        {accounts.map((account) => (
          <div className="admin-account" key={account.account_id}>
            <strong><ShieldCheck size={14} /> Account {account.account_id}</strong>
            <small>{account.documents.length} document(s) · {account.events[0]?.action || 'No activity yet'}</small>
          </div>
        ))}
      </div>
    </section>
  );
}