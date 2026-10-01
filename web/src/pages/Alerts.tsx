import { useState } from 'react';
import { Check, CheckCheck, MessageSquare } from 'lucide-react';
import { api, useResource } from '../api';
import { Badge, Empty, ErrorBox, Loading, Panel } from '../components';
import type { Alert } from '../types';

export function Alerts({ sessionId, onMachine }: { sessionId?: number; onMachine: (id: string) => void }) {
  const resource = useResource<Alert[]>(`/alerts${sessionId ? `?session_id=${sessionId}` : ''}`, 4000);
  const [show, setShow] = useState('pending');
  const visible = resource.data?.filter(a => show === 'all' || (show === 'pending' ? !a.acknowledged_at : !!a.acknowledged_at));
  return <Panel title="Centro de alertas" subtitle="Últimas 200 alertas de la sesión · Reconocer no implica resolver una avería"
    action={<select aria-label="Filtrar alertas" value={show} onChange={e => setShow(e.target.value)}><option value="pending">Pendientes</option><option value="acknowledged">Reconocidas</option><option value="all">Todas</option></select>}>
    {resource.error ? <ErrorBox message={resource.error} retry={resource.reload} /> : resource.loading ? <Loading /> :
      !visible?.length ? <Empty title="No hay alertas en esta vista" text="Las lecturas que requieren atención aparecerán aquí durante la demo." /> :
        <div className="alerts-list">{visible.map(alert => <AlertCard key={alert.id} alert={alert} reload={resource.reload} onMachine={onMachine} />)}</div>}
  </Panel>;
}

function AlertCard({ alert, reload, onMachine }: { alert: Alert; reload: () => void; onMachine: (id: string) => void }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function action(type: 'acknowledge' | 'notes') {
    setBusy(true); setError('');
    try { await api(`/alerts/${alert.id}/${type}`, 'POST', type === 'notes' ? { body: note } : undefined); setNote(''); reload(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <article className="alert-card"><div className="alert-top"><div><span className="tiny-label">ALERTA #{alert.id} · SESIÓN {alert.session_id}</span>
    <button className="machine-link" onClick={() => onMachine(alert.machine_id)}>{alert.machine_id}</button></div><Badge status={alert.status} /></div>
    <p>{alert.prediction.explanation}</p><div className="recommendation">{alert.prediction.recommended_action}</div>
    <div className="alert-meta"><span>{new Date(alert.created_at).toLocaleString('es-ES')} · Hora de la demo</span>
      {alert.acknowledged_at ? <span className="recognized"><CheckCheck size={16} /> Reconocida</span> : <button disabled={busy} onClick={() => void action('acknowledge')}><Check size={16} /> Reconocer alerta</button>}</div>
    {alert.notes.map(n => <div className="note" key={n.id}><MessageSquare size={15} />{n.body}</div>)}
    <form className="note-form" onSubmit={e => { e.preventDefault(); void action('notes'); }}><input value={note} maxLength={2000} required
      aria-label={`Nota para alerta ${alert.id}`} placeholder="Añadir una nota de mantenimiento…" onChange={e => setNote(e.target.value)} />
      <button disabled={busy || !note.trim()} type="submit">Guardar nota</button></form>{error && <ErrorBox message={error} />}</article>;
}
