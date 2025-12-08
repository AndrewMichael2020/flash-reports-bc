import React from 'react';
import { Incident, GraphNode, Severity } from '../types';

interface Props {
  incidents: Incident[];
  graphNodes: GraphNode[];
}

// Use explicit three-level threat description
type ThreatLevel = 'LOW' | 'MODERATE' | 'SEVERE';

// Helper: parse ISO string safely
function parseTs(ts: string | undefined | null): Date | null {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

function computeThreatCondition(incidents: Incident[]): ThreatLevel {
  // Only consider incidents from the last 7 days for HUD threat level
  const now = Date.now();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  let critical = 0;
  let high = 0;
  let medium = 0;

  for (const inc of incidents) {
    const d = parseTs(inc.timestamp);
    if (!d) continue;
    if (now - d.getTime() > sevenDaysMs) continue; // older than 7 days -> ignore for threat level

    if (inc.severity === Severity.CRITICAL) critical += 1;
    else if (inc.severity === Severity.HIGH) high += 1;
    else if (inc.severity === Severity.MEDIUM) medium += 1;
  }

  // SEVERE: any recent Critical, or many recent High
  if (critical >= 1 || high >= 5) return 'SEVERE';
  // MODERATE: some recent High or many recent Medium
  if (high >= 1 || medium >= 5) return 'MODERATE';
  // Otherwise, LOW
  return 'LOW';
}

function computeSeverityCounts(incidents: Incident[]) {
  let low = 0;
  let medium = 0;
  let high = 0;
  let critical = 0;

  for (const inc of incidents) {
    if (inc.severity === Severity.CRITICAL) critical += 1;
    else if (inc.severity === Severity.HIGH) high += 1;
    else if (inc.severity === Severity.MEDIUM) medium += 1;
    else if (inc.severity === Severity.LOW) low += 1;
  }
  return { low, medium, high, critical };
}

function computeTopAgencies(incidents: Incident[], maxCount: number = 3): string {
  if (incidents.length === 0) return 'N/A';
  const counts = new Map<string, number>();

  for (const inc of incidents) {
    const name = (inc.agencyName && inc.agencyName.trim()) || inc.source;
    counts.set(name, (counts.get(name) || 0) + 1);
  }

  const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  const top = sorted.slice(0, maxCount);
  return top.map(([name, count]) => `${name} (${count})`).join(', ');
}

const MetricsHUD: React.FC<Props> = ({ incidents /* , graphNodes */ }) => {
  const total = incidents.length;
  const threat = computeThreatCondition(incidents);
  const { critical, high, medium, low } = computeSeverityCounts(incidents);
  const topAgencies = computeTopAgencies(incidents);

  return (
    <div className="grid grid-cols-4 gap-3 text-xs">
      {/* Threat Condition */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Threat Condition</div>
        <div
          className={`text-sm font-bold ${
            threat === 'SEVERE'
              ? 'text-red-400'
              : threat === 'MODERATE'
              ? 'text-yellow-300'
              : 'text-emerald-400'
          }`}
        >
          {threat}
        </div>
      </div>

      {/* Severity Breakdown */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Incident Levels</div>
        <div className="text-[11px] text-slate-200 space-y-0.5">
          <div>Critical: <span className="font-semibold">{critical}</span></div>
          <div>High: <span className="font-semibold">{high}</span></div>
          <div>Medium: <span className="font-semibold">{medium}</span></div>
          <div>Low: <span className="font-semibold">{low}</span></div>
        </div>
      </div>

      {/* Top Agencies */}
      <div className="bg-slate-900/80 border border-slate-700 rounded p-3 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">Top Agencies</div>
        <div className="text-[11px] font-semibold text-slate-100">
          {topAgencies}
        </div>
      </div>

      {/* Signals */}
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