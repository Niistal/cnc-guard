import { useEffect, useRef, useState } from 'react';
import { Activity, Bell, ChartNoAxesCombined, ChevronRight, CircleHelp, Cpu,
  FlaskConical, LayoutDashboard, Pause, Play, RotateCcw, ShieldCheck } from 'lucide-react';
import { api, useResource } from './api';
import { ErrorBox } from './components';
import type { Health, Machine, Session } from './types';
import { Overview } from './pages/Overview';
import { Machines } from './pages/Machines';
import { Alerts } from './pages/Alerts';
import { Milling } from './pages/Milling';
import { Evaluations } from './pages/Evaluations';

const navigation = [
  { id: 'overview', label: 'Resumen de planta', icon: LayoutDashboard, section: 'Operación' },
  { id: 'machines', label: 'Máquinas', icon: Cpu },
  { id: 'alerts', label: 'Alertas', icon: Bell },
  { id: 'milling', label: 'Laboratorio de desgaste', icon: FlaskConical, section: 'Inteligencia' },
  { id: 'evaluation', label: 'Evaluación', icon: ChartNoAxesCombined },
];

export default function App() {
  const [page, setPage] = useState(window.location.hash.slice(1) || 'overview');
  const [selectedMachine, setSelectedMachine] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const sessions = useResource<Session[]>('/sessions', 3000);
  const health = useResource<Health>('/health', 10000);
  const current = sessions.data?.[0];
  const viewedSession = selectedSession ?? current?.id;
  const machines = useResource<Machine[]>(`/machines${viewedSession ? `?session_id=${viewedSession}` : ''}`, 3000);
  const viewed = sessions.data?.find(s => s.id === viewedSession);
  const activePage = navigation.find(n => n.id === page) || navigation[0];
  useEffect(() => { const handler = () => setPage(window.location.hash.slice(1) || 'overview');
    window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler); }, []);
  useEffect(() => { heading.current?.focus(); }, [page]);

  function navigate(id: string) { setPage(id); window.location.hash = id; }
  function openMachine(id: string) { setSelectedMachine(id); navigate('machines'); }
  async function control(action: 'play' | 'pause' | 'restart') {
    setBusy(true); setActionError('');
    try {
      if (action === 'restart' || !current) {
        const created = await api<Session>('/sessions', 'POST');
        setSelectedSession(created.id);
        if (action === 'play') await api(`/sessions/${created.id}`, 'PATCH', { action: 'play' });
      } else { await api(`/sessions/${current.id}`, 'PATCH', { action }); setSelectedSession(current.id); }
      sessions.reload(); machines.reload();
    } catch (e) { setActionError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <div className="shell">
    <a className="skip-link" href="#main">Saltar al contenido</a>
    <aside className="sidebar">
      <a className="brand" href="#overview" onClick={() => navigate('overview')}><span className="brand-mark"><ShieldCheck size={25} /></span>
        <span>CNC<span className="brand-light">Guard</span><small>MAINTENANCE INTELLIGENCE</small></span></a>
      <div className="workspace-label"><span className="workspace-icon">A</span><div>ARAKAIN Makineria<small>Bilbao · Entorno académico</small></div></div>
      <nav aria-label="Navegación principal">{navigation.map(item => <div key={item.id}>
        {item.section && <p className="nav-section">{item.section}</p>}
        <a href={`#${item.id}`} onClick={() => navigate(item.id)} aria-current={activePage.id === item.id ? 'page' : undefined}
          className={activePage.id === item.id ? 'nav-item active' : 'nav-item'}><item.icon size={19} />{item.label}
          {activePage.id === item.id && <ChevronRight className="nav-chevron" size={16} />}</a></div>)}</nav>
      <div className="sidebar-bottom"><div className="local-tag"><span />Ejecución local</div><p>La inteligencia recomienda.<br />Las personas deciden.</p>
        <a href="/docs" target="_blank" rel="noreferrer"><CircleHelp size={16} /> Documentación API</a>
        <div className="project-tag">ERRONKA 1 <span>2026</span></div></div>
    </aside>
    <div className="workspace"><header className="topbar"><div><span className="breadcrumb">Centro de mantenimiento</span><ChevronRight size={14} />
      <span>{activePage.label}</span></div><span className="demo-tag"><Activity size={14} /> DEMO ACADÉMICA</span></header>
      <main id="main"><div className="page-heading"><div><p className="eyebrow">ARAKAIN / CNC GUARD</p>
        <h1 ref={heading} tabIndex={-1}>{activePage.label}</h1><p className="page-subtitle">{page === 'milling'
          ? 'Del ensayo de fresado a una estimación de desgaste.' : page === 'evaluation'
            ? 'Resultados medidos. Decisiones que puedes explicar.' : 'Una visión clara para cada decisión de mantenimiento.'}</p></div>
        <div className="session-controls"><button disabled={busy || !health.data?.models.ai4i.ready}
          className="primary" onClick={() => void control(current?.state === 'running' ? 'pause' : 'play')}>
          {current?.state === 'running' ? <Pause size={16} /> : <Play size={16} />}
          {busy ? 'Preparando…' : current?.state === 'running' ? 'Pausar demo' : 'Reproducir demo'}</button>
          <button disabled={busy || !health.data?.models.ai4i.ready} title="Nueva sesión; conserva las anteriores"
            onClick={() => void control('restart')}><RotateCcw size={16} /> Nueva sesión</button></div></div>
        <div className="context-strip"><span><ShieldCheck size={16} />50 identidades virtuales · Sin conexión a maquinaria</span>
          <label>Sesión <select aria-label="Sesión de demostración" value={viewedSession ?? ''}
            onChange={e => setSelectedSession(Number(e.target.value))}>
            {!sessions.data?.length && <option value="">Sin iniciar</option>}
            {sessions.data?.map(s => <option key={s.id} value={s.id}>#{s.id} · {s.state === 'running' ? 'En reproducción' : s.state === 'archived' ? 'Archivada' : 'Pausada'}</option>)}</select></label></div>
        {(actionError || sessions.error || health.error) && <ErrorBox message={actionError || sessions.error || health.error} retry={() => { sessions.reload(); health.reload(); setActionError(''); }} />}
        {current?.error && <ErrorBox message={`Sesión detenida: ${current.error}`} />}
        {health.data && !health.data.models.ai4i.ready && <div className="setup-banner"><strong>El modelo todavía no está disponible.</strong>
          <span>Ejecuta el paso «Preparar datos» del inicio rápido para habilitar la demostración.</span></div>}
        {activePage.id === 'overview' && <Overview machines={machines} session={viewed} onMachine={openMachine} />}
        {activePage.id === 'machines' && <Machines resource={machines} sessionId={viewedSession} selected={selectedMachine} onSelect={setSelectedMachine} />}
        {activePage.id === 'alerts' && <Alerts sessionId={viewedSession} onMachine={openMachine} />}
        {activePage.id === 'milling' && <Milling />}
        {activePage.id === 'evaluation' && <Evaluations />}
        <footer className="footer"><span>CNC Guard · Erronka 1</span><span>Datos con procedencia · Decisiones con contexto</span></footer>
      </main></div>
  </div>;
}
