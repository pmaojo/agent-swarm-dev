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
    <div className="p-4 h-full flex flex-col gap-4 overflow-y-auto">
      <Card className="bg-black/40 border-neon-cyan/20">
        <CardHeader>
          <CardTitle className="text-neon-cyan flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Citadel Command
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-neon-cyan/80">Select Agent</Label>
            <Select onValueChange={setSelectedAgent} value={selectedAgent}>
              <SelectTrigger className="bg-black/20 border-white/10">
                <SelectValue placeholder="Choose an agent..." />
              </SelectTrigger>
              <SelectContent>
                {agents.map((agent) => (
                  <SelectItem key={agent.id} value={agent.id}>
                    <div className="flex items-center gap-2">
                      <User className="h-4 w-4" />
                      {agent.name} ({agent.class})
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-neon-cyan/80">Target Repository</Label>
            <Select onValueChange={setSelectedRepo} value={selectedRepo}>
              <SelectTrigger className="bg-black/20 border-white/10">
                <SelectValue placeholder="Select target building..." />
              </SelectTrigger>
              <SelectContent>
                {repositories.map((repo) => (
                  <SelectItem key={repo.id} value={repo.id}>
                    <div className="flex items-center gap-2">
                      <Building className="h-4 w-4" />
                      {repo.name} ({repo.tasks_pending} tasks)
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-neon-cyan/80">Mission Directive</Label>
            <Textarea
              placeholder="Enter mission details..."
              className="bg-black/20 border-white/10 min-h-[100px]"
              value={missionTask}
              onChange={(e) => setMissionTask(e.target.value)}
            />
          </div>

          <Button
            className="w-full bg-neon-cyan/20 text-neon-cyan hover:bg-neon-cyan/30 border border-neon-cyan/50"
            onClick={handleAssign}
            disabled={assignMutation.isPending}
          >
            {assignMutation.isPending ? "Transmitting..." : "Deploy Agent"}
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-black/40 border-white/10 flex-1 overflow-hidden">
        <CardHeader className="pb-2">
            <CardTitle className="text-white/60 text-sm">Citadel Visualization (Godot)</CardTitle>
        </CardHeader>
        <CardContent className="h-full p-0 relative min-h-[400px]">
             <iframe
                src="/godot/index.html"
                className="w-full h-full absolute inset-0 border-0 rounded-b-md"
                title="Citadel Godot Visualization"
                allow="cross-origin-isolated"
             />
        </CardContent>
      </Card>
    </div>
  );
}
