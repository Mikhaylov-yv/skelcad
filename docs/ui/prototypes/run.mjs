// Прогон одинаковых сценариев конструктора по всем макетам: node run.mjs [фильтр имени файла]
// Считает действия (щелчок, клавиша = 1; ввод текста = 2), ошибки JS, снимает скриншоты в shots/.
import { chromium } from "../../../web/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";
const DIR = path.dirname(new URL(import.meta.url).pathname);
const VARIANTS = JSON.parse(fs.readFileSync(path.join(DIR, "variants.json"), "utf8"));
const only = process.argv[2];
const log = (...a) => fs.writeSync(1, a.join(" ") + "\n");
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const results = fs.existsSync(path.join(DIR, "results.json")) ? JSON.parse(fs.readFileSync(path.join(DIR, "results.json"), "utf8")) : {};
fs.mkdirSync(path.join(DIR, "shots"), { recursive: true });

for (const v of VARIANTS) {
  if (only && !v.file.includes(only)) continue;
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(4000);
  const errors = [];
  page.on("pageerror", e => errors.push(e.message.slice(0, 160)));
  page.on("console", m => { if (m.type() === "error") errors.push("console: " + m.text().slice(0, 160)); });
  log("open", v.file);
  await page.goto("file://" + path.join(DIR, v.file));
  await page.waitForSelector(".tree, .gallery");
  await page.waitForTimeout(400);
  const name = await page.evaluate(() => window.proto.name);
  const state = () => page.evaluate(() => JSON.parse(JSON.stringify(window.proto.state())));
  const cur = () => page.evaluate(() => JSON.parse(JSON.stringify(window.proto.cur())));
  const next = pid => page.evaluate(pid => window.proto.next(pid), pid);
  const logOf = () => page.evaluate(() => window.proto.log());
  let count = 0;
  const vis = sel => page.locator(sel).filter({ visible: true }).first();
  const ui = {
    async click(sel) { count++; await vis(sel).click(); await page.waitForTimeout(80); },
    async press(key) { count++; await page.keyboard.press(key); await page.waitForTimeout(80); },
    async fill(sel, text) { count += 2; await vis(sel).fill(text); await page.waitForTimeout(40); },
  };
  const shot = n => page.screenshot({ path: path.join(DIR, "shots", v.file.replace(".html", `-${n}.png`)) });
  const treeVisible = async () => (await page.locator(".tree").filter({ visible: true }).count()) > 0;
  const drv = {
    async openTree() { if (v.tree === "drawer" && !(await treeVisible())) await ui.click('[data-act="pin"]'); },
    async openProject(pid) { await drv.openTree(); await ui.click(`[data-tree="project:${pid}"]`); },
    async openFolder(fid) { await drv.openTree(); const c = await cur(); if (c.folder !== fid || c.project) await ui.click(`[data-tree="folder:${fid}"]`); },
    async waitAgent(pid) { for (let i = 0; i < 50; i++) { const n = await next(pid); if (n.kind !== "running") return; await page.waitForTimeout(100); } },
  };
  // снимки: папка, агент за работой, результат, выбор варианта
  const ctl = await page.evaluate(() => {
    const vis = n => { const r = n.getBoundingClientRect(); if (!(r.width > 0 && r.height > 0 && r.top < innerHeight)) return false; for (let e = n; e; e = e.parentElement) { const st = getComputedStyle(e); if (st.visibility === "hidden" || +st.opacity < 0.05 || st.display === "none") return false; } return true; };
    const all = [...document.querySelectorAll("button, select, input, textarea, [data-act], [data-tree]")];
    return { visible: all.filter(vis).length, total: all.length };
  });
  await shot(0);
  await drv.openProject("bolt");
  await page.evaluate(() => { window.proto.core.speed = 100000; });
  await ui.click('[data-act="next"]');
  await page.waitForTimeout(300);
  await shot(1);
  await page.evaluate(() => { window.proto.core.stop("bolt"); window.proto.fast(); });
  await page.waitForTimeout(100);
  // Вернуть начальное состояние и считать сценарии
  await page.reload();
  await page.waitForSelector(".tree, .gallery");
  await page.evaluate(() => window.proto.fast());
  count = 0;
  const scenarios = [
    ["Открыть «Болт обычный М16» из дерева", async () => { await drv.openProject("bolt"); return (await cur()).project === "bolt"; }],
    ["Понять, что дальше, и поручить агенту детали", async () => { await ui.click('[data-act="next"]'); await drv.waitAgent("bolt"); const s = await state(); const p = s.projects.find(x => x.id === "bolt"); await shot(2); return p.design.state === "done" && p.design.variants.length === 1; }],
    ["Согласовать компоновку «Специальный болт»", async () => { await drv.openProject("sbolt"); await ui.click('[data-act="next"]'); const s = await state(); return s.projects.find(x => x.id === "sbolt").layout.state === "approved"; }],
    ["Выбрать вариант кронштейна B_hub", async () => { await drv.openProject("bracket"); await shot(3); await ui.click('[data-act="choose:B_hub"]'); const s = await state(); return s.projects.find(x => x.id === "bracket").design.chosen === "B_hub"; }],
    ["Выдать комплект по опоре под трубу", async () => { await drv.openProject("pipe_support"); await ui.click('[data-act="next"]'); await drv.waitAgent("pipe_support"); const s = await state(); return s.projects.find(x => x.id === "pipe_support").kit.state === "ready"; }],
    ["Скачать комплект планки", async () => { await drv.openProject("plate"); await ui.click('[data-act="download"]'); return (await logOf()).includes("download:plate"); }],
    ["Создать проект «Хомут трубы Ø57» в папке «Крепёж»", async () => { await drv.openFolder("krepezh"); await ui.click('[data-act="new-project"]'); await ui.fill('[data-field="title"]', "Хомут трубы Ø57"); await ui.click('[data-act="create"]'); const s = await state(); const p = s.projects.find(x => x.title === "Хомут трубы Ø57"); const c = await cur(); return !!p && p.folder === "krepezh" && c.project === p.id; }],
    ["Описать задание и получить компоновку", async () => { await ui.fill('[data-field="brief"]', "Хомут под трубу Ø57 на стене, два болта М10, нагрузка 1 кН вниз"); await ui.click('[data-act="next"]'); const c = await cur(); await drv.waitAgent(c.project); const s = await state(); const p = s.projects.find(x => x.id === c.project); await shot(4); return p.brief.done && p.layout.state === "waiting"; }],
    ["Создать папку «Насосы»", async () => { await drv.openTree(); await ui.click('[data-act="new-folder"]'); await ui.fill('[data-field="name"]', "Насосы"); await ui.click('[data-act="create"]'); const s = await state(); return s.folders.some(f => f.name === "Насосы"); }],
    ["Удалить проект «Планка» и вернуть", async () => { await drv.openProject("plate"); await ui.click('[data-act^="delete:"]'); const gone = !(await state()).projects.some(x => x.id === "plate"); await ui.click('#toast [data-act="undo"]'); const back = (await state()).projects.some(x => x.id === "plate"); return gone && back; }],
  ];
  const r = { file: v.file, name, scenarios: [], errors, controls: ctl, actions: 0, pass: 0 };
  for (const [title, fn] of scenarios) {
    const before = count;
    let ok = false, err = "";
    try { ok = await fn(); } catch (e) { err = e.message.split("\n")[0].slice(0, 140); }
    r.scenarios.push({ title, ok, actions: count - before, err });
    if (ok) r.pass++;
    log(`  ${ok ? "ok " : "FAIL"} ${count - before}  ${title}${err ? "  — " + err : ""}`);
  }
  r.actions = count;
  r.errors = errors;
  results[v.file] = r;
  log(`${name}: ${r.pass}/${scenarios.length}, действий ${count}, ошибок JS ${errors.length}`);
  await page.close();
}
await browser.close();
fs.writeFileSync(path.join(DIR, "results.json"), JSON.stringify(results, null, 1));
