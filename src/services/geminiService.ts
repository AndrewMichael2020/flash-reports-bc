import { GoogleGenAI, Type } from "@google/genai";
import { Incident, NetworkData, Severity, SourceType } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
const modelName = "gemini-2.5-flash";

// Helper to generate a unique ID
const generateId = () => Math.random().toString(36).substr(2, 9);

/**
 * Stage 1: Ingestion & Filtering
 * Simulates scraping by using Gemini with Grounding to find relevant news.
 */
export const fetchRecentIncidents = async (region: string): Promise<Incident[]> => {
  const prompt = `
    Find recent police news, penitentiary reports, and highway patrol incidents in ${region}.
    
    CRITICAL FILTERING RULES:
    1. STRICTLY EXCLUDE: Petty theft, shoplifting, simple traffic violations, domestic disputes without weapons, vandalism, minor drug possession, and public disorder/riots (unless organized attack).
    2. MUST INCLUDE: 
       - Homicides / Assassinations
       - Carjackings / Grand Theft Auto rings
       - Major Drug Busts / Trafficking (Medium Severity)
       - Missing Persons (High profile or suspicious)
       - Prison Escapes / Penitentiary Breaches
       - Gang Warfare (High/Critical)
       - Kidnapping
       - Commercial/Industrial Theft Rings (Medium/High)
    3. SOURCES: Local police, state police, specialized units, port authorities, prisons.
    4. EXCLUDE: Military operations, social media rumors.
    
    Return a list of at least 5-7 distinct event summaries.
    Provide a balanced spectrum of severity, not just Critical events. Include Medium severity intelligence like large scale theft or drug labs.
    IMPORTANT: You must estimate specific Latitude and Longitude coordinates for where each event likely occurred based on the location description.

    OUTPUT FORMAT:
    You must return a valid raw JSON array. 
    DO NOT wrap the response in markdown code blocks (like \`\`\`json). 
    Just return the raw JSON string starting with '[' and ending with ']'.
    
    Structure:
    [
      {
        "summary": "Short headline",
        "location": "Specific address or area",
        "lat": 12.3456,
        "lng": -12.3456,
        "sourceType": "One of: Local Police, State Police, Penitentiary, Port Authority, Highway Patrol, Specialized Unit",
        "fullText": "Detailed description..."
      }
    ]
  `;

  try {
    // NOTE: responseMimeType: 'application/json' cannot be used with tools: [{ googleSearch: {} }]
    // We rely on the prompt to enforce JSON structure.
    const response = await ai.models.generateContent({
      model: modelName,
      contents: prompt,
      config: {
        tools: [{ googleSearch: {} }],
      }
    });

    let text = response.text || "[]";
    
    // Aggressive cleanup of markdown if the model ignores the instruction
    text = text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
    
    // Ensure we have something looking like an array
    const firstBracket = text.indexOf('[');
    const lastBracket = text.lastIndexOf(']');
    
    if (firstBracket !== -1 && lastBracket !== -1) {
      text = text.substring(firstBracket, lastBracket + 1);
    } else {
      console.warn("Model response was not a JSON array, attempting fallback parsing or using fallback data.");
      // If parsing fails completely, we might throw or return empty
      if (!text.startsWith('[')) throw new Error("Invalid JSON format");
    }

    const rawData = JSON.parse(text);

    // Map to our internal strict types
    return rawData.map((item: any) => ({
      id: generateId(),
      timestamp: new Date().toISOString(),
      source: mapSourceType(item.sourceType),
      location: item.location || region,
      coordinates: { lat: item.lat || 0, lng: item.lng || 0 },
      summary: item.summary,
      fullText: item.fullText,
      severity: Severity.MEDIUM, // Default, will be refined in analysis
      tags: [],
      entities: [],
      relatedIncidentIds: []
    }));

  } catch (error) {
    console.error("Error fetching incidents:", error);
    return fallbackIncidents;
  }
};

