import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Incident, NetworkData, Severity } from './types';
import * as BackendClient from './services/backendClient';
import NetworkGraph from './components/NetworkGraph';
import IncidentFeed from './components/IncidentFeed';
import DetailPanel from './components/DetailPanel';
import MetricsHUD from './components/MetricsHUD';
import IncidentMap from './components/IncidentMap';

const REGIONS = [
  "Fraser Valley, BC",
  "Metro Vancouver, BC",
  "Victoria, BC",
  "BC Interior",
  "Calgary, AB",
  "Edmonton, AB",
  "Seattle Metro, WA"
];

// UI constants
const JOB_ID_DISPLAY_LENGTH = 8; // Number of characters to show from job ID in status messages

function App() {
  const [region, setRegion] = useState(REGIONS[0]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [graphData, setGraphData] = useState<NetworkData>({ nodes: [], links: [] });
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("System Ready");

  // --- initial load: read-only, no refresh ---
  const loadInitialData = useCallback(async () => {
    setIsLoading(true);
    setStatus(`Loading existing ${region} incidents from DB...`);

    try {
      const [incidentsData, graphResult, mapResult] = await Promise.all([
        BackendClient.getIncidents(region),
        BackendClient.getGraph(region),
        BackendClient.getMap(region),
      ]);

      setIncidents(incidentsData.incidents);
      setGraphData({ nodes: graphResult.nodes, links: graphResult.links });

      if (incidentsData.incidents.length > 0) {
        setStatus(`Loaded ${incidentsData.incidents.length} existing incidents.`);
      } else {
        setStatus(`No incidents found yet for ${region}. Click REFRESH FEED to fetch.`);
      }
    } catch (error) {
      console.error("Failed to load initial data from backend:", error);
      setStatus(
        `System Error (initial load): ${
          error instanceof Error ? error.message : "Failed to query existing data"
        }`,
      );
    } finally {
      setIsLoading(false);
    }
  }, [region]);

  useEffect(() => {
    // On first mount, load whatever is already in the DB for the default region.
    // Do not call /api/refresh here.
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // run once on mount

  // --- explicit refresh: calls POST /api/refresh-async then polls status ---
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setStatus(`Starting refresh for ${region}...`);
    setIncidents([]);
    setGraphData({ nodes: [], links: [] });

    try {
      // Start async refresh job
      const asyncResponse = await BackendClient.refreshFeedAsync(region);
      const jobId = asyncResponse.job_id;
      
      setStatus(`Refresh job ${jobId.substring(0, JOB_ID_DISPLAY_LENGTH)}... started. Fetching data...`);

      // Poll for job completion
      const pollInterval = 3000; // 3 seconds
      const maxPolls = 60; // Max 3 minutes (60 * 3s = 180s)
      let pollCount = 0;

      const pollStatus = async (): Promise<boolean> => {
        try {
          const statusResponse = await BackendClient.getRefreshStatus(jobId);
          
          if (statusResponse.status === 'succeeded') {
            setStatus(`Refresh complete: ${statusResponse.new_articles || 0} new articles. Loading incidents...`);
            
            // Load the fresh data
            const [incidentsData, graphResult, mapResult] = await Promise.all([
              BackendClient.getIncidents(region),
              BackendClient.getGraph(region),
              BackendClient.getMap(region),
            ]);

            setIncidents(incidentsData.incidents);
            setGraphData({ nodes: graphResult.nodes, links: graphResult.links });
            setStatus(`Monitoring complete. ${incidentsData.incidents.length} events logged.`);
            return true; // Stop polling
            
          } else if (statusResponse.status === 'failed') {
            setStatus(`Refresh failed: ${statusResponse.error_message || 'Unknown error'}`);
            return true; // Stop polling
            
          } else if (statusResponse.status === 'running') {
            setStatus(`Refresh in progress (${statusResponse.status})...`);
            return false; // Continue polling
            
          } else {
            // pending or other status
            setStatus(`Refresh pending...`);
            return false; // Continue polling
          }
        } catch (error) {
          console.error("Failed to poll refresh status:", error);
          // Continue polling on transient errors
          return false;
        }
      };

      // Poll until complete or max attempts
      while (pollCount < maxPolls) {
        const isDone = await pollStatus();
        if (isDone) break;
        
        await new Promise(resolve => setTimeout(resolve, pollInterval));
        pollCount++;
      }

      if (pollCount >= maxPolls) {
        setStatus(`Refresh is taking longer than expected. It may still be running in the background.`);
        
        // Load whatever data is available
        try {
          const [incidentsData, graphResult, mapResult] = await Promise.all([
            BackendClient.getIncidents(region),
            BackendClient.getGraph(region),
            BackendClient.getMap(region),
          ]);

          setIncidents(incidentsData.incidents);
          setGraphData({ nodes: graphResult.nodes, links: graphResult.links });
        } catch (e) {
          console.error("Failed to load data after timeout:", e);
        }
      }

    } catch (error) {
      console.error("Failed to start refresh:", error);
      
      // Check if it's a 504 timeout - be graceful about it
      if (error instanceof Error && error.message.includes('504')) {
        setStatus(`Refresh is running in the background. Data will update shortly.`);
        
        // Try to load existing data
        try {
          const [incidentsData, graphResult, mapResult] = await Promise.all([
            BackendClient.getIncidents(region),
            BackendClient.getGraph(region),
            BackendClient.getMap(region),
          ]);

          setIncidents(incidentsData.incidents);
          setGraphData({ nodes: graphResult.nodes, links: graphResult.links });
        } catch (e) {
          console.error("Failed to load existing data:", e);
        }
      } else {
        setStatus(
          `System Error: ${
            error instanceof Error ? error.message : "Failed to acquire feed"
          }`,
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [region]);

  const handleIncidentSelect = (incident: Incident) => {
    setSelectedIncidentId(incident.id);
  };

  const handleNodeClick = (nodeId: string) => {
    // Check if the node matches an incident ID
    const incident = incidents.find(i => i.id === nodeId);
    if (incident) {
      setSelectedIncidentId(nodeId);
    }
  };

  const filteredIncidents = useMemo(() => {
    // no filters: just return all incidents
    return incidents;
  }, [incidents]);

  const filteredGraphData = useMemo(() => {
    // no filters: just return full graph
    return graphData;
  }, [graphData]);

  const selectedIncident = incidents.find(i => i.id === selectedIncidentId) || null;

  return (
    <div className="flex flex-col h-screen w-full bg-slate-950 text-slate-200 font-sans overflow-hidden">
      {/* Header */}
      <header className="flex-none h-16 border-b border-slate-800 bg-slate-900 flex items-center justify-between px-6 shadow-md z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
             <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-white">
              <path fillRule="evenodd" d="M9 4.5a.75.75 0 01.721.544l.813 2.846a3.75 3.75 0 002.576 2.576l2.846.813a.75.75 0 010 1.442l-2.846.813a3.75 3.75 0 00-2.576 2.576l-.813 2.846a.75.75 0 01-1.442 0l-.813-2.846a3.75 3.75 0 00-2.576-2.576l-2.846-.813a.75.75 0 010-1.442l2.846-.813a3.75 3.75 0 002.576-2.576l.813-2.846A.75.75 0 019 4.5zM6 20.25a.75.75 0 01.75.75v.75c0 .414-.336.75-.75.75H5.25a.75.75 0 01-.75-.75v-.75a.75.75 0 01.75-.75H6z" clipRule="evenodd" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">CRIMEWATCH <span className="text-blue-500">INTEL</span></h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest">Multi-Agency Feed Aggregator</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center bg-slate-800 rounded px-3 py-1.5 border border-slate-700">
            <span
              className={`w-2 h-2 rounded-full mr-2 ${
                isLoading ? "bg-yellow-400 animate-pulse" : "bg-green-500"
              }`}
            ></span>
            <span className="text-xs font-mono text-slate-300">{status}</span>
          </div>

          <select
            className="bg-slate-800 border border-slate-700 text-sm rounded px-3 py-1.5 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            disabled={isLoading}
          >
            {REGIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          <button
            onClick={loadData}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold py-2 px-4 rounded transition-colors disabled:opacity-50"
          >
            REFRESH FEED
          </button>
        </div>
      </header>

      {/* Main Content Grid */}
      <main className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
        
        {/* Left Sidebar: Feed */}
        <aside className="col-span-3 bg-slate-900 border-r border-slate-800 p-4 flex flex-col h-full min-h-0 z-10 shadow-[10px_0_20px_rgba(0,0,0,0.1)]">
          <div className="flex justify-between items-center mb-4 flex-none">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Reports Feed</h2>
            <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-500">
              {filteredIncidents.length} / {incidents.length}
            </span>
          </div>
          
          <div className="flex-1 min-h-0 overflow-y-auto">
            <IncidentFeed
              incidents={filteredIncidents}
              onSelect={handleIncidentSelect}
              selectedIncidentId={selectedIncidentId}
            />
          </div>
        </aside>

        {/* Center: Graph & Map */}
        <section className="col-span-6 bg-slate-950 relative flex flex-col">
          
          {/* Top HUD Area */}
          <div className="p-4 border-b border-slate-800/50 bg-slate-900/20 backdrop-blur-sm z-10">
            <MetricsHUD incidents={incidents} graphNodes={graphData.nodes} />
          </div>

          {/* Visualization Split View */}
          <div className="flex-1 flex flex-col overflow-hidden">
            
            {/* Top: Mind Map */}
            <div className="h-[60%] border-b border-slate-800 relative">
               {isLoading && graphData.nodes.length === 0 ? (
                  <div className="w-full h-full flex flex-col items-center justify-center">
                     <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
                     <span className="text-slate-500 font-mono text-sm animate-pulse">Initializing Neural Link...</span>
                  </div>
               ) : (
                 <NetworkGraph 
                    data={filteredGraphData} 
                    onNodeClick={handleNodeClick} 
                    selectedIncidentId={selectedIncidentId} 
                 />
               )}
            </div>
            
            {/* Bottom: Geospatial Map */}
            <div className="h-[40%] bg-slate-900 relative">
               <IncidentMap 
                  incidents={filteredIncidents} 
                  selectedIncidentId={selectedIncidentId}
                  region={region} 
               />
            </div>

          </div>
        </section>

        {/* Right Sidebar: Details */}
        <aside className="col-span-3 bg-slate-900 border-l border-slate-800 p-4 flex flex-col z-10 shadow-[-10px_0_20px_rgba(0,0,0,0.2)]">
          <div className="mb-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Analysis and Sources
            </h2>
          </div>
          <div className="flex-1 overflow-hidden">
            <DetailPanel incident={selectedIncident} />
          </div>
        </aside>

      </main>
    </div>
  );
}

export default App;