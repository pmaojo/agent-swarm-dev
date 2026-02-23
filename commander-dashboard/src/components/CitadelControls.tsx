import { useState } from "react";
import { Agent, Repository } from "@/lib/types";
import { useAssignMission } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Rocket, Building, User } from "lucide-react";
import { toast } from "sonner";

interface CitadelControlsProps {
  agents: Agent[];
  repositories: Repository[];
}

export function CitadelControls({ agents, repositories }: CitadelControlsProps) {
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [missionTask, setMissionTask] = useState<string>("");

  const assignMutation = useAssignMission();

  const handleAssign = () => {
    if (!selectedAgent || !selectedRepo || !missionTask) {
      toast.error("Please fill in all fields.");
      return;
    }

    assignMutation.mutate(
      {
        agent_id: selectedAgent,
        repo_id: selectedRepo,
        task: missionTask,
      },
      {
        onSuccess: () => {
          toast.success("Mission Assigned successfully!");
          setMissionTask("");
        },
        onError: () => {
          toast.error("Failed to assign mission.");
        },
      }
    );
  };

  return (
    <div className="flex h-full w-full relative">
      {/* Absolute Godot iframe to fill the entire TabsContent space */}
      <div className="absolute inset-0 z-0 bg-black">
        <iframe
          src="/godot/index.html"
          className="w-full h-full border-0"
          title="Citadel Godot Visualization"
          allow="cross-origin-isolated"
        />
      </div>

      {/* Floating Citadel Controls on the bottom right side */}
      <div className="z-10 absolute right-4 bottom-4 w-80 max-h-[calc(100%-2rem)] overflow-y-auto">
        <Card className="bg-black/70 backdrop-blur-md border-neon-cyan/40 shadow-xl shadow-cyan-900/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-neon-cyan flex items-center gap-2 text-lg">
              <Rocket className="h-5 w-5" />
              Citadel Command
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-neon-cyan/80 text-xs uppercase tracking-wider">Deploy Agent</Label>
              <Select onValueChange={setSelectedAgent} value={selectedAgent}>
                <SelectTrigger className="bg-black/40 border-white/20 h-9">
                  <SelectValue placeholder="Choose unit..." />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      <div className="flex items-center gap-2 text-sm">
                        <User className="h-3.5 w-3.5" />
                        {agent.name}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-neon-cyan/80 text-xs uppercase tracking-wider">Target</Label>
              <Select onValueChange={setSelectedRepo} value={selectedRepo}>
                <SelectTrigger className="bg-black/40 border-white/20 h-9">
                  <SelectValue placeholder="Choose structure..." />
                </SelectTrigger>
                <SelectContent>
                  {repositories.map((repo) => (
                    <SelectItem key={repo.id} value={repo.id}>
                      <div className="flex items-center gap-2 text-sm">
                        <Building className="h-3.5 w-3.5" />
                        {repo.name}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-neon-cyan/80 text-xs uppercase tracking-wider">Mission Data</Label>
              <Textarea
                placeholder="Enter directives..."
                className="bg-black/40 border-white/20 min-h-[80px] text-sm resize-none"
                value={missionTask}
                onChange={(e) => setMissionTask(e.target.value)}
              />
            </div>

            <Button
              className="w-full bg-neon-cyan/20 text-neon-cyan hover:bg-neon-cyan/30 border border-neon-cyan/50 mt-2"
              onClick={handleAssign}
              disabled={assignMutation.isPending}
            >
              {assignMutation.isPending ? "Transmitting..." : "Execute Deploy"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
