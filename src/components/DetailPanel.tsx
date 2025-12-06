import React from 'react';
import { Incident } from '../types';

interface Props {
  incident: Incident | null;
}

const DetailPanel: React.FC<Props> = ({ incident }) => {
  if (!incident) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500 text-sm italic p-6 text-center border border-slate-800 rounded-lg bg-slate-900/50">
        Select an incident or graph node to view intelligence details.
      </div>
    );
  }

  return (
    <div className="h-full bg-slate-900/80 border border-slate-700 rounded-lg p-4 flex flex-col overflow-y-auto shadow-xl">
      <div className="mb-4 pb-4 border-b border-slate-700">
        <h2 className="text-xl font-bold text-white mb-2">{incident.summary}</h2>
        <div className="flex flex-wrap gap-2">
          {incident.tags.map(tag => (
            <span key={tag} className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded-full">
              #{tag}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">Raw Intelligence</h3>
          <p className="text-slate-300 text-sm leading-relaxed bg-slate-800/50 p-3 rounded">
            {incident.fullText}
          </p>
        </div>

        <div>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">Detected Entities</h3>
          {incident.entities.length > 0 ? (
            <ul className="space-y-1">
              {incident.entities.map((entity, idx) => (
                <li key={idx} className="flex items-center gap-2 text-sm text-sky-400">
                  <span className="w-1.5 h-1.5 bg-sky-500 rounded-full"></span>
                  {entity}
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-slate-600 text-sm">No specific entities extracted.</span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-800/30 p-2 rounded border border-slate-700">
            <span className="block text-xs text-slate-500">Source</span>
            <span className="text-sm font-medium text-slate-200">{incident.source}</span>
          </div>
          <div className="bg-slate-800/30 p-2 rounded border border-slate-700">
            <span className="block text-xs text-slate-500">Location</span>
            <span className="text-sm font-medium text-slate-200 truncate">{incident.location}</span>
          </div>
        </div>

        {incident.severity === 'Critical' && (
           <div className="mt-4 p-3 bg-red-900/20 border border-red-600/50 rounded text-red-200 text-sm animate-pulse">
             ⚠️ <strong>ALERT:</strong> This incident is marked as CRITICAL. Immediate cross-reference with Penitentiary and Transport logs suggested.
           </div>
        )}
      </div>
    </div>
  );
};

export default DetailPanel;