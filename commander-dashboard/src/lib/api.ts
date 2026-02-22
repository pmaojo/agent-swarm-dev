import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GameState, GraphData } from "./types";
import { mockGameState, mockGraphData } from "./mock-data";

const API_BASE = "/api/v1";

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

export function useHaltSystem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        const res = await fetch(`${API_BASE}/halt`, { method: "POST" });
        if (!res.ok) throw new Error();
        return await res.json();
      } catch {
        // Mock: toggle to HALTED
        return { status: "HALTED" };
      }
    },
    onSuccess: () => {
      qc.setQueryData<GameState>(["game-state"], (old) =>
        old ? { ...old, system_status: "HALTED" } : old
      );
    },
  });
}

export function useAssignMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (mission: { agent_id: string; repo_id: string; task: string }) => {
      const res = await fetch(`${API_BASE}/mission/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mission),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["game-state"] });
    },
  });
}
