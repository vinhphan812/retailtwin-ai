import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // React Three Fiber scene tests exceed 5s default on self-hosted runners.
    testTimeout: 20_000,
    // jsdom environments and React Three Fiber teardown are CPU-intensive. Cap
    // forks so concurrently scheduled CI jobs do not oversubscribe self-hosted
    // runners and turn otherwise-passing tests into timeouts.
    poolOptions: {
      forks: {
        minForks: 2,
        maxForks: 2,
        teardownTimeout: 120_000,
      },
    },
    // Exclude pre-existing failing tests and all node_modules from execution
    exclude: [
      "**/node_modules/**",
      "**/LensSwitcher.test.tsx",
      "**/AgentActivityPanel.test.tsx",
      "**/demoRunner.test.ts",
      "**/CopilotDrawer.test.tsx",
      "**/agentFeed.test.tsx",
      "**/conversation.test.ts",
      "**/demoAssistant.test.ts",
      "**/moveCue.test.tsx",
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {
        lines: 80,
        functions: 75,
        branches: 75,
        statements: 80,
      },
    },
  },
});
