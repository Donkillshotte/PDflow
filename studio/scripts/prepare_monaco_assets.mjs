import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const studioRoot = path.resolve(scriptsDir, "..");
const source = path.join(studioRoot, "node_modules", "monaco-editor", "min", "vs");
const destination = path.join(studioRoot, "public", "monaco", "vs");
const sourceLoader = path.join(source, "loader.js");
const destinationLoader = path.join(destination, "loader.js");

if (!fs.existsSync(sourceLoader)) {
  console.error("FAIL: Monaco runtime is unavailable; run npm ci in studio/");
  process.exit(1);
}

const sourceSize = fs.statSync(sourceLoader).size;
const destinationSize = fs.existsSync(destinationLoader)
  ? fs.statSync(destinationLoader).size
  : -1;

if (sourceSize !== destinationSize) {
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, { recursive: true, force: true });
}

console.log(`MONACO_RUNTIME_READY ${path.relative(studioRoot, destination)}`);
