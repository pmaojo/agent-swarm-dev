/* @vitest-environment node */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer, type ViteDevServer } from "vite";
import viteConfig from "../../vite.config";

const HOST = "127.0.0.1";
const PORT = 4180;

const expectedHeaders = {
  "cross-origin-opener-policy": "same-origin",
  "cross-origin-embedder-policy": "require-corp",
  "cross-origin-resource-policy": "cross-origin",
} as const;

let server: ViteDevServer;

beforeAll(async () => {
  const config = viteConfig({
    command: "serve",
    mode: "test",
    isSsrBuild: false,
    isPreview: false,
  });

  server = await createServer({
    ...config,
    server: {
      ...config.server,
      host: HOST,
      port: PORT,
      strictPort: true,
    },
  });

  await server.listen();
});

afterAll(async () => {
  await server.close();
});

describe("godot static assets headers", () => {
  it("serves /godot/index.js with expected MIME and COOP/COEP/CORP headers", async () => {
    const response = await fetch(`http://${HOST}:${PORT}/godot/index.js`);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("javascript");

    for (const [headerName, expectedValue] of Object.entries(expectedHeaders)) {
      expect(response.headers.get(headerName)).toBe(expectedValue);
    }
  });
});
