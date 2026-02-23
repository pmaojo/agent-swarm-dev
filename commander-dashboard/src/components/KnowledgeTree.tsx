import { KnowledgeNode } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface KnowledgeTreeProps {
  nodes: KnowledgeNode[];
}

export function KnowledgeTree({ nodes }: KnowledgeTreeProps) {
  const grouped = nodes.reduce<Record<string, KnowledgeNode[]>>((acc, node) => {
    if (!acc[node.domain]) {
      acc[node.domain] = [];
    }
    acc[node.domain].push(node);
    return acc;
  }, {});

  const domains = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 h-full overflow-auto pb-3">
      {domains.map((domain) => (
        <Card key={domain} className="bg-card/50 border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-mono text-neon-cyan">{domain}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {grouped[domain]
              .sort((a, b) => a.level - b.level)
              .map((node) => (
                <div key={node.id} className="rounded border border-border p-2 bg-muted/30">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-sm">{node.name}</p>
                    <Badge variant={node.unlocked ? "default" : "outline"}>
                      {node.unlocked ? "Unlocked" : "Locked"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{node.capability}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Nivel {node.level} · Budget {node.cost.budget} · Tiempo {node.cost.time_hours}h
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Prerrequisitos: {node.prerequisites.length ? node.prerequisites.join(", ") : "—"}
                  </p>
                </div>
              ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