/**
 * Stage 2: Deep Analysis & Classification
 * Analyzing a single incident to extract entities and severity.
 */
export const analyzeIncident = async (incident: Incident): Promise<Incident> => {
  const prompt = `
    Analyze this police report for intelligence purposes: "${incident.fullText}"
    
    Tasks:
    1. Determine Severity (Low, Medium, High, Critical). 
       - Critical: Assassination, Mass casualty, Prison Escape, Cop killer.
       - High: Gang shooting, Armed Robbery, Kidnapping, Carjacking ring, Missing Person.
       - Medium: Drug bust, Industrial Theft, Weapon seizure.
       - Low: Non-violent.
    2. Extract Entities: Specific Gang names (e.g., Latin Kings, GDs, UN Gang), Key Individuals, Specific Addresses/Landmarks.
    3. Generate Categories/Tags: Select from [Assassination, Gang Activity, Trafficking, Escape, Homicide, Armed Assault, Carjacking, Missing Person, Theft Ring].
  `;

  try {
    const response = await ai.models.generateContent({
      model: modelName,
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            severity: { type: Type.STRING, enum: ["Low", "Medium", "High", "Critical"] },
            tags: { type: Type.ARRAY, items: { type: Type.STRING } },
            entities: { type: Type.ARRAY, items: { type: Type.STRING } }
          }
        }
      }
    });

    const analysis = JSON.parse(response.text || "{}");
    
    return {
      ...incident,
      severity: analysis.severity as Severity,
      tags: analysis.tags || [],
      entities: analysis.entities || []
    };

  } catch (e) {
    console.error("Analysis failed", e);
    return incident;
  }
};

/**
 * Stage 3: Network Correlation
 * Analyzes the entire dataset to build a mindmap/tree of connections.
 */
export const generateCorrelationGraph = async (incidents: Incident[]): Promise<NetworkData> => {
  if (incidents.length === 0) return { nodes: [], links: [] };

  const incidentsJson = JSON.stringify(incidents.map(i => ({
    id: i.id,
    summary: i.summary,
    entities: i.entities,
    location: i.location,
    source: i.source,
    tags: i.tags
  })));

  const prompt = `
    You are a police intelligence analyst. Build a hierarchical mind map structure from these incidents.
    
    Data: ${incidentsJson}

    The goal is a "Mind Map" style graph that flows from left to right.
    
    Structure:
    1. Identify key Clusters/Themes (e.g. "Gang War", "Trafficking Ring", "Prison Breaches") or use the Incidents themselves as primary nodes if they are distinct.
    2. Connect Incidents to their Locations and Entities (Gangs, Persons).
    3. Connect related incidents together.
    
    Return a JSON structure with 'nodes' and 'links'.
    Nodes must have: id, label, type (incident, location, group, person).
    Links must have: source (id), target (id), type (involved, occurred_at, related_to).
  `;

  try {
    const response = await ai.models.generateContent({
      model: modelName,
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            nodes: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  id: { type: Type.STRING },
                  label: { type: Type.STRING },
                  type: { type: Type.STRING, enum: ['incident', 'location', 'group', 'person'] }
                }
              }
            },
            links: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  source: { type: Type.STRING },
                  target: { type: Type.STRING },
                  type: { type: Type.STRING, enum: ['occurred_at', 'involved', 'related_to'] }
                }
              }
            }
          }
        }
      }
    });

    const graph = JSON.parse(response.text || "{\"nodes\": [], \"links\": []}");
    
    // Enrich nodes
    const enrichedNodes = graph.nodes.map((node: any) => {
      const incident = incidents.find(i => i.id === node.id);
      return {
        ...node,
        severity: incident ? incident.severity : undefined
      };
    });

    return {
      nodes: enrichedNodes,
      links: graph.links
    };

  } catch (e) {
    console.error("Graph generation failed", e);
    return { nodes: [], links: [] };
  }
};

