import { RUNTIME_BASE_URL } from "./config";
import type { RuntimeHealth } from "../types/runtime";

export async function getRuntimeHealth(): Promise<RuntimeHealth> {
  const response = await fetch(`${RUNTIME_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Runtime health failed: ${response.status}`);
  }
  return (await response.json()) as RuntimeHealth;
}
