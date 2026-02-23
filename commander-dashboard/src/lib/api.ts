import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AuditRecord, GameState, GraphData, SovereignCommand } from "./types";

const RUST_GATEWAY_BASE = import.meta.env.VITE_RUST_GATEWAY_URL ?? "http://localhost:18789";
const API_BASE = `${RUST_GATEWAY_BASE}/api/v1`;

async function fetchFromApi<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return await res.json();
}

export function useGameState() {
  return useQuery<GameState>({
    queryKey: ["game-state"],
    queryFn: () => fetchFromApi("/game-state"),
    refetchInterval: 5000,
  });
}

export function useGraphData() {
  return useQuery<GraphData>({
    queryKey: ["graph-data"],
    queryFn: () => fetchFromApi("/graph-nodes"),
    refetchInterval: 5000,
  });
}

export function useAuditLog() {
  return useQuery<AuditRecord[]>({
    queryKey: ["audit-log"],
    queryFn: () => fetchFromApi("/control/audit"),
    refetchInterval: 3000,
  });
}

export function useSendSovereignCommand() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: async (command: SovereignCommand) => {
      const res = await fetch(`${API_BASE}/control/commands`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(command),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
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
