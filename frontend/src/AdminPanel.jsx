import { useEffect, useState } from 'react';
import { Play, ShieldCheck } from 'lucide-react';
import { ragApiRequest } from './api';

export default function AdminPanel({ onClose }) {
  const [accounts, setAccounts] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [runStatus, setRunStatus] = useState('');
  const [status, setStatus] = useState('Loading audit overview…');

  useEffect(() => {
    Promise.all([ragApiRequest('/api/admin/overview'), ragApiRequest('/api/admin/metrics'), ragApiRequest('/api/admin/evaluation')])
      .then(([overview, metricData, evaluationData]) => { setAccounts(overview.accounts || []); setMetrics(metricData); setEvaluation(evaluationData); setStatus(''); })
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
      {metrics ? <div className="admin-metrics"><span>{metrics.answers} answers</span><span>{metrics.average_latency_ms} ms avg.</span><span>{Math.round(metrics.average_confidence * 100)}% confidence</span></div> : null}
      {evaluation ? <p className="document-status">Evaluation: {evaluation.total_cases} cases · security guards {evaluation.guard_passed}/{evaluation.guard_total}</p> : null}
      <button className="secondary-button" type="button" onClick={runEvaluation}><Play size={14} /> Run retrieval evaluation</button>
      {runStatus ? <p className="document-status">{runStatus}</p> : null}
      {metrics?.failed_reviews?.length ? <div className="review-queue"><strong>Needs review</strong>{metrics.failed_reviews.map((item, index) => <p key={`${item.message_id}-${index}`}>Q: {item.question}<br />A: {item.response}</p>)}</div> : null}
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
