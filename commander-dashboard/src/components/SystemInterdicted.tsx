import { ShieldAlert } from "lucide-react";

export function SystemInterdicted() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/95 backdrop-blur-md animate-warning-pulse">
      {/* Scanlines */}
      <div className="absolute inset-0 scanlines pointer-events-none opacity-40" />

      {/* Red glow overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(circle at center, hsl(0 85% 55% / 0.15) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 flex flex-col items-center gap-6 text-center">
        <div className="p-6 rounded-full neon-glow-crimson border-2 neon-border-crimson">
          <ShieldAlert className="h-16 w-16 text-neon-crimson" />
        </div>

        <h1 className="text-4xl font-black tracking-[0.3em] uppercase text-neon-crimson">
          System Interdicted
        </h1>

        <p className="text-sm font-mono text-muted-foreground max-w-md">
          All agent operations have been suspended by the Sovereign Kill Switch.
          Manual intervention required to resume operations.
        </p>

        <div className="flex items-center gap-2 text-[10px] font-mono text-neon-crimson animate-pulse-neon">
          <span className="inline-block h-2 w-2 rounded-full bg-neon-crimson" />
          EMERGENCY SEAL ACTIVE
        </div>
      </div>
    </div>
  );
}
