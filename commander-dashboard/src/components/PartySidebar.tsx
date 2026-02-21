import { Agent } from "@/lib/types";
import { CharacterCard } from "./CharacterCard";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Users } from "lucide-react";

export function PartySidebar({ party }: { party: Agent[] }) {
  return (
    <aside className="w-64 border-r border-border bg-sidebar flex flex-col shrink-0">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <Users className="h-4 w-4 text-neon-cyan" />
        <h2 className="text-xs font-bold tracking-widest uppercase text-neon-cyan">
          The Party
        </h2>
      </div>
      <ScrollArea className="flex-1 p-3">
        <div className="space-y-3">
          {party.map((agent) => (
            <CharacterCard key={agent.id} agent={agent} />
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
}
