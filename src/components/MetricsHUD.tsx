import React from 'react';
import { Incident, Severity } from '../types';

interface Props {
  incidents: Incident[];
  graphNodes: any[];
}

const MetricsHUD: React.FC<Props> = ({ incidents, graphNodes }) => {
  
  // 1. Calculate Threat Condition
  const calculateThreatLevel = () => {
    if (incidents.length === 0) return { level: 'STABLE', color: 'text-emerald-500', bg: 'bg-emerald-500/10 border-emerald-500/30' };
    
    const score = incidents.reduce((acc, curr) => {
      if (curr.severity === Severity.CRITICAL) return acc + 3;
      if (curr.severity === Severity.HIGH) return acc + 2;
      return acc + 1;
    }, 0);

    const avg = score / incidents.length;

    if (avg > 2.2) return { level: 'SEVERE', color: 'text-red-500', bg: 'bg-red-500/10 border-red-500/30' };
    if (avg > 1.5) return { level: 'ELEVATED', color: 'text-orange-500', bg: 'bg-orange-500/10 border-orange-500/30' };
    return { level: 'GUARDED', color: 'text-blue-500', bg: 'bg-blue-500/10 border-blue-500/30' };
  };

  // 2. Count Active Factions (Groups in graph)
  const activeFactions = graphNodes.filter(n => n.type === 'group').length;

  // 3. Most Volatile Source
  const getVolatilitySource = () => {
    const counts: Record<string, number> = {};
    incidents.forEach(i => {
      counts[i.source] = (counts[i.source] || 0) + (i.severity === Severity.CRITICAL ? 3 : 1);
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted.length > 0 ? sorted[0][0] : 'None';
  };

  const threat = calculateThreatLevel();

  return (
    <div className="grid grid-cols-4 gap-4 mb-4">
      {/* Threat Level */}
      <div className={`flex flex-col p-3 rounded border ${threat.bg}`}>
        <span className="text-[10px] uppercase tracking-widest opacity-70">Threat Condition</span>
        <div className={`text-2xl font-black ${threat.color} tracking-tighter`}>
          {threat.level}
        </div>
      </div>

      {/* Active Groups */}
      <div className="flex flex-col p-3 rounded border border-slate-800 bg-slate-900/50">
        <span className="text-[10px] uppercase tracking-widest text-slate-500">Active Factions</span>
        <div className="text-2xl font-mono text-slate-200">
          {activeFactions} <span className="text-xs text-slate-500 align-middle">ID'D</span>
        </div>
      </div>

      {/* Volatile Sector */}
      <div className="flex flex-col p-3 rounded border border-slate-800 bg-slate-900/50">
        <span className="text-[10px] uppercase tracking-widest text-slate-500">Primary Heat Source</span>
        <div className="text-lg font-bold text-slate-200 truncate mt-1">
          {getVolatilitySource()}
        </div>
      </div>

      {/* Critical Incidents Count */}
      <div className="flex flex-col p-3 rounded border border-slate-800 bg-slate-900/50">
        <span className="text-[10px] uppercase tracking-widest text-slate-500">Critical Events</span>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-mono text-white">
            {incidents.filter(i => i.severity === Severity.CRITICAL).length}
          </span>
          <span className="text-xs text-slate-500">/ {incidents.length} Total</span>
        </div>
      </div>
    </div>
  );
};

export default MetricsHUD;