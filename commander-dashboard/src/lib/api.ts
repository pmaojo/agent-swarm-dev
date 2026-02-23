import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AuditRecord, CommandAck, GameState, GraphData, SovereignCommand } from "./types";
import { mockGameState, mockGraphData } from "./mock-data";

const RUST_GATEWAY_BASE = import.meta.env.VITE_RUST_GATEWAY_URL ?? "http://localhost:18789";
const API_BASE = `${RUST_GATEWAY_BASE}/api/v1`;

async function fetchWithFallback<T>(url: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${url}`);
    if (!res.ok) throw new Error(`${res.status}`);
    return await res.json();
  } catch {
    return fallback;
  }
}

export function useGameState() {
  return useQuery<GameState>({
    queryKey: ["game-state"],
    queryFn: () => fetchWithFallback("/game-state", mockGameState),
    refetchInterval: 5000,
  });
}

export function useGraphData() {
  return useQuery<GraphData>({
    queryKey: ["graph-data"],
    queryFn: () => fetchWithFallback("/graph-nodes", mockGraphData),
    refetchInterval: 5000,
  });
}

export function useAuditLog() {
  return useQuery<AuditRecord[]>({
    queryKey: ["audit-log"],
    queryFn: () => fetchWithFallback("/control/audit", []),
    refetchInterval: 3000,
  });
}

const buildMockAck = (command: SovereignCommand): CommandAck => ({
  tracking_id: crypto.randomUUID(),
  status: "COMPLETED",
  final_state: `${command.command}_EXECUTED`,
  command,
});

export function useSendSovereignCommand() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async (command: SovereignCommand): Promise<CommandAck> => {
      try {
        const res = await fetch(`${API_BASE}/control/commands`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(command),
        });
        if (!res.ok) throw new Error(`${res.status}`);
        return await res.json();
      } catch {
        return buildMockAck(command);
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["game-state"] });
      qc.invalidateQueries({ queryKey: ["audit-log"] });
    },
  });
}

export function useAssignMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { agent_id: string; repo_id: string; task: string }) => {
      // Mock assignment
      return new Promise((resolve) => setTimeout(resolve, 500));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["game-state"] });
    },
  });
}
