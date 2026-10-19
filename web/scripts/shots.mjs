// Скриншоты workbench: node shot.mjs <base> <outdir>
import { chromium } from "playwright";
const [base, out] = [process.argv[2], process.argv[3]];
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.screenshot({ path: out + "/01-projects.png" });
await page.goto(base + "/p/bracket/A_fork", { waitUntil: "networkidle" });
await page.waitForSelector("canvas", { timeout: 20000 });
await page.waitForTimeout(2500);
await page.screenshot({ path: out + "/03-variant.png" });
// клик по предупреждению про шов → подсветка
const ref = page.getByRole("button", { name: /^weld:/ }).first();
if (await ref.count()) { await ref.click(); await page.waitForTimeout(800); await page.screenshot({ path: out + "/03-variant-weld.png" }); }
// разрез
await page.getByLabel("Разрез").check();
await page.waitForTimeout(500);
await page.getByRole("button", { name: "Главный" }).click();
await page.waitForTimeout(800);
await page.screenshot({ path: out + "/03-variant-clip.png" });
const webgl = await page.evaluate(() => { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); });
console.log(JSON.stringify({ webgl, errors: errors.slice(0, 5) }));
await browser.close();
