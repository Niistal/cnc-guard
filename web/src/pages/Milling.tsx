import { useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, useResource } from '../api';
import { Empty, ErrorBox, fmt, Loading, Metric, Panel } from '../components';
import type { MillingResult, MillingRun } from '../types';

export function Milling() {
  const cases = useResource<{ case: number; runs: number; labeled: number }[]>('/milling/cases');
  const [caseId, setCaseId] = useState(1);
  return <><div className="notice"><strong>Datos de ensayos reales · NASA / BEST Lab, UC Berkeley</strong>
    <p>Estimación del desgaste observado. Estos ensayos no representan las 50 máquinas virtuales de la demo.</p></div>
    {cases.error ? <ErrorBox message={cases.error} retry={cases.reload} /> : cases.loading ? <Loading /> : <>
      <div className="metrics-grid three"><Metric label="Ensayos disponibles" value={cases.data?.length || 0} foot="Grupos separados en la evaluación" />
        <Metric label="Ejecuciones registradas" value={cases.data?.reduce((n, c) => n + c.runs, 0) || 0} foot="Seis señales por ejecución" />
        <Metric label="Mediciones de desgaste" value={cases.data?.reduce((n, c) => n + c.labeled, 0) || 0} foot="Las etiquetas ausentes no se rellenan" accent /></div>
      <div className="case-picker"><label>Ensayo <select value={caseId} onChange={e => setCaseId(Number(e.target.value))}>
        {cases.data?.map(c => <option value={c.case} key={c.case}>Ensayo {c.case.toString().padStart(2, '0')} · {c.runs} ejecuciones</option>)}</select></label>
        <span>Se conservan las condiciones y el orden de cada ensayo.</span></div><CaseDetail key={caseId} caseId={caseId} /></>}
  </>;
}

function CaseDetail({ caseId }: { caseId: number }) {
  const runs = useResource<MillingRun[]>(`/milling/cases/${caseId}`);
  const [run, setRun] = useState(1);
  const [signal, setSignal] = useState('vib_spindle');
  const [result, setResult] = useState<MillingResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const signals = useResource<{ sample_count: number; points: Record<string, number>[] }>(`/milling/cases/${caseId}/runs/${run}/signals`);
  async function estimate() {
    setError(''); setResult(null); setBusy(true);
    try { setResult(await api<MillingResult>('/predictions/milling', 'POST', { case: caseId, run })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  if (runs.error) return <ErrorBox message={runs.error} retry={runs.reload} />;
  if (runs.loading) return <Loading />;
  return <><Panel title={`Desgaste de herramienta · Ensayo ${caseId}`} subtitle={`Partición: ${runs.data?.[0]?.partition || '—'} · VB en milímetros`}>
    <p className="caption">La curva estimada muestra el resultado bruto del modelo para análisis, incluso fuera de dominio. La consulta operativa se abstiene en esos casos.</p>
    <div className="chart tall" role="img" aria-label="Desgaste observado y estimado por ejecución"><ResponsiveContainer width="100%" height="100%"><LineChart data={runs.data || []}>
      <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="run" /><YAxis /><Tooltip /><Legend />
      <Line dataKey="VB" name="VB observado · mm" stroke="#172624" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
      <Line dataKey="predicted_vb" name="VB estimado bruto · mm" stroke="#137869" strokeWidth={2} strokeDasharray="5 5" dot={false} /></LineChart></ResponsiveContainer></div>
    <div className="table-wrap"><table><thead><tr><th>Ejecución</th><th>VB observado</th><th>Estimación bruta</th><th>Dominio</th></tr></thead><tbody>{runs.data?.map(r =>
      <tr key={r.run}><td>{r.run}</td><td>{fmt(r.VB)} mm</td><td>{fmt(r.predicted_vb)} mm</td><td>{r.in_domain ? 'Dentro' : 'Fuera · abstención operativa'}</td></tr>)}</tbody></table></div>
  </Panel><div className="two-columns"><Panel title="Explorador de señales" subtitle="Se muestran hasta 300 muestras de la señal original">
    <div className="filters"><label>Ejecución<select value={run} onChange={e => { setRun(Number(e.target.value)); setResult(null); }}>
      {runs.data?.map(r => <option key={r.run} value={r.run}>{r.run}</option>)}</select></label><label>Señal<select value={signal} onChange={e => setSignal(e.target.value)}>
      {['smcAC', 'smcDC', 'vib_table', 'vib_spindle', 'AE_table', 'AE_spindle'].map(s => <option key={s}>{s}</option>)}</select></label></div>
    {signals.error ? <ErrorBox message={signals.error} retry={signals.reload} /> : signals.loading ? <Loading /> :
      <div className="chart" role="img" aria-label={`Señal ${signal}, índice de muestra`}><ResponsiveContainer width="100%" height="100%"><LineChart data={signals.data?.points || []}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="sample" /><YAxis /><Tooltip /><Line dataKey={signal} stroke="#137869" dot={false} /></LineChart></ResponsiveContainer></div>}
    <p className="caption">Eje X: índice de muestra. Amplitud en unidades de adquisición, sin calibración física aplicada. {signals.data?.sample_count || 0} muestras originales.</p>
  </Panel><Panel title="Consultar el modelo" subtitle={`Ensayo ${caseId} · Ejecución ${run}`}><p>Analiza las señales de esta ejecución y guarda una estimación de desgaste en el historial local.</p>
    <button className="primary" disabled={busy} onClick={() => void estimate()}>{busy ? 'Estimando…' : 'Estimar desgaste'}</button>
    {error && <ErrorBox message={error} />}{result ? <div className="wear-result"><strong>{result.estimated_wear == null ? 'Sin estimación' : `${fmt(result.estimated_wear)} mm`}</strong>
      <p>{result.explanation}</p><span className="tiny-label">{result.data_quality_status}</span></div> : <Empty title="Consulta consultiva" text="No se calcula vida útil restante ni fecha de avería." />}</Panel></div></>;
}
