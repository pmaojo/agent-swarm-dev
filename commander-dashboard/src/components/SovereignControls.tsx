import { ShieldAlert, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { GuardrailEntry } from "@/lib/types";

interface SovereignControlsProps {
  onHalt: () => void;
  isHalting: boolean;
  guardrailLog: GuardrailEntry[];
}

const severityStyle: Record<string, string> = {
  LOW: "text-muted-foreground",
  MEDIUM: "text-neon-amber",
  HIGH: "text-neon-crimson",
  CRITICAL: "text-neon-crimson font-bold",
};

export function SovereignControls({ onHalt, isHalting, guardrailLog }: SovereignControlsProps) {
  return (
    <footer className="border-t border-border bg-card/50 backdrop-blur-sm px-4 py-2">
      <div className="flex items-start gap-4 h-24">
        {/* Kill Switch */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <Button
            variant="destructive"
            onClick={onHalt}
            disabled={isHalting}
            className="neon-glow-crimson font-mono text-xs uppercase tracking-widest px-6 py-2 h-auto"
          >
            <ShieldAlert className="h-4 w-4 mr-2" />
            Emergency Seal
          </Button>
          <span className="text-[9px] font-mono text-muted-foreground">POST /api/v1/halt</span>
        </div>

        {/* Guardrail Log */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="h-3 w-3 text-neon-amber" />
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              NIST Guardrail Interceptions
            </span>
          </div>
          <ScrollArea className="h-16">
            <div className="space-y-0.5">
              {guardrailLog.map((entry) => (
                <div key={entry.id} className="flex items-start gap-2 text-[10px] font-mono">
                  <span className="text-muted-foreground shrink-0">[{entry.timestamp}]</span>
                  <span className={`shrink-0 ${severityStyle[entry.severity]}`}>
                    {entry.severity}
                  </span>
                  <span className="text-foreground truncate">{entry.reason}</span>
                  <span className="text-destructive/60 truncate">→ {entry.blocked_command}</span>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      </div>
    </footer>
  );
}
