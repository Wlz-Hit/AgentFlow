import { useEffect, useState } from "react";
import { getRuntimeHealth } from "../api/runtime";

type RuntimeStatus = "checking" | "connected" | "unavailable";

export function HomePage() {
  const [status, setStatus] = useState<RuntimeStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    async function probe() {
      try {
        const health = await getRuntimeHealth();
        if (!cancelled && health.status === "ok") {
          setStatus("connected");
        } else if (!cancelled) {
          setStatus("unavailable");
        }
      } catch {
        if (!cancelled) {
          setStatus("unavailable");
        }
      }
    }

    void probe();
    return () => {
      cancelled = true;
    };
  }, []);

  const runtimeLabel =
    status === "checking"
      ? "Runtime: checking..."
      : status === "connected"
        ? "Runtime: Connected"
        : "Runtime: unavailable";

  return (
    <main className="shell">
      <section className="panel">
        <h1>AgentFlow</h1>
        <p className="tagline">Local Agent Orchestration Runtime</p>
        <p className="status">{runtimeLabel}</p>
      </section>
    </main>
  );
}
