import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { NetworkData, GraphNode, GraphLink, Severity } from '../types';

interface Props {
  data: NetworkData;
  onNodeClick: (nodeId: string) => void;
  selectedIncidentId: string | null;
}

const NetworkGraph: React.FC<Props> = ({ data, onNodeClick, selectedIncidentId }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!data.nodes.length || !svgRef.current || !wrapperRef.current) return;

    const width = wrapperRef.current.clientWidth;
    const height = wrapperRef.current.clientHeight;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous

    const g = svg.append("g");

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    svg.call(zoom);

    // Prepare data for "Mind Map" flow
    // We want to force a left-to-right structure based on "depth" or "type"
    const nodes = data.nodes.map(d => ({ ...d }));
    const links = data.links.map(d => ({ ...d }));

    // Assign rough levels for x-positioning
    nodes.forEach(node => {
      // If node is selected incident, it's level 0 (root)
      // Otherwise incidents are level 1
      // Entities are level 2
      if (node.id === selectedIncidentId) {
        node.level = 0;
        node.fx = 100; // Fixed start X
        node.fy = height / 2; // Fixed start Y
      } else if (node.type === 'incident') {
        node.level = 1;
      } else {
        node.level = 2;
      }
    });

    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force("link", d3.forceLink<GraphNode, GraphLink>(links).id(d => d.id).distance(150))
      .force("charge", d3.forceManyBody().strength(-400))
      .force("collide", d3.forceCollide().radius(60))
      .force("x", d3.forceX<GraphNode>((d) => {
         if (d.level === 0) return 100;
         if (d.level === 1) return width * 0.4;
         return width * 0.8;
      }).strength(0.5))
      .force("y", d3.forceY(height / 2).strength(0.1));

    // Draw Links (Curved bezier for mind map look)
    const link = g.append("g")
      .attr("fill", "none")
      .attr("stroke-opacity", 0.4)
      .selectAll("path")
      .data(links)
      .join("path")
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 1.5);

    // Draw Nodes (Pills/Rects)
    const nodeGroup = g.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("cursor", "pointer")
      .on("click", (event, d) => {
        event.stopPropagation();
        onNodeClick(d.id);
      })
      .call(d3.drag<SVGGElement, GraphNode>()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    // Node Background (Pill)
    nodeGroup.append("rect")
      .attr("rx", 16)
      .attr("ry", 16)
      .attr("height", 32)
      .attr("fill", d => {
        if (d.id === selectedIncidentId) return "#f8fafc"; // White highlight
        if (d.type === 'group') return '#fca5a5'; // Red-ish pastel
        if (d.type === 'location') return '#bae6fd'; // Blue-ish pastel
        if (d.severity === Severity.CRITICAL) return '#fecaca';
        return '#e2e8f0'; // Slate 200
      })
      .attr("stroke", d => {
        if (d.id === selectedIncidentId) return "#3b82f6";
        if (d.severity === Severity.CRITICAL) return "#ef4444";
        return "none";
      })
      .attr("stroke-width", d => d.id === selectedIncidentId ? 3 : 0);

    // Node Text
    const texts = nodeGroup.append("text")
      .text(d => d.label.length > 25 ? d.label.substring(0, 25) + '...' : d.label)
      .attr("x", 12)
      .attr("y", 20)
      .style("font-size", "12px")
      .style("font-family", "sans-serif")
      .style("font-weight", "500")
      .attr("fill", d => {
        // Dark text for pastel backgrounds
        return "#0f172a";
      })
      .style("pointer-events", "none");

    // Dynamic width for rects based on text
    nodeGroup.select("rect")
      .attr("width", function(d) {
         // @ts-ignore
         const w = this.nextSibling.getComputedTextLength();
         return w + 24; // Padding
      });

    simulation.on("tick", () => {
      // Curved edges
      link.attr("d", (d) => {
        const s = d.source as GraphNode;
        const t = d.target as GraphNode;
        // Simple curve
        const dx = (t.x || 0) - (s.x || 0);
        const dy = (t.y || 0) - (s.y || 0);
        const dr = Math.sqrt(dx * dx + dy * dy);
        // Straight line logic is cleaner for horizontal tree sometimes, but let's try shallow curve
        return `M${s.x},${s.y}C${(s.x! + t.x!) / 2},${s.y} ${(s.x! + t.x!) / 2},${t.y} ${t.x},${t.y}`;
      });

      nodeGroup.attr("transform", d => `translate(${d.x! - 20}, ${d.y! - 16})`); // Centering approx
    });

    function dragstarted(event: any, d: GraphNode) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: any, d: GraphNode) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: any, d: GraphNode) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [data, onNodeClick, selectedIncidentId]);

  return (
    <div ref={wrapperRef} className="w-full h-full bg-slate-950 overflow-hidden relative">
      <div className="absolute top-2 left-2 z-10 text-[10px] text-slate-500 uppercase tracking-widest pointer-events-none">
        Entity Mind Map
      </div>
      <svg ref={svgRef} width="100%" height="100%" className="w-full h-full"></svg>
    </div>
  );
};

export default NetworkGraph;