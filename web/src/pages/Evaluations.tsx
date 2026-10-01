import { useState } from 'react';
import { Download } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useResource } from '../api';
import { ErrorBox, fmt, Loading, Metric, Panel } from '../components';
import type { Evaluation } from '../types';

export function Evaluations() {
  const [dataset, setDataset] = useState<'ai4i' | 'nasa'>('ai4i');
  return <><div className="tabs" role="group" aria-label="Dataset de evaluación"><button className={dataset === 'ai4i' ? 'selected' : ''} onClick={() => setDataset('ai4i')}>AI4I · Clasificación</button>
    <button className={dataset === 'nasa' ? 'selected' : ''} onClick={() => setDataset('nasa')}>NASA · Desgaste</button></div><EvaluationView key={dataset} dataset={dataset} /></>;
}

function EvaluationView({ dataset }: { dataset: 'ai4i' | 'nasa' }) {
  const resource = useResource<Evaluation>(`/evaluations/${dataset}`);
  if (resource.error) return <ErrorBox message={resource.error} retry={resource.reload} />;
  if (resource.loading || !resource.data) return <Loading />;
  const report = resource.data;
  const keys = dataset === 'ai4i' ? ['average_precision', 'precision', 'recall'] : ['mae', 'rmse', 'macro_case_mae'];
  const labels = dataset === 'ai4i' ? ['Average precision', 'Precisión', 'Recall'] : ['Error absoluto · mm', 'RMSE · mm', 'MAE medio por ensayo'];
  const matrix = report.test.confusion_matrix_tn_fp_fn_tp as number[] | undefined;
  return <><div className="notice"><strong>{report.selected_model}</strong><p>{report.target}</p></div>
    <div className="metrics-grid three">{keys.map((key, i) => <Metric key={key} label={labels[i]} value={fmt(report.test[key] as number)} foot="Conjunto de test reservado" accent={i === 0} />)}</div>
    <div className="two-columns"><Panel title="Separación de los datos" subtitle={dataset === 'ai4i' ? 'Orden UDI · no equivale a tiempo físico' : 'Ensayos completos; ninguno se comparte entre particiones'}>
      <div className="table-wrap"><table><thead><tr><th>Partición</th><th>Registros</th><th>{dataset === 'ai4i' ? 'Fallos' : 'Ensayos'}</th></tr></thead><tbody>
        {Object.entries(report.partitions).map(([key, p]) => <tr key={key}><td>{key}</td><td>{p.rows}</td><td>{p.cases?.join(', ') ?? p.failures}</td></tr>)}</tbody></table></div>
      <div className="coverage"><strong>{(report.coverage.fraction * 100).toFixed(1)}%</strong><span>Cobertura operativa en test<br />{report.coverage.accepted} de {report.coverage.total} lecturas dentro del dominio.</span></div>
      <p className="caption">Las métricas superiores evalúan todas las filas de test. El informe descargable incluye la evaluación de las aceptadas cuando es calculable.</p>
    </Panel><Panel title="Selección en validación" subtitle="El test no selecciona el modelo ni sus umbrales">
      <div className="table-wrap"><table><thead><tr><th>Candidato</th><th>{dataset === 'ai4i' ? 'Average precision' : 'MAE por ensayo'}</th></tr></thead>
        <tbody>{Object.entries(report.validation).map(([name, m]) => <tr key={name}><td>{name}{name === report.selected_model ? ' ✓' : ''}</td><td>{fmt(m[dataset === 'ai4i' ? 'average_precision' : 'macro_case_mae'])}</td></tr>)}</tbody></table></div>
      <p className="caption">Referencia básica en test: {dataset === 'ai4i' ? `AP ${fmt(report.dummy_test.average_precision)}` : `MAE ${fmt(report.dummy_test.mae)} mm`}.</p>
      <a className="button primary" href={`/api/v1/evaluations/${dataset}/download`}><Download size={16} /> Descargar informe completo</a>
    </Panel></div>
    {matrix && <Panel title="Matriz de confusión" subtitle="Test completo · El coste de los errores debe interpretarse con mantenimiento">
      <div className="confusion-grid">{['Verdaderos negativos', 'Falsos positivos', 'Falsos negativos', 'Verdaderos positivos'].map((label, i) => <div key={label}><strong>{matrix[i]}</strong><span>{label}</span></div>)}</div></Panel>}
    {report.global_importance && <Panel title="Importancia global" subtitle="Describe el comportamiento del modelo; no establece causalidad">
      <div className="chart tall" role="img" aria-label="Importancia global de las variables"><ResponsiveContainer width="100%" height="100%"><BarChart
        data={Object.entries(report.global_importance).map(([name, value]) => ({ name: name.replace('numeric__', '').replace('type__', ''), value }))}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} /><YAxis /><Tooltip /><Bar dataKey="value" name="Importancia" fill="#137869" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></Panel>}
    {dataset === 'nasa' && <Panel title="Errores por ensayo de test" subtitle="Cada grupo aporta evidencia independiente">
      <table><thead><tr><th>Ensayo</th><th>Filas etiquetadas</th><th>MAE · mm</th></tr></thead><tbody>{Object.entries(report.test.per_case as Record<string, { mae: number; rows: number }>).map(([key, value]) =>
        <tr key={key}><td>{key}</td><td>{value.rows}</td><td>{fmt(value.mae)}</td></tr>)}</tbody></table></Panel>}
    <p className="model-version">Modelo: {report.model_version}</p></>;
}