// Utilities
function mapSourceType(raw: string): SourceType {
  const r = raw ? raw.toLowerCase() : "";
  if (r.includes('highway')) return SourceType.HIGHWAY_PATROL;
  if (r.includes('prison') || r.includes('penitentiary') || r.includes('correction')) return SourceType.PENITENTIARY;
  if (r.includes('port')) return SourceType.PORT_AUTHORITY;
  if (r.includes('special')) return SourceType.SPECIALIZED;
  if (r.includes('state')) return SourceType.POLICE_STATE;
  return SourceType.POLICE_LOCAL;
}

// Fallback data for Langley, Chilliwack, and area
const fallbackIncidents: Incident[] = [
  {
    id: "fb1",
    timestamp: new Date().toISOString(),
    source: SourceType.POLICE_LOCAL,
    location: "Langley, BC - Industrial Ave",
    coordinates: { lat: 49.1042, lng: -122.6604 },
    summary: "Clandestine lab discovery in warehouse.",
    fullText: "RCMP raided a commercial property on Industrial Ave finding a significant synthetic drug production lab. Three arrests made, linked to the 'Wolfpack' alliance.",
    severity: Severity.HIGH,
    tags: ["Trafficking", "Gang Activity"],
    entities: ["Wolfpack", "Langley RCMP"],
    relatedIncidentIds: []
  },
  {
    id: "fb2",
    timestamp: new Date().toISOString(),
    source: SourceType.SPECIALIZED,
    location: "Chilliwack, BC - Vedder Rd",
    coordinates: { lat: 49.1173, lng: -121.9610 },
    summary: "Heavy Equipment Theft Ring bust.",
    fullText: "Integrated Municipal Provincial Auto Crime Team (IMPACT) recovered 4 excavators stolen from construction sites. Suspects believed to be shipping machinery overseas.",
    severity: Severity.MEDIUM,
    tags: ["Theft Ring", "Organized Crime"],
    entities: ["IMPACT", "Overseas Export Group"],
    relatedIncidentIds: []
  },
  {
    id: "fb3",
    timestamp: new Date().toISOString(),
    source: SourceType.PENITENTIARY,
    location: "Abbotsford, BC",
    coordinates: { lat: 49.0304, lng: -122.3275 },
    summary: "Drone contraband drop intercepted.",
    fullText: "Pacific Institution staff intercepted a heavy-lift drone carrying narcotics and SIM cards into the medium security yard.",
    severity: Severity.MEDIUM,
    tags: ["Trafficking", "Contraband"],
    entities: ["Pacific Institution", "Drone Pilot Unknown"],
    relatedIncidentIds: []
  },
  {
    id: "fb4",
    timestamp: new Date().toISOString(),
    source: SourceType.POLICE_LOCAL,
    location: "Langley/Surrey Border",
    coordinates: { lat: 49.1100, lng: -122.7000 },
    summary: "Drive-by shooting, no injuries.",
    fullText: "Shots fired at a residence known to police. Shell casings recovered consistent with conflict between rival dial-a-dope lines.",
    severity: Severity.HIGH,
    tags: ["Gang Activity", "Shooting"],
    entities: ["Dial-a-dope Line A", "Dial-a-dope Line B"],
    relatedIncidentIds: []
  },
  {
    id: "fb5",
    timestamp: new Date().toISOString(),
    source: SourceType.POLICE_LOCAL,
    location: "Chilliwack River Valley",
    coordinates: { lat: 49.0800, lng: -121.9000 },
    summary: "Suspicious Missing Person.",
    fullText: "Vehicle found abandoned near Tamahi Creek. Owner has known ties to organized crime; disappearance considered suspicious by IHIT.",
    severity: Severity.CRITICAL,
    tags: ["Missing Person", "Homicide"],
    entities: ["IHIT", "Tamahi Creek"],
    relatedIncidentIds: []
  }
];