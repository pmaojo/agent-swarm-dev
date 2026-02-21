import { Music, Wand2, Sword, Shield } from "lucide-react";
import { Agent, AgentClass } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

const classConfig: Record<AgentClass, { icon: React.ElementType; title: string; color: string }> = {
  Bard: { icon: Music, title: "Product Manager", color: "text-neon-amber" },
  Wizard: { icon: Wand2, title: "Architect", color: "text-neon-purple" },
  Warrior: { icon: Sword, title: "Coder", color: "text-neon-crimson" },
  Paladin: { icon: Shield, title: "Reviewer", color: "text-neon-green" },
};

// purple needs special handling since it's not in the neon-glow utilities
const classGlow: Record<AgentClass, string> = {
  Bard: "neon-glow-amber",
  Wizard: "neon-glow-cyan",
  Warrior: "neon-glow-crimson",
  Paladin: "neon-glow-green",
};

export function CharacterCard({ agent }: { agent: Agent }) {
  const config = classConfig[agent.class];
  const Icon = config.icon;
  const successRate = parseInt(agent.stats.success_rate);
  const manaPercent = (agent.stats.mana / 100) * 100;
  const hpPercent = agent.stats.hp;
  const isActive = agent.current_action.length > 0;

  return (
    <div
      className={`relative border border-border rounded-lg p-3 bg-card/80 backdrop-blur-sm transition-all duration-300 ${
        isActive ? `animate-glow-pulse ${classGlow[agent.class]}` : ""
      }`}
    >
      {/* Scanline overlay */}
      <div className="absolute inset-0 scanlines rounded-lg pointer-events-none opacity-30" />

      <div className="relative z-10 space-y-2.5">
        {/* Header */}
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded bg-muted ${config.color}`}>
            <Icon className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-foreground truncate">{agent.name}</p>
            <p className={`text-[10px] font-mono uppercase tracking-wider ${config.color}`}>
              {config.title}
            </p>
          </div>
        </div>

        {/* Mana Bar */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
            <span>MANA</span>
            <span>{agent.stats.mana}/100</span>
          </div>
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${manaPercent}%`,
                background: "linear-gradient(90deg, hsl(190 100% 50%), hsl(210 100% 60%))",
                boxShadow: "0 0 6px hsl(190 100% 50% / 0.5)",
              }}
            />
          </div>
        </div>

        {/* HP Bar */}
        <div className="space-y-0.5">
          <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
            <span>HP</span>
            <span>{successRate}%</span>
          </div>
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${hpPercent}%`,
                background:
                  hpPercent > 70
                    ? "linear-gradient(90deg, hsl(140 100% 45%), hsl(160 100% 40%))"
                    : hpPercent > 40
                    ? "linear-gradient(90deg, hsl(40 100% 55%), hsl(30 100% 50%))"
                    : "linear-gradient(90deg, hsl(0 85% 55%), hsl(10 90% 50%))",
                boxShadow:
                  hpPercent > 70
                    ? "0 0 6px hsl(140 100% 45% / 0.5)"
                    : "0 0 6px hsl(0 85% 55% / 0.5)",
              }}
            />
          </div>
        </div>

        {/* Battle log */}
        <div className="overflow-hidden h-5 bg-muted/50 rounded px-1.5 flex items-center">
          <p className="text-[10px] font-mono text-muted-foreground whitespace-nowrap animate-scroll-text">
            ⚔ {agent.current_action}
          </p>
        </div>

        {/* Location */}
        <Badge variant="outline" className="text-[9px] font-mono neon-border-cyan text-neon-cyan py-0 px-1.5">
          📍 {agent.location}
        </Badge>
      </div>
    </div>
  );
}
