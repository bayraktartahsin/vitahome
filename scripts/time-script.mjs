#!/usr/bin/env node
/**
 * Guards the four-minute rule.
 *
 * The contest evaluates only the first four minutes of the demo video, so the
 * autopilot's running time is a correctness property, not a preference. This
 * reads web/lib/autopilot.ts and checks two things:
 *
 *   1. every spoken cue is held long enough to actually say it, at 2.6 words
 *      per second plus a breath — a cue that advances mid-sentence is a defect
 *   2. the whole run finishes under the ceiling, with margin
 *
 * Run it after any edit to the script. Non-zero exit means do not record.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const WORDS_PER_SEC = 2.6;   // ~155 wpm, an unhurried presenting pace
const BREATH_MS = 700;       // the pause between finishing a line and the cut
const CEILING_MS = 240_000;  // four minutes, hard
const TARGET_MS = 232_000;   // leave ~8s of margin for a slow read

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(join(root, "web/lib/autopilot.ts"), "utf8");

const body = src.split("SCRIPT: Step[] = [")[1]?.split("\n];")[0];
if (!body) {
  console.error("could not find SCRIPT in web/lib/autopilot.ts");
  process.exit(2);
}

const cues = [];
for (const block of ("\n" + body).split(/\n  \{/)) {
  const ms = block.match(/ms:\s*(\d+)/);
  if (!ms) continue;
  const say = block.match(/say:\s*"((?:[^"\\]|\\.)*)"/);
  const silent = /silent:\s*true/.test(block);
  const words = silent || !say ? 0 : say[1].split(/\s+/).filter(Boolean).length;
  cues.push({
    ms: Number(ms[1]),
    words,
    silent,
    text: say ? say[1] : "",
    need: words ? Math.round((words / WORDS_PER_SEC) * 1000) + BREATH_MS : 0,
  });
}

let total = 0, speech = 0, rushed = 0;
const fmt = (ms) => `${Math.floor(ms / 60000)}:${String(Math.round(ms % 60000 / 1000)).padStart(2, "0")}`;

console.log(`   at      hold    need   words  cue`);
for (const c of cues) {
  const at = total;
  total += c.ms;
  speech += c.words;
  const tight = c.need > c.ms;
  if (tight) rushed++;
  console.log(
    `${fmt(at).padStart(5)}  ${(c.ms / 1000).toFixed(1).padStart(6)}s ${
      (c.need / 1000).toFixed(1).padStart(6)}s ${String(c.words).padStart(6)}  ${
      c.silent ? "· " : "  "}${c.text.slice(0, 58)}${tight ? "   RUSHED" : ""}`,
  );
}

console.log(`\n  cues            ${cues.length}`);
console.log(`  spoken words    ${speech}`);
console.log(`  running time    ${fmt(total)}  (${(total / 1000).toFixed(1)}s)`);
console.log(`  margin to 4:00  ${((CEILING_MS - total) / 1000).toFixed(1)}s`);

let bad = false;
if (rushed) {
  console.log(`\n  FAIL  ${rushed} cue(s) advance before the line can be spoken`);
  bad = true;
}
if (total > TARGET_MS) {
  console.log(`\n  FAIL  ${fmt(total)} exceeds the ${fmt(TARGET_MS)} target ` +
              `(${fmt(CEILING_MS)} ceiling with margin)`);
  bad = true;
}
if (!bad) console.log(`\n  PASS  fits in four minutes with ${((CEILING_MS - total) / 1000).toFixed(0)}s to spare`);
process.exit(bad ? 1 : 0);
