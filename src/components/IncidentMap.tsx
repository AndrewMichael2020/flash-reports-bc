import React, { useEffect, useRef } from 'react';
import { Incident, Severity } from '../types';

interface Props {
  incidents: Incident[];
  selectedIncidentId: string | null;
  region: string;
}

const IncidentMap: React.FC<Props> = ({ incidents, selectedIncidentId, region }) => {
  const mapRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<any[]>([]);

  // Initialize Map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    
    // Default fallback center
    const defaultCenter = [41.8781, -87.6298]; 
    
    // @ts-ignore
    const L = window.L;
    if (!L) return;

    const map = L.map(containerRef.current, {
        zoomControl: false,
        attributionControl: false
    }).setView(defaultCenter, 11);

    // CartoDB Dark Matter tiles for dark theme
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);

    mapRef.current = map;
  }, []);

  // Update Markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    // @ts-ignore
    const L = window.L;

    // Clear existing
    markersRef.current.forEach(m => map.removeLayer(m));
    markersRef.current = [];

    // Add new markers
    incidents.forEach(incident => {
      if (!incident.coordinates || (incident.coordinates.lat === 0 && incident.coordinates.lng === 0)) return;

      const isSelected = incident.id === selectedIncidentId;
      const isCritical = incident.severity === Severity.CRITICAL;

      // Custom Icon color
      const color = isCritical ? '#ef4444' : isSelected ? '#3b82f6' : '#10b981';
      
      const icon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px ${color};"></div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6]
      });

      const marker = L.marker([incident.coordinates.lat, incident.coordinates.lng], { icon })
        .addTo(map)
        .bindPopup(`
          <div style="color: #0f172a; font-family: sans-serif; font-size: 12px;">
            <strong>${incident.summary}</strong><br/>
            <span style="color: #64748b; font-size: 10px;">${incident.location}</span>
          </div>
        `);

      if (isSelected) {
        marker.openPopup();
      }

      markersRef.current.push(marker);
    });

    // Fit bounds if we have points
    if (incidents.length > 0) {
        const bounds = L.latLngBounds(incidents.map(i => [i.coordinates.lat, i.coordinates.lng]).filter(c => c[0] !== 0));
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
        }
    }

  }, [incidents, selectedIncidentId]);

  return (
    <div className="w-full h-full relative">
      <div className="absolute top-2 left-2 z-[400] text-[10px] text-slate-400 uppercase tracking-widest bg-slate-900/80 px-2 py-1 rounded">
        Geospatial Intel
      </div>
      <div ref={containerRef} className="w-full h-full bg-slate-900" />
    </div>
  );
};

export default IncidentMap;