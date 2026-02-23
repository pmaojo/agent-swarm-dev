import { useState } from "react";
import { ShieldAlert, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AuditRecord,
  CommandAck,
  ControlCommandType,
  GuardrailEntry,
  SovereignCommand,
  SovereignControlStatus,
} from "@/lib/types";

interface SovereignControlsProps {
  onSendCommand: (command: SovereignCommand) => void;
  isSubmitting: boolean;
  guardrailLog: GuardrailEntry[];
  sovereignStatus?: SovereignControlStatus;
  latestAck?: CommandAck;
  auditLog: AuditRecord[];
}

const severityStyle: Record<string, string> = {
  LOW: "text-muted-foreground",
  MEDIUM: "text-neon-amber",
  HIGH: "text-neon-crimson",
  CRITICAL: "text-neon-crimson font-bold",
};

const commandOptions: ControlCommandType[] = [
  "HALT",
  "RESUME",
  "ASSIGN_MISSION",
  "SET_AGENT_PRIORITY",
  "DEPLOY",
  "ROLLBACK",
  "CONFIGURE_AGENT_MODEL",
];

export function SovereignControls({
  onSendCommand,
  isSubmitting,
  guardrailLog,
  sovereignStatus,
  latestAck,
  auditLog,
}: SovereignControlsProps) {
  const [commandType, setCommandType] = useState<ControlCommandType>("HALT");

  return (
    <footer className="border-t border-border bg-card/50 backdrop-blur-sm px-4 py-2">
      <div className="grid grid-cols-4 gap-4 h-32">
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-mono uppercase text-muted-foreground">Sovereign Controls</span>
          <select
            className="bg-background border border-border rounded text-xs font-mono px-2 py-1"
            value={commandType}
            onChange={(event) => setCommandType(event.target.value as ControlCommandType)}
          >
            {commandOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <Button
            variant="destructive"
            onClick={() =>
              onSendCommand({
                command: commandType,
                actor: "sovereign-operator",
                nist_policy_id: sovereignStatus?.policy_id ?? "NIST-800-53-REV5",
                approved_by: sovereignStatus?.approved_by ?? "security-council",
                llm_profile: {
                  provider: "OpenAI",
                  model: commandType === "CONFIGURE_AGENT_MODEL" ? "gpt-5-mini" : "gpt-5",
                  hierarchy: commandType === "CONFIGURE_AGENT_MODEL" ? "minion" : "champion",
                },
              })
            }
            disabled={isSubmitting}
            className="neon-glow-crimson font-mono text-xs uppercase tracking-widest px-3 py-2 h-auto"
          >
            <ShieldAlert className="h-4 w-4 mr-2" />
            Dispatch Command
          </Button>
          <span className="text-[9px] font-mono text-muted-foreground">POST /api/v1/control/commands</span>
        </div>

        <div className="text-[10px] font-mono">
          <div className="uppercase text-muted-foreground mb-1">Policy Status</div>
          <div className="flex items-center gap-1">
            {sovereignStatus?.approved ? (
              <CheckCircle2 className="h-3 w-3 text-green-400" />
            ) : (
              <XCircle className="h-3 w-3 text-red-400" />
            )}
            <span>{sovereignStatus?.approved ? "Approved" : "Pending Approval"}</span>
          </div>
          <div>Policy: {sovereignStatus?.policy_id ?? "NIST-800-53-REV5"}</div>
          <div>By: {sovereignStatus?.approved_by ?? "-"}</div>
          {latestAck && <div>Last: {latestAck.status} ({latestAck.final_state ?? "N/A"})</div>}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="h-3 w-3 text-neon-amber" />
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
              NIST Guardrails
            </span>
          </div>
          <ScrollArea className="h-24">
            <div className="space-y-0.5">
              {guardrailLog.map((entry) => (
                <div key={entry.id} className="flex items-start gap-2 text-[10px] font-mono">
                  <span className="text-muted-foreground shrink-0">[{entry.timestamp}]</span>
                  <span className={`shrink-0 ${severityStyle[entry.severity]}`}>{entry.severity}</span>
                  <span className="text-foreground truncate">{entry.reason}</span>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Bidirectional confirmations</div>
          <ScrollArea className="h-24">
            <div className="space-y-1 text-[10px] font-mono">
              {auditLog.slice(-5).map((record) => (
                <div key={`${record.tracking_id}-${record.phase}`}>
                  [{record.phase}] {record.command} · {record.actor}
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      </div>
    </footer>
  );
}
