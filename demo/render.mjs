import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const framesDir = path.join(here, "out", "frames");
const gifPath = path.join(here, "..", "docs", "demo.gif");

const serveUrl = await bundle({
  entryPoint: path.join(here, "src", "index.ts"),
});
const composition = await selectComposition({ serveUrl, id: "Flow" });

fs.rmSync(framesDir, { recursive: true, force: true });
fs.mkdirSync(framesDir, { recursive: true });

const only = process.argv.slice(2).map(Number).filter((n) => Number.isInteger(n));
const frames = only.length ? only : [...Array(composition.durationInFrames).keys()];

let cursor = 0;
const run = async () => {
  while (cursor < frames.length) {
    const frame = frames[cursor++];
    await renderStill({
      composition,
      serveUrl,
      frame,
      imageFormat: "png",
      output: path.join(framesDir, `f${String(frame).padStart(4, "0")}.png`),
    });
    process.stdout.write(`\r${cursor}/${frames.length}`);
  }
};

await Promise.all([run(), run(), run()]);
process.stdout.write("\n");

if (only.length) {
  console.log(framesDir);
  process.exit(0);
}

const python = process.env.PYTHON || "python3";
const py = spawnSync(python, [path.join(here, "gif.py"), framesDir, gifPath], {
  encoding: "utf-8",
});
if (py.status !== 0) {
  console.error(py.stderr || py.stdout);
  process.exit(py.status ?? 1);
}
console.log(py.stdout.trim());
