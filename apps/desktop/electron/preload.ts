import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("agentflowDesktop", {
  shell: "electron",
});
