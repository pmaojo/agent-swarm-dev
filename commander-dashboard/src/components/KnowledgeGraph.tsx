import { useEffect, useRef, useState, useCallback } from "react";
import cytoscape from "cytoscape";
import { GraphData, GraphNode } from "@/lib/types";
import { ZoomIn, ZoomOut, Maximize } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface KnowledgeGraphProps {
  graphData: GraphData | undefined;
}

export function KnowledgeGraph({ graphData }: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode["data"] | null>(null);

  const initGraph = useCallback(() => {
    if (!containerRef.current || !graphData) return;

    if (cyRef.current) cyRef.current.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...graphData.elements.nodes.map((n) => ({ data: n.data, group: "nodes" as const })),
        ...graphData.elements.edges.map((e) => ({ data: e.data, group: "edges" as const })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#0d1117",
            "border-width": 2,
            "border-color": "#00e5ff",
            label: "data(label)",
            color: "#e0e6ed",
            "font-size": "10px",
            "font-family": "JetBrains Mono, monospace",
            "text-valign": "bottom",
            "text-margin-y": 6,
            width: 30,
            height: 30,
          },
        },
        {
          selector: "node[?active]",
          style: {
            "border-color": "#00e5ff",
            "border-width": 3,
            "background-color": "rgba(0, 229, 255, 0.15)",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "rgba(0, 229, 255, 0.3)",
            "target-arrow-color": "rgba(0, 229, 255, 0.5)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "8px",
            color: "rgba(0, 229, 255, 0.5)",
            "font-family": "JetBrains Mono, monospace",
            "text-rotation": "autorotate",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#00e5ff",
            "border-width": 4,
            "background-color": "rgba(0, 229, 255, 0.25)",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        padding: 40,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 120,
      },
      minZoom: 0.3,
      maxZoom: 3,
    });

    cy.on("tap", "node", (e) => {
      const nodeData = e.target.data();
      setSelectedNode(nodeData);
    });

    cy.on("tap", (e) => {
      if (e.target === cy) setSelectedNode(null);
    });

    cyRef.current = cy;
  }, [graphData]);

  useEffect(() => {
    initGraph();
    return () => {
      cyRef.current?.destroy();
    };
  }, [initGraph]);

  return (
    <div className="flex flex-1 h-full relative">
      {/* Graph */}
      <div className="flex-1 relative">
        <div ref={containerRef} className="absolute inset-0 bg-background/50 rounded-lg border border-border" />

        {/* Scanline overlay */}
        <div className="absolute inset-0 scanlines pointer-events-none opacity-20 rounded-lg" />

        {/* Controls */}
        <div className="absolute top-3 right-3 flex flex-col gap-1.5 z-10">
          <Button
            size="icon"
            variant="outline"
            className="h-7 w-7 bg-card/80 border-border"
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.3)}
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="outline"
            className="h-7 w-7 bg-card/80 border-border"
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.7)}
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="outline"
            className="h-7 w-7 bg-card/80 border-border"
            onClick={() => cyRef.current?.fit(undefined, 40)}
          >
            <Maximize className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Detail Panel */}
      {selectedNode && (
        <div className="w-64 border-l border-border bg-card/80 backdrop-blur-sm p-4 space-y-4 animate-in slide-in-from-right-4">
          <div>
            <h3 className="text-sm font-bold text-neon-cyan">{selectedNode.label}</h3>
            <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              {selectedNode.type}
            </p>
            {selectedNode.active && (
              <span className="inline-block mt-1 text-[9px] font-mono text-neon-green animate-pulse-neon">
                ● ACTIVE
              </span>
            )}
          </div>

          {selectedNode.triples && selectedNode.triples.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                Semantic Triples
              </h4>
              <ScrollArea className="max-h-48">
                <div className="space-y-1.5">
                  {selectedNode.triples.map((t, i) => (
                    <div
                      key={i}
                      className="text-[10px] font-mono p-2 rounded bg-muted/50 border border-border space-y-0.5"
                    >
                      <p className="text-foreground">{t.subject}</p>
                      <p className="text-neon-cyan">→ {t.predicate}</p>
                      <p className="text-muted-foreground">{t.object}</p>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}

          <Button
            size="sm"
            variant="ghost"
            className="w-full text-xs text-muted-foreground"
            onClick={() => setSelectedNode(null)}
          >
            Close
          </Button>
        </div>
      )}
    </div>
  );
}
