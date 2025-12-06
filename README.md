# Crimewatch Intel Dashboard

**AI-Powered Police Intelligence Aggregator & Correlation Engine**

Crimewatch Intel is a tactical dashboard designed for analyzing, classifying, and visualizing law enforcement incidents. It uses Google's **Gemini 2.5 Flash** model to aggregate scattered reports, clean the data, and generate correlation graphs to identify organized crime activity, gang conflicts, and systemic threats.

## 🚀 Features

*   **Multi-Source Aggregation**: Ingests data simulating Local Police, State Troopers, Penitentiary Logs, and Port Authorities.
*   **AI Intelligence Analysis**:
    *   **Severity Scoring**: Auto-classifies incidents (Low to Critical).
    *   **Entity Extraction**: Identifies specific gangs, known associates, and hot-zones.
    *   **Summarization**: Converts bureaucratic reports into tactical summaries.
*   **Visual Intelligence**:
    *   **Neural Link Graph**: A D3.js "Mind Map" showing relationships between incidents, suspects, and locations.
    *   **Geospatial Map**: Leaflet.js dark-mode map for physical tracking of events.
*   **Tactical HUD**: Real-time metrics on Threat Condition, Active Factions, and Volatility.

## 🛠️ Tech Stack

*   **Frontend**: React 19, Tailwind CSS
*   **AI Engine**: Google GenAI SDK (`gemini-2.5-flash`)
*   **Visualization**: D3.js (Force Graph), Leaflet (Maps)
*   **Language**: TypeScript

## ⚡ Quick Start

1.  **Environment Setup**:
    Ensure you have a valid Google Gemini API Key.
    
    ```bash
    export API_KEY="your_gemini_api_key"
    ```

2.  **Install Dependencies**:
    ```bash
    npm install
    ```

3.  **Run Application**:
    ```bash
    npm start
    ```

## 🧠 Usage Guide

1.  **Select Region**: Use the dropdown in the header to target a specific metro area (e.g., "Fraser Valley, BC").
2.  **Refresh Feed**: Triggers the Gemini Agent to perform a fresh sweep of intelligence for that area.
3.  **Filter**: Use the `MetricsHUD` and filter chips to isolate "Critical" events or specific crime types like "Trafficking".
4.  **Analyze**: 
    *   Click a **Node** in the Mind Map to see connections.
    *   Click a **Map Marker** to see physical location.
    *   View detailed intelligence in the right-hand **Tactical Panel**.

## ⚠️ Data Disclaimer
This tool uses Large Language Models to simulate and aggregate intelligence based on public knowledge and news. It is a proof-of-concept for visualization and correlation logic. Do not use for real-world emergency response without integrating live CAD (Computer Aided Dispatch) APIs.
