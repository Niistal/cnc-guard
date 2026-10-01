import type { ReactNode } from 'react';
import { AlertTriangle, ArrowUpRight, RotateCw } from 'lucide-react';
import type { Status } from './types';

export const statusLabels: Record<Status, string> = {
  NORMAL: 'Normal', WARNING: 'Observación', CRITICAL: 'Revisión prioritaria', UNKNOWN: 'Sin estimación',
};
export const fmt = (value: number | null | undefined, digits = 3) => value == null ? '—' : value.toFixed(digits);
export function Badge({ status }: { status: Status }) {
  return <span className={`badge ${status.toLowerCase()}`}><span className="status-dot" />{statusLabels[status]}</span>;
}
export function Panel({ title, subtitle, action, children, className = '' }: {
  title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>
    {subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}
export function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty" role="status"><RotateCw size={25} /><h3>{title}</h3><p>{text}</p></div>;
}
export function ErrorBox({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="error-box" role="alert"><AlertTriangle size={18} /><span>{message}</span>
    {retry && <button onClick={retry}>Reintentar</button>}</div>;
}
export function Loading() {
  return <div className="skeleton" aria-busy="true" aria-label="Cargando datos"><div /><div /><div /></div>;
}
export function Metric({ label, value, foot, accent = false }: {
  label: string; value: string | number; foot: string; accent?: boolean;
}) {
  return <div className={`metric ${accent ? 'accent' : ''}`}><div>{label}<ArrowUpRight size={17} /></div>
    <strong>{value}</strong><p>{foot}</p></div>;
}
