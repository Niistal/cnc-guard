import { useCallback, useEffect, useState } from 'react';

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.detail || 'No se pudo completar la solicitud.');
  return payload as T;
}

export function useResource<T>(path: string, interval = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(r => r + 1), []);
  useEffect(() => {
    let active = true;
    setData(null); setLoading(true); setError('');
    const load = async () => {
      try { const result = await api<T>(path); if (active) { setData(result); setError(''); } }
      catch (e) { if (active) setError(e instanceof Error ? e.message : 'Error de conexión'); }
      finally { if (active) setLoading(false); }
    };
    void load();
    const timer = interval ? window.setInterval(() => { void load(); }, interval) : undefined;
    return () => { active = false; window.clearInterval(timer); };
  }, [path, interval, revision]);
  return { data, error, loading, reload };
}
