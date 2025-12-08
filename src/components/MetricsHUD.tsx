import React from 'react';
import { Incident, GraphNode, Severity } from '../types';

interface Props {
  incidents: Incident[];
  graphNodes: GraphNode[];
}

function computeThreatCondition(incidents: Incident[]): 'NORMAL' | 'ELEVATED' | 'SEVERE' {
  let critical = 0;
  let high = 0;
  let medium = 0;

  for (const inc of incidents) {
    if (inc.severity === Severity.CRITICAL) critical += 1;
    else if (inc.severity === Severity.HIGH) high += 1;
    else if (inc.severity === Severity.MEDIUM) medium += 1;
  }

  if (critical >= 1 || high >= 3) return 'SEVERE';
  if (high >= 1 || medium >= 5) return 'ELEVATED';
  return 'NORMAL';
}

function computePrimaryHeatSource(incidents: Incident[]): string {
  if (incidents.length === 0) return 'N/A';
  const counts = new Map<string, number>();
  for (const inc of incidents) {
    counts.set(inc.source, (counts.get(inc.source) || 0) + 1);
  }
  const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  return sorted[0]?.[0] ?? 'N/A';
}

const MetricsHUD: React.FC<Props> = ({ incidents }) => {
  const total = incidents.length;
  const criticalCount = incidents.filter(i => i.severity === Severity.CRITICAL).length;
  const threat = computeThreatCondition(incidents);
  const primarySource = computePrimaryHeatSource(incidents);

  return (
    <div className="grid grid-cols-4 gap-3 text-xs">
      {/* Threat Condition */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Threat Condition</div>
        <div
          className={`text-sm font-bold ${
            threat === 'SEVERE'
              ? 'text-red-400'
              : threat === 'ELEVATED'
              ? 'text-yellow-300'
              : 'text-emerald-400'
          }`}
        >
          {threat}
        </div>
      </div>

      {/* Critical Events */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Critical Events</div>
        <div className="text-sm font-bold text-slate-100">
          {criticalCount} <span className="text-slate-500 text-[11px]">/ {total} Total</span>
        </div>
      </div>

      {/* Primary Heat Source */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Primary Heat Source</div>
        <div className="text-sm font-bold text-slate-100">{primarySource}</div>
      </div>

      {/* Reserved metric (can be used later, keep factual) */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Signals</div>
        <div className="text-sm font-bold text-slate-100">
          {total > 0 ? `${total} active reports` : 'No recent reports'}
        </div>
      </div>
    </div>
  );
};

export default MetricsHUD;