import React from 'react';
import { Severity } from '../types';

interface Props {
  activeFilters: string[];
  onToggleFilter: (filter: string) => void;
  availableTags: string[];
}

const FilterControls: React.FC<Props> = ({ activeFilters, onToggleFilter, availableTags }) => {
  
  const categories = [
    { id: 'Critical Only', label: 'CRITICAL', color: 'border-red-500 text-red-400' },
    { id: 'Gang Activity', label: 'GANGS', color: 'border-indigo-500 text-indigo-400' },
    { id: 'Assassination', label: 'ASSASSINATION', color: 'border-amber-500 text-amber-400' },
    { id: 'Trafficking', label: 'TRAFFICKING', color: 'border-emerald-500 text-emerald-400' },
  ];

  // Merge predefined with dynamic tags if needed, for now stick to major categories for UI cleanliness
  
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
      <span className="text-[10px] text-slate-500 uppercase font-bold mr-2">Filters:</span>
      
      {categories.map(cat => {
        const isActive = activeFilters.includes(cat.id);
        return (
          <button
            key={cat.id}
            onClick={() => onToggleFilter(cat.id)}
            className={`
              text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full border transition-all
              ${isActive 
                ? `bg-slate-800 ${cat.color} shadow-[0_0_10px_rgba(0,0,0,0.5)]` 
                : 'bg-transparent border-slate-700 text-slate-500 hover:border-slate-500'
              }
            `}
          >
            {isActive && <span className="mr-1">●</span>}
            {cat.label}
          </button>
        );
      })}
    </div>
  );
};

export default FilterControls;