import { Activity, Wifi, WifiOff } from "lucide-react";
import { GameState } from "@/lib/types";
import { Progress } from "@/components/ui/progress";

interface HeaderProps {
  gameState: GameState | undefined;
  isConnected: boolean;
}

export function Header({ gameState, isConnected }: HeaderProps) {
  const budget = gameState?.daily_budget;
  const budgetPercent = budget ? (budget.spent / budget.max) * 100 : 0;
  const status = gameState?.system_status ?? "UNKNOWN";

  const statusColor =
    status === "OPERATIONAL"
      ? "text-neon-green"
      : status === "DEGRADED"
      ? "text-neon-amber"
      : "text-neon-crimson";

  return (
    <header className="flex items-center justify-between border-b border-border px-4 py-3 bg-card/50 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <Activity className="h-5 w-5 text-neon-cyan" />
        <h1 className="text-lg font-bold tracking-wider text-neon-cyan uppercase">
          Command Center
        </h1>
        <span className={`text-xs font-mono uppercase tracking-widest ${statusColor}`}>
          ● {status}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 min-w-[200px]">
          <span className="text-xs text-muted-foreground font-mono">BUDGET</span>
          <div className="flex-1 relative">
            <Progress value={budgetPercent} className="h-2 bg-muted" />
            <div
              className="absolute inset-0 h-2 rounded-full"
              style={{
                width: `${budgetPercent}%`,
                background: "linear-gradient(90deg, hsl(190 100% 50%), hsl(270 80% 60%))",
                boxShadow: "0 0 8px hsl(190 100% 50% / 0.5)",
              }}
            />
          </div>
          <span className="text-xs font-mono text-foreground">
            ${budget?.spent.toFixed(2) ?? "0"}/{budget?.max ?? "0"} {budget?.unit}
          </span>
        </div>

        <div className="flex items-center gap-1 text-xs font-mono">
          {isConnected ? (
            <Wifi className="h-3.5 w-3.5 text-neon-green" />
          ) : (
            <WifiOff className="h-3.5 w-3.5 text-neon-amber" />
          )}
          <span className={isConnected ? "text-neon-green" : "text-neon-amber"}>
            {isConnected ? "POLLING" : "MOCK"}
          </span>
        </div>
      </div>
    </header>
  );
}
