import { useGameState, useGraphData, useHaltSystem } from "@/lib/api";
import { Header } from "@/components/Header";
import { PartySidebar } from "@/components/PartySidebar";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { QuestLog } from "@/components/QuestLog";
import { CitadelControls } from "@/components/CitadelControls";
import { SovereignControls } from "@/components/SovereignControls";
import { SystemInterdicted } from "@/components/SystemInterdicted";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Network, ScrollText, Rocket } from "lucide-react";

const Index = () => {
  const { data: gameState, isError: gsError } = useGameState();
  const { data: graphData, isError: gdError } = useGraphData();
  const haltMutation = useHaltSystem();

  const isConnected = !gsError && !gdError;
  const isHalted = gameState?.system_status === "HALTED";

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      {isHalted && <SystemInterdicted />}

      <Header gameState={gameState} isConnected={isConnected} />

      <div className="flex flex-1 min-h-0">
        <PartySidebar party={gameState?.party ?? []} />

        <main className="flex-1 flex flex-col min-h-0">
          <Tabs defaultValue="graph" className="flex-1 flex flex-col min-h-0">
            <TabsList className="mx-3 mt-3 w-fit bg-muted/50 border border-border">
              <TabsTrigger value="graph" className="font-mono text-xs data-[state=active]:text-neon-cyan gap-1.5">
                <Network className="h-3.5 w-3.5" />
                Knowledge Graph
              </TabsTrigger>
              <TabsTrigger value="quests" className="font-mono text-xs data-[state=active]:text-neon-cyan gap-1.5">
                <ScrollText className="h-3.5 w-3.5" />
                Quest Log
              </TabsTrigger>
              <TabsTrigger value="citadel" className="font-mono text-xs data-[state=active]:text-neon-cyan gap-1.5">
                <Rocket className="h-3.5 w-3.5" />
                Citadel Ops
              </TabsTrigger>
            </TabsList>

            <TabsContent value="graph" className="flex-1 min-h-0 px-3 pb-1">
              <KnowledgeGraph graphData={graphData} />
            </TabsContent>

            <TabsContent value="quests" className="flex-1 min-h-0 overflow-auto">
              <QuestLog quests={gameState?.active_quests ?? []} />
            </TabsContent>

            <TabsContent value="citadel" className="flex-1 min-h-0 overflow-auto">
              <CitadelControls agents={gameState?.party ?? []} repositories={gameState?.repositories ?? []} />
            </TabsContent>
          </Tabs>
        </main>
      </div>

      <SovereignControls
        onHalt={() => haltMutation.mutate()}
        isHalting={haltMutation.isPending}
        guardrailLog={gameState?.guardrail_log ?? []}
      />
    </div>
  );
};

export default Index;
