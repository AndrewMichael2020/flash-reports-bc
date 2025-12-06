import React from 'react';
import { Incident, Severity, SourceType } from '../types';

interface Props {
  incidents: Incident[];
  onSelect: (incident: Incident) => void;
  selectedIncidentId: string | null;
}

const IncidentFeed: React.FC<Props> = ({ incidents, onSelect, selectedIncidentId }) => {
  const getSeverityColor = (s: Severity) => {
    switch (s) {
      case Severity.CRITICAL: return 'bg-red-900/50 border-red-500 text-red-200';
      case Severity.HIGH: return 'bg-orange-900/40 border-orange-500 text-orange-200';
      case Severity.MEDIUM: return 'bg-yellow-900/30 border-yellow-500 text-yellow-200';
      default: return 'bg-slate-800 border-slate-600 text-slate-300';
    }
  };

  const getSourceIcon = (s: SourceType) => {
    switch (s) {
      case SourceType.PENITENTIARY: return '🔒';
      case SourceType.HIGHWAY_PATROL: return '🛣️';
      case SourceType.PORT_AUTHORITY: return '⚓';
      case SourceType.SPECIALIZED: return '🕵️';
      default: return '🚓';
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto pr-2 space-y-3">
      {incidents.length === 0 && (
        <div className="text-slate-500 text-center text-sm py-10">Waiting for data stream...</div>
      )}
      {incidents.map((incident) => (
        <div
          key={incident.id}
          onClick={() => onSelect(incident)}
          className={`
            p-3 rounded-l border-l-4 cursor-pointer transition-all hover:bg-slate-800
            ${selectedIncidentId === incident.id ? 'bg-slate-800 ring-1 ring-slate-600' : 'bg-slate-900/50'}
            ${getSeverityColor(incident.severity)}
          `}
        >
          <div className="flex justify-between items-start mb-1">
            <span className="text-xs font-mono opacity-70 flex items-center gap-1">
              {getSourceIcon(incident.source)} {incident.source}
            </span>
            <span className="text-[10px] font-bold uppercase tracking-wider opacity-90 border px-1 rounded border-current">
              {incident.severity}
            </span>
          </div>
          <h4 className="font-semibold text-sm mb-1 leading-snug">{incident.summary}</h4>
          <div className="flex justify-between items-end mt-2">
            <span className="text-xs opacity-60 truncate max-w-[120px]">📍 {incident.location}</span>
            <span className="text-[10px] opacity-50">{new Date(incident.timestamp).toLocaleTimeString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default IncidentFeed;