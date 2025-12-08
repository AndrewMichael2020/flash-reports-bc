```tsx
// src/App.tsx or src/components/ReportsFeed.tsx

import React from 'react';
import './App.css'; // Ensure your CSS file is imported

function App() {
  // ...existing state, hooks, handlers...

  return (
    <div className="app-root">
      {/* ...existing layout... */}
      <section className="reports-panel">
        <h2>Reports Feed</h2>
        <div className="reports-feed-scroll">
          {/* ...existing incident list rendering, e.g.: */}
          {/* {incidents.map(incident => (
               <IncidentCard key={incident.id} incident={incident} />
             ))} */}
        </div>
      </section>
      {/* ...existing layout... */}
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
- **JSX Changes:** Wrapped the incident list in a `div` with the class `reports-feed-scroll`.
- **CSS Styles:**
  - `.reports-feed-scroll`: Sets a `max-height` to make the container scrollable and adds padding for scrollbar spacing.
  - **Scrollbar Styles (Optional):** Customizes the scrollbar appearance for WebKit browsers (Chrome, Safari). Adjust or remove these rules based on your design preferences and browser support requirements.