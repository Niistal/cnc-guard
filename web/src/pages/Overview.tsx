import { ArrowRight, CircleDot, Cpu, ScanLine } from 'lucide-react';
import { Badge, Empty, ErrorBox, Loading, Metric, Panel } from '../components';
import type { Machine, Session, Status } from '../types';

export function Overview({ machines, session, onMachine }: {
  machines: { data: Machine[] | null; loading: boolean; error: string; reload: () => void };
  session?: Session; onMachine: (id: string) => void;
}) {
  if (machines.error) return <ErrorBox message={machines.error} retry={machines.reload} />;
  if (machines.loading) return <Loading />;
  const data = machines.data || [];
  const count = (s: Status) => data.filter(m => m.prediction?.status === s).length;
  const withData = data.filter(m => m.prediction);
  const priority = [...withData].sort((a, b) => (b.prediction?.failure_score ?? -1) - (a.prediction?.failure_score ?? -1)).slice(0, 5);
  return <><div className="metrics-grid">
    <Metric label="Máquinas en la demo" value={data.length} foot={`${withData.length} con lectura disponible`} />
    <Metric label="Estado normal" value={count('NORMAL')} foot="Según la última lectura válida" accent />
    <Metric label="Requieren revisión" value={count('WARNING') + count('CRITICAL')} foot={`${count('CRITICAL')} de prioridad alta`} />
    <Metric label="Cobertura de inferencia" value={withData.length ? `${Math.round((withData.length - count('UNKNOWN')) / withData.length * 100)}%` : '—'}
      foot={`${count('UNKNOWN')} lecturas fuera del dominio`} />
  </div><div className="overview-grid"><Panel title="Mapa de planta" subtitle="Distribución virtual · Lecturas reproducidas de AI4I"
      action={<span className="tiny-label"><CircleDot size={14} />{session?.state === 'running' ? 'En reproducción' : 'En pausa'}</span>}>
      <div className="floor-plan">{['Fresado', 'Torneado', 'Acabado'].map(area => <div className="floor-zone" key={area}>
        <div className="zone-title"><span>{area}</span><small>{data.filter(m => m.area === area).length} EQUIPOS</small></div>
        <div className="machine-grid">{data.filter(m => m.area === area).map(m => <button key={m.id}
          className={`machine-tile ${m.prediction?.status.toLowerCase() || 'idle'}`} onClick={() => onMachine(m.id)}
          aria-label={`${m.id}: ${m.prediction?.status || 'sin datos'}`}><Cpu size={23} /><span>{m.id.slice(4)}</span>
          <span className="tile-state" /></button>)}</div></div>)}</div>
      <div className="map-legend"><Badge status="NORMAL" /><Badge status="WARNING" /><Badge status="CRITICAL" /><Badge status="UNKNOWN" /></div>
    </Panel><div className="overview-side"><section className="insight-card"><ScanLine size={28} /><p className="eyebrow">UNA LECTURA, DOS PERSPECTIVAS</p>
      <h2>Condición de máquina.<br />Comportamiento inusual.</h2><p>Combinamos clasificación y detección de anomalías para orientar la revisión de cada lectura.</p>
      <div className="insight-divider" /><span>Los resultados son consultivos.<br />No predicen una fecha de avería.</span></section>
      <Panel title="Esta sesión" subtitle="Reloj y máquinas simulados"><dl className="details-list"><div><dt>Sesión</dt><dd>{session ? `#${session.id}` : 'Sin iniciar'}</dd></div>
        <div><dt>Lecturas procesadas</dt><dd>{session?.cursor ?? 0}</dd></div><div><dt>Dataset</dt><dd>UCI · AI4I 2020</dd></div>
        <div><dt>Naturaleza</dt><dd>Sintético</dd></div></dl></Panel></div></div>
    <Panel title="Prioridad de observación" subtitle="Últimas lecturas ordenadas por score del clasificador">
      {!priority.length ? <Empty title="La planta está lista" text="Reproduce la demo para consultar las primeras 50 lecturas." /> :
        <div className="table-wrap"><table><thead><tr><th>Máquina</th><th>Zona virtual</th><th>Estado</th><th>Score de fallo</th><th>Origen</th><th>Detalle</th></tr></thead>
          <tbody>{priority.map(m => <tr key={m.id}><td><strong>{m.id}</strong></td><td>{m.area}</td><td><Badge status={m.prediction!.status} /></td>
            <td>{m.prediction!.failure_score?.toFixed(3) ?? 'Abstención'}</td><td>UDI {m.source_udi}</td><td><button className="text-button" onClick={() => onMachine(m.id)} aria-label={`Ver ${m.id}`}><ArrowRight size={18} /></button></td></tr>)}</tbody></table></div>}
    </Panel></>;
}
