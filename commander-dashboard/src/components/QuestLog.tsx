import { Quest } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

const stages = ["Requirements", "Design", "Todo", "In Progress"] as const;

const difficultyColor: Record<string, string> = {
  Easy: "neon-border-green text-neon-green",
  Medium: "neon-border-amber text-neon-amber",
  Hard: "neon-border-crimson text-neon-crimson",
  Legendary: "border-neon-purple text-neon-purple",
};

const stageGlow: Record<string, string> = {
  Requirements: "neon-border-amber",
  Design: "neon-border-cyan",
  Todo: "border-border",
  "In Progress": "neon-border-green",
};

export function QuestLog({ quests }: { quests: Quest[] }) {
  return (
    <div className="grid grid-cols-4 gap-3 h-full p-3">
      {stages.map((stage) => {
        const stageQuests = quests.filter((q) => q.stage === stage);
        return (
          <div key={stage} className="flex flex-col min-h-0">
            <div className="flex items-center gap-2 mb-2 px-1">
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-muted-foreground">
                {stage}
              </h3>
              <span className="text-[10px] font-mono text-muted-foreground bg-muted rounded-full px-1.5">
                {stageQuests.length}
              </span>
            </div>
            <ScrollArea className="flex-1">
              <div className="space-y-2 pr-1">
                {stageQuests.map((quest) => (
                  <div
                    key={quest.id}
                    className={`border rounded-lg p-3 bg-card/60 backdrop-blur-sm space-y-2 ${stageGlow[stage]}`}
                  >
                    <p className="text-sm font-medium text-foreground">{quest.title}</p>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Badge
                        variant="outline"
                        className={`text-[9px] font-mono py-0 ${difficultyColor[quest.difficulty] ?? ""}`}
                      >
                        {quest.difficulty}
                      </Badge>
                      {quest.assigned_agent && (
                        <Badge variant="outline" className="text-[9px] font-mono py-0 neon-border-cyan text-neon-cyan">
                          {quest.assigned_agent}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        );
      })}
    </div>
  );
}
