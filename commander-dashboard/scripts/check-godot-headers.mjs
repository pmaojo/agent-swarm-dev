import { access, readFile } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

const viteConfigPath = path.join(projectRoot, "vite.config.ts");
const godotJsPath = path.join(projectRoot, "public", "godot", "index.js");

const requiredHeaders = [
  '"Cross-Origin-Opener-Policy": "same-origin"',
  '"Cross-Origin-Embedder-Policy": "require-corp"',
  '"Cross-Origin-Resource-Policy": "cross-origin"',
];

const viteConfigContents = await readFile(viteConfigPath, "utf8");

for (const headerSnippet of requiredHeaders) {
  if (!viteConfigContents.includes(headerSnippet)) {
    throw new Error(`Missing required Vite header config: ${headerSnippet}`);
  }
}

await access(godotJsPath, constants.R_OK);

console.log("Godot header config check passed.");
