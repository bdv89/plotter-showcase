import { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '../store/appStore';
import { getMetricsSummary, getMetricsDaily, getMetricsEndpoints } from '../api/client';
import type { MetricsSummary, MetricsDailyRow, MetricsEndpointRow } from '../types';

const REFRESH_MS = 60_000; // auto-refresh comme la vue de référence (picture_to_CAS)

export function MetricsView() {
  const setError = useAppStore(s => s.setError);
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [daily, setDaily] = useState<MetricsDailyRow[]>([]);
  const [endpoints, setEndpoints] = useState<MetricsEndpointRow[]>([]);

  const load = useCallback(() => {
    Promise.all([getMetricsSummary(), getMetricsDaily(30), getMetricsEndpoints()])
      .then(([s, d, e]) => {
        setSummary(s);
        setDaily(d.rows);
        setEndpoints(e.rows);
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Metrics failed'));
  }, [setError]);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const hasData = !!summary && summary.total_requests > 0;

  return (
    <div className="metrics-view">
      <div className="metrics-toolbar">
        <h3>Suivi de connexion</h3>
        <button onClick={load} title="Rafraîchir">Refresh</button>
      </div>

      <div className="metrics-cards">
        <div className="metric-card">
          <span className="metric-value">{summary?.total_requests ?? 0}</span>
          <span className="metric-label">Requêtes totales</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{summary?.unique_ips_total ?? 0}</span>
          <span className="metric-label">IPs uniques (total)</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{summary?.unique_ips_today ?? 0}</span>
          <span className="metric-label">IPs uniques (aujourd'hui)</span>
        </div>
      </div>

      {!hasData ? (
        <div className="file-table-empty">Aucune donnée de connexion pour le moment</div>
      ) : (
        <>
          <h4 className="metrics-heading">Hits par endpoint</h4>
          <div className="file-table-wrapper">
            <table className="file-table">
              <thead>
                <tr>
                  <th className="col-filename">Endpoint</th>
                  <th className="col-extracted">Total</th>
                  <th className="col-extracted">Dernière activité</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map(e => (
                  <tr key={e.endpoint}>
                    <td className="col-filename">{e.endpoint}</td>
                    <td className="col-extracted">{e.total}</td>
                    <td className="col-extracted">{e.last_activity ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4 className="metrics-heading">Activité par jour (30 derniers jours)</h4>
          <div className="file-table-wrapper">
            <table className="file-table">
              <thead>
                <tr>
                  <th className="col-filename">Date</th>
                  <th className="col-extracted">Requêtes</th>
                  <th className="col-extracted">IPs uniques</th>
                </tr>
              </thead>
              <tbody>
                {daily.map(d => (
                  <tr key={d.date}>
                    <td className="col-filename">{d.date}</td>
                    <td className="col-extracted">{d.requests}</td>
                    <td className="col-extracted">{d.unique_ips}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
