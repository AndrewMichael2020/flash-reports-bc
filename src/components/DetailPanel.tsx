import React from 'react';
import { Incident, Severity } from '../types';

interface Props {
  incident: Incident | null;
}

const DetailPanel: React.FC<Props> = ({ incident }) => {
  if (!incident) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500 text-sm">
        Select an event from the feed or graph to see details.
      </div>
    );
  }

  const {
    summary,
    fullText,
    severity,
    source,
    location,
    timestamp,
    incidentOccurredAt,
    tags,
    entities,
    sourceUrl,
    crimeCategory,
    temporalContext,
    weaponInvolved,
    tacticalAdvice,
  } = incident;

  const reportedAt = new Date(timestamp);
  const occurredAt = incidentOccurredAt ? new Date(incidentOccurredAt) : null;

  return (
    <div className="flex flex-col h-full space-y-3 text-sm text-slate-200">
      {/* Title */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold text-white">{summary}</h3>
          <span
            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
              severity === Severity.CRITICAL
                ? 'bg-red-600/80 text-white'
                : severity === Severity.HIGH
                ? 'bg-orange-500/80 text-white'
                : severity === Severity.MEDIUM
                ? 'bg-yellow-400/80 text-slate-900'
                : 'bg-emerald-500/80 text-slate-900'
            }`}
          >
            {severity}
          </span>
        </div>
        <p className="text-[11px] text-slate-500">
          {source} · {location}
        </p>
      </div>

      {/* Times */}
      <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
        <div>
          <div className="text-slate-500 uppercase tracking-wide text-[10px]">Reported</div>
          <div className="text-[12px] text-slate-200">{reportedAt.toLocaleString()}</div>
        </div>
        {occurredAt && (
          <div>
            <div className="text-slate-500 uppercase tracking-wide text-[10px]">Incident Time</div>
            <div className="text-[12px] text-slate-200">{occurredAt.toLocaleString()}</div>
          </div>
        )}
      </div>

      {/* Analysis and Sources */}
      <div className="mt-1 border-t border-slate-800 pt-2">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
            Analysis and Sources
          </h4>
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="text-[11px] text-blue-400 hover:text-blue-300 underline"
            >
              Open source article
            </a>
          )}
        </div>

        <div className="space-y-1 text-[12px] text-slate-200">
          {crimeCategory && (
            <div>
              <span className="text-slate-500">Crime Category: </span>
              <span>{crimeCategory}</span>
            </div>
          )}
          {temporalContext && (
            <div>
              <span className="text-slate-500">Temporal Context: </span>
              <span>{temporalContext}</span>
            </div>
          )}
          {weaponInvolved && (
            <div>
              <span className="text-slate-500">Weapon Involved: </span>
              <span>{weaponInvolved}</span>
            </div>
          )}
          {tacticalAdvice && (
            <div>
              <span className="text-slate-500">Tactical Advice: </span>
              <span>{tacticalAdvice}</span>
            </div>
          )}
        </div>
      </div>

      {/* Entities */}
      <div className="mt-2">
        <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-1">
          Detected Entities
        </h4>
        <div className="flex flex-wrap gap-1">
          {entities.map((e) => (
            <span
              key={e}
              className="px-2 py-0.5 rounded-full bg-slate-800 text-[11px] text-slate-200"
            >
              {e}
            </span>
          ))}
          {entities.length === 0 && (
            <span className="text-[11px] text-slate-500">None detected.</span>
          )}
        </div>
      </div>

      {/* Narrative */}
      <div className="mt-2">
        <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wide mb-1">
          Narrative
        </h4>
        <div className="text-[11px] text-slate-300 bg-slate-900/60 rounded p-2 border border-slate-800 overflow-y-auto max-h-40">
          {fullText}
        </div>
      </div>
    </div>
  );
};

export default DetailPanel;