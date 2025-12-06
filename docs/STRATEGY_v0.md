# Product Strategy & Technical Architecture

## 1. Executive Summary
**Crimewatch Intel** addresses the problem of information silos in law enforcement. By using Generative AI, we correlate data between disjointed agencies (e.g., a prison drone drop and a street-level shooting) to provide a holistic threat assessment.

## 2. Architecture Overview

The application follows a **Client-Side Intelligence** architecture. There is no heavy backend database; intelligence is generated on-the-fly via the Gemini API, creating a stateless but context-aware session.

### Core Pipeline ( The "Intel Cycle" )

1.  **Collection (Ingestion)**: 
    *   *Component*: `services/geminiService.ts` -> `fetchRecentIncidents`
    *   *Method*: Uses Gemini with `googleSearch` tools to find recent relevant events.
    *   *Filter Logic*: Strict negative prompting is used to exclude "noise" (petty theft, traffic stops) to ensure the dashboard focuses on actionable intelligence.

2.  **Processing (Analysis)**:
    *   *Component*: `services/geminiService.ts` -> `analyzeIncident`
    *   *Method*: Each raw incident is passed through a secondary prompt to extract structured data: `Severity`, `Entities` (Gang names), and `Tags`.
    *   *Tech*: Parallel processing using `Promise.all`.

3.  **Dissemination (Visualization)**:
    *   *Graph Layer*: Uses D3.js to render a force-directed "Mind Map".
    *   *Map Layer*: Uses Leaflet/OpenStreetMap to render geospatial coordinates estimated by the AI.

## 3. Prompt Engineering Strategy

We use a multi-stage prompting strategy to ensure high-quality data.

### Stage 1: The Gatekeeper (Ingestion)
The prompt explicitly defines what is *NOT* allowed.
> "STRICTLY EXCLUDE: Petty theft... domestic disputes... public disorder."
> "MUST INCLUDE: Assassinations, Prison Escapes, Gang Warfare."

This prevents the dashboard from being flooded with low-value data, preserving the "Tactical" feel.

### Stage 2: The Analyst (Enrichment)
We ask the model to think like a detective.
> "Determine Severity... Extract Entities... Generate Tags."

### Stage 3: The Link Analyst (Correlation)
We feed the enriched JSON back into the model to generate the graph structure.
> "Build a hierarchical mind map... Connect Incidents to their Locations and Entities."

## 4. Technical Specifications

### Data Structures (`types.ts`)
*   **Incident**: The atomic unit of data. Contains `id`, `fullText`, `coordinates`, `severity`.
*   **GraphNode**: Extends D3 simulation nodes. Includes visual properties like `level` (for tree layout) and `type` (Incident vs. Entity).

### Visualization Logic
*   **NetworkGraph (`components/NetworkGraph.tsx`)**: 
    *   Uses a constrained Force Simulation.
    *   **x-positioning** is coerced based on node depth to create a Left-to-Right flow (Root -> Incident -> Entity).
    *   **Pill Shapes**: Custom SVG drawing to accommodate text labels within the node, mimicking modern research tools (like NotebookLM).

*   **Geospatial (`components/IncidentMap.tsx`)**:
    *   Dark Mode tiles (CartoDB) to match the app theme.
    *   Dynamic marker coloring based on Severity.

## 5. Roadmap & Scalability

### Phase 1: Prototype (Current)
*   Client-side generation.
*   Simulated/News-based data.
*   In-memory state.

### Phase 2: Integration (Next Steps)
*   **Live CAD Integration**: Replace `googleSearch` with specific API hooks to Police CAD systems (e.g., Hexagon, Motorola Solutions).
*   **Persistent Database**: Store incidents in PostgreSQL/Supabase to track trends over time.
*   **User Auth**: RLS (Row Level Security) for different clearance levels.

### Phase 3: Predictive Analytics
*   Use Gemini Pro to predict *future* hotspots based on historical graph density.
*   Automated alerts when specific entities (e.g., "Wolfpack Alliance") are detected in new regions.
