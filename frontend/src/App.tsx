```tsx
// src/App.tsx or src/components/ReportsFeed.tsx

import React, { useState } from 'react';
import './App.css'; // Ensure your CSS file is imported
// ...other imports

function App() {
  const [incidents, setIncidents] = useState([]); // Assuming you have some state for incidents
  // const [selectedRegion, setSelectedRegion] = useState<string>("Fraser Valley, BC");
  // ...other state

  // REMOVE any auto-refresh effects like:
  // useEffect(() => {
  //   doRefresh(selectedRegion);
  // }, [selectedRegion]);
  //
  // And also any effect that calls doRefresh() on initial mount.
  // Keep only the explicit handler that is wired to the Refresh button.

  const handleRefreshClick = async () => {
    // ...existing code that calls backendClient.refreshFeed and then getIncidents/getGraph/getMap...
  };

  const handleRegionChange = (newRegion: string) => {
    // Only change state; do NOT auto-refresh here.
    // setSelectedRegion(newRegion);
    // ...existing code, but ensure no refresh call...
  };

  return (
    <div className="app-root">
      {/* ...existing layout and header... */}

      {/* Region dropdown and refresh button */}
      {/* <RegionSelector value={selectedRegion} onChange={handleRegionChange} /> */}
      {/* <button onClick={handleRefreshClick}>Refresh</button> */}

      {/* Reports feed panel */}
      <section className="reports-panel">
        <h2>Reports Feed</h2>
        <div className="reports-feed-scroll">
          {/* ...existing incident list rendering, e.g.: */}
          {/* {incidents.map(incident => (
               <IncidentCard key={incident.id} incident={incident} />
             ))} */}
        </div>
      </section>

      {/* ...existing graph/map panels... */}
    </div>
  );
}

export default App;
```

```css
/* src/App.css or the relevant CSS file */

.reports-feed-scroll {
  max-height: 400px; /* Adjust based on your layout */
  overflow-y: auto;
  padding-right: 10px; /* Optional: for scrollbar spacing */
}

/* Optional: Add some styling for the scrollbar */
.reports-feed-scroll::-webkit-scrollbar {
  width: 8px;
}

.reports-feed-scroll::-webkit-scrollbar-thumb {
  background-color: #888;
  border-radius: 4px;
}

.reports-feed-scroll::-webkit-scrollbar-thumb:hover {
  background-color: #555;
}
```

### Explanation
- **JSX Changes:** Wrapped the incident list in a `div` with the class `reports-feed-scroll`. Removed any `useEffect` that auto-calls `refreshFeed` on mount or on region change.
- **CSS Styles:**
  - `.reports-feed-scroll`: Sets a `max-height` to make the container scrollable and adds padding for scrollbar spacing.
  - **Scrollbar Styles (Optional):** Customizes the scrollbar appearance for WebKit browsers (Chrome, Safari). Adjust or remove these rules based on your design preferences and browser support requirements.