import { useState } from 'react';
import { Search } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, useResource } from '../api';
import { Badge, Empty, ErrorBox, fmt, Loading, Panel, statusLabels } from '../components';
import type { HistoryRow, Machine, Prediction, Status } from '../types';

export function Machines({ resource, sessionId, selected, onSelect }: {
  resource: { data: Machine[] | null; error: string; loading: boolean; reload: () => void };
  sessionId?: number; selected: string | null; onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const selectedId = selected || 'CNC-001';
  const history = useResource<HistoryRow[]>(`/machines/${selectedId}/readings${sessionId ? `?session_id=${sessionId}` : ''}`, 3000);
  const machine = resource.data?.find(m => m.id === selectedId);
  const filtered = resource.data?.filter(m => `${m.id} ${m.name} ${m.area}`.toLowerCase().includes(query.toLowerCase()) &&
    (status === 'all' || (m.prediction?.status || 'empty') === status)) || [];
  return <div className="machines-layout"><Panel title="Directorio de máquinas" subtitle="50 identidades virtuales">
    <div className="filters"><label className="search"><Search size={16} /><input aria-label="Buscar máquina" placeholder="Buscar máquina o zona…" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <select aria-label="Filtrar por estado" value={status} onChange={e => setStatus(e.target.value)}><option value="all">Todos los estados</option>
        {Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}<option value="empty">Sin datos</option></select></div>
    {resource.error && <ErrorBox message={resource.error} retry={resource.reload} />}
    {resource.loading ? <Loading /> : !filtered.length ? <Empty title="Sin coincidencias" text="Prueba otro nombre o elimina el filtro de estado." /> :
      <div className="machine-list">{filtered.map(m => <button key={m.id} className={`machine-row ${m.id === selectedId ? 'selected' : ''}`} onClick={() => onSelect(m.id)}>
        <span><strong>{m.id}</strong><small>{m.area}</small></span>{m.prediction ? <Badge status={m.prediction.status} /> : <span className="muted">Sin datos</span>}</button>)}</div>}
  </Panel><div className="detail-column"><Panel title={selectedId} subtitle={machine?.name || 'Detalle de máquina'}
    action={machine?.prediction && <Badge status={machine.prediction.status} />}>
    {!machine?.prediction ? <Empty title="Esperando la primera lectura" text="Reproduce la demo para analizar este equipo virtual." /> : <>
      <div className="score-row"><div><small>Score de clasificación</small><strong>{fmt(machine.prediction.failure_score)}</strong></div>
        <div><small>Score de anomalía</small><strong>{fmt(machine.prediction.anomaly_score)}</strong></div></div>
      <p className="explanation">{machine.prediction.explanation}</p><div className="recommendation">{machine.prediction.recommended_action}</div>
      <dl className="sensor-grid">{Object.entries(machine.reading || {}).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
      <p className="caption">UDI {machine.source_udi} · Paso simulado {machine.step} · Estado actual, sin horizonte futuro.</p></>}
  </Panel><Panel title="Historial de observación" subtitle="Eje horizontal: paso simulado, no tiempo del dataset">
    {history.error ? <ErrorBox message={history.error} retry={history.reload} /> : !history.data?.length ? <Empty title="Todavía no hay historial" text="Las lecturas de cada sesión quedan almacenadas localmente." /> :
      <div className="chart" role="img" aria-label="Historial del score de clasificación"><ResponsiveContainer width="100%" height="100%">
        <LineChart data={history.data.map(r => ({ step: r.step, score: r.prediction.failure_score }))}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="step" /><YAxis domain={[0, 1]} /><Tooltip />
          <Line dataKey="score" name="Score" stroke="#137869" strokeWidth={2} dot={false} connectNulls={false} /></LineChart></ResponsiveContainer></div>}
  </Panel><ManualReading key={`${selectedId}-${sessionId}`} initial={machine} /></div></div>;
}

const fields = [
  ['air_temperature_k', 'Temperatura del aire · K', 298.1, 'Air temperature [K]'],
  ['process_temperature_k', 'Temperatura del proceso · K', 308.6, 'Process temperature [K]'],
  ['rotational_speed_rpm', 'Velocidad · rpm', 1551, 'Rotational speed [rpm]'],
  ['torque_nm', 'Par · Nm', 42.8, 'Torque [Nm]'],
  ['tool_wear_min', 'Uso de herramienta · min', 0, 'Tool wear [min]'],
] as const;

function ManualReading({ initial }: { initial?: Machine }) {
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(form: HTMLFormElement) {
    const data = new FormData(form);
    const payload = { product_type: data.get('product_type'), ...Object.fromEntries(fields.map(([key]) => [key, Number(data.get(key))])) };
    setBusy(true); setError(''); setResult(null);
    try { setResult(await api<Prediction>('/predictions/ai4i', 'POST', payload)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Panel title="Analizar una lectura" subtitle="Consulta independiente; no modifica el estado de la máquina">
    <form onSubmit={e => { e.preventDefault(); void submit(e.currentTarget); }}><div className="form-grid">
      <label>Tipo de producto<select name="product_type" defaultValue={String(initial?.reading?.Type || 'L')}><option>L</option><option>M</option><option>H</option></select></label>
      {fields.map(([key, label, value, source]) => <label key={key}>{label}<input name={key} required type="number" step="any" min={key === 'tool_wear_min' ? 0 : 0.001}
        defaultValue={Number(initial?.reading?.[source] ?? value)} /></label>)}</div>
      <button className="primary" disabled={busy}>{busy ? 'Analizando…' : 'Analizar y guardar'}</button></form>
    {error && <ErrorBox message={error} />}{result && <div className="manual-result"><Badge status={result.status as Status} /><p>{result.explanation}</p><p>{result.recommended_action}</p></div>}
  </Panel>;
}
