// Приёмка M2.2: граф связей — поиск по всем проектам, блок «Связи», «Где используется», инструменты агента
// (docs/architecture/07-m2-2-graph-plan.md). node scripts/acceptance-m2-2.mjs <base> <outdir>  (сервер без входа)
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
const [base, out] = [process.argv[2], process.argv[3]];
const browser = await chromium.launch({
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
const log = [];
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
const step = async (name, fn) => {
  const t0 = Date.now();
  try {
    const info = (await fn()) ?? "";
    log.push({ step: name, ok: true, ms: Date.now() - t0, info });
  } catch (e) {
    log.push({ step: name, ok: false, ms: Date.now() - t0, info: e.message.split("\n")[0] });
    await page.screenshot({ path: `${out}/fail-${log.length}.png` });
  }
};
const shot = (n) => page.screenshot({ path: `${out}/${n}.png` });
const mcp = async (name, args) => {
  const r = await fetch(base + "/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message);
  const txt = j.result.content.find((c) => c.type === "text")?.text ?? "{}";
  try {
    return JSON.parse(txt);
  } catch {
    return { summary: txt };
  }
};

await step("0. индекс поднят: /health graph ok, сводка не пустая", async () => {
  const h = await (await fetch(base + "/health")).json();
  if (h.graph !== "ok") throw new Error("graph: " + h.graph);
  const st = await (await fetch(base + "/api/graph/stats")).json();
  if (!(st.entities > 0 && st.relations > 0)) throw new Error("пустой индекс");
  return `сущностей ${st.entities}, связей ${st.relations}, проектов ${new Set(st.state.map((s) => s.project)).size}`;
});

await step("1. поиск «wall» со страницы «Проекты»: базы, интерфейсы, обстановка", async () => {
  await page.goto(base + "/?q=wall");
  await page.waitForSelector(".search__list a");
  const refs = await page.$$eval(".search__list .mono", (els) => els.map((e) => e.textContent));
  if (!refs.includes("datum:wall") || !refs.includes("surrounding:wall_body")) throw new Error(refs.join(", "));
  await shot("14-projects-search");
  return refs.slice(0, 8).join(", ");
});

await step("2. ссылка ведёт в компоновку с выделенной базой; блок «Связи» показывает интерфейс и проект", async () => {
  await page.click('.search__list a:has-text("datum:wall")');
  await page.waitForURL(/mode=layout&ref=datum%3Awall/);
  await page.waitForSelector(".links .links__item");
  const items = await page.$$eval(".links .links__item .mono", (els) => els.map((e) => e.textContent));
  if (!items.includes("interface:wall")) throw new Error(items.join(", "));
  await page.waitForSelector(".sketch svg");
  const selected = await page.$$eval(".sketch [data-ref].selected", (els) => els.length);
  if (selected === 0) throw new Error("база не выделена на эскизе");
  await shot("14-variant-links-layout");
  return items.join(", ");
});

await step("3. клик по связи «interface:wall» выделяет интерфейс; «← ссылаются» показывает узел варианта", async () => {
  await page.click('.links .links__item:has-text("interface:wall")');
  await page.waitForFunction(() => document.querySelector(".links__root")?.textContent?.includes("interface:wall"));
  const groups = await page.$$eval(".links__group > .muted", (els) => els.map((e) => e.textContent));
  if (!groups.some((g) => g.includes("привязан к базе"))) throw new Error(groups.join(" | "));
  return groups.join(" | ");
});

await step(
  "4. деталь в 3D: «Связи» — отверстия, материал, узел; «Где используется» материала по проектам",
  async () => {
    await page.goto(base + "/p/bracket/A_fork?part=base_plate");
    await page.waitForSelector(".links .links__item");
    const items = await page.$$eval(".links .links__item .mono", (els) => els.map((e) => e.textContent));
    if (!items.some((i) => i.includes("/hole:")) || !items.includes("material:St3sp"))
      throw new Error(items.join(", "));
    await shot("14-variant-links-part");
    await page.click('.links .links__item:has-text("material:St3sp")');
    await page.waitForFunction(() => document.querySelector(".links__root")?.textContent?.includes("material:St3sp"));
    await page.click('button:has-text("Где используется")');
    await page.waitForSelector(".links__list a");
    const uses = await page.$$eval(".links__list a .mono", (els) => els.map((e) => e.textContent));
    const projects = await page.$$eval(".links__list li .small", (els) => els.map((e) => e.textContent));
    await shot("14-where-used");
    return `использований ${uses.length}; ${projects.slice(0, 3).join(" | ")}`;
  },
);

await step("5. агент: search / links / where_used отвечают текстом и данными", async () => {
  const s = await mcp("search", { query: "M16" });
  if (!s.hits?.length) throw new Error("search пуст");
  const l = await mcp("links", { project: "bracket", ref: "interface:wall" });
  if (!l.summary?.includes("привязан к базе")) throw new Error("links: " + l.summary);
  const w = await mcp("where_used", { ref: "material:St3sp" });
  if (!w.by_project?.bracket) throw new Error("where_used: " + JSON.stringify(w.by_project));
  return `search: ${s.hits.length}; links: ${l.nodes.length} узлов; where_used: ${JSON.stringify(w.by_project)}`;
});

await step("6. индекс обновляется после коммита агента: новое имя базы видно в «Связях»", async () => {
  const f = await mcp("files_read", { project: "bracket", path: "project.yaml" });
  const stamp = "приёмка " + Date.now().toString(36).slice(-4);
  const text = f.content.replace(/name: "Лицевая плоскость стены[^"]*"/, `name: "Лицевая плоскость стены (${stamp})"`);
  if (text === f.content) throw new Error("не нашёл имя базы wall");
  await mcp("files_write", { project: "bracket", files: { "project.yaml": text }, message: "приёмка M2.2: имя базы" });
  const l = await mcp("links", { project: "bracket", ref: "datum:wall" });
  if (!l.root?.name?.includes(stamp)) throw new Error("имя не обновилось: " + l.root?.name);
  await page.goto(base + "/p/bracket/A_fork?mode=layout&ref=datum%3Awall");
  await page.waitForFunction((st) => document.querySelector(".links__root")?.textContent?.includes(st), stamp);
  return l.root.name;
});

await browser.close();
log.push({ step: "ошибки страницы", ok: errors.length === 0, ms: 0, info: errors.join("; ") });
writeFileSync(`${out}/acceptance.json`, JSON.stringify(log, null, 2));
for (const l of log) console.log(`${l.ok ? "OK " : "FAIL"} ${l.step} (${l.ms} мс) ${l.info}`);
process.exit(log.every((l) => l.ok) ? 0 : 1);
