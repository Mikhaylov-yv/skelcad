// Прогон одинаковых сценариев конструктора по всем макетам: node run.mjs [фильтр имени файла]
// Считает действия (щелчок, клавиша = 1; ввод текста = 2), ошибки JS, снимает скриншоты в shots/.
// Два набора сценариев: "default" — папки и проекты (v01–v04), "nodes" — изделие из узлов и разговор (v05).
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
  const proj = async id => (await state()).projects.find(x => x.id === id);
  let count = 0;
  const vis = sel => page.locator(sel).filter({ visible: true }).first();
  const ui = {
    async click(sel) { count++; await vis(sel).click(); await page.waitForTimeout(80); },
    async press(key) { count++; await page.keyboard.press(key); await page.waitForTimeout(80); },
    async fill(sel, text) { count += 2; await vis(sel).fill(text); await page.waitForTimeout(40); },
  };
  const shot = n => page.screenshot({ path: path.join(DIR, "shots", v.file.replace(".html", `-${n}.png`)) });
  const treeVisible = async () => (await page.locator(".tree:not(.ntree)").filter({ visible: true }).count()) > 0;
  const drv = {
    async openTree() { if (v.tree === "drawer" && !(await treeVisible())) await ui.click('[data-act="pin"], [data-act="drawer"]'); },
    async openProject(pid) { await drv.openTree(); await ui.click(`[data-tree="project:${pid}"]`); },
    async openFolder(fid) { await drv.openTree(); const c = await cur(); if (c.folder !== fid || c.project) await ui.click(`[data-tree="folder:${fid}"]`); },
    async waitAgent(pid) { for (let i = 0; i < 50; i++) { const n = await next(pid); if (n.kind !== "running") return; await page.waitForTimeout(100); } },
    async liveShot(pid, n) { await page.evaluate(() => { window.proto.core.speed = 100000; }); await ui.click('[data-act="next"]'); await page.waitForTimeout(300); await shot(n); await page.evaluate(pid => { window.proto.core.stop(pid); window.proto.fast(); }, pid); await page.waitForTimeout(100); },
  };
  const ctl = await page.evaluate(() => {
    const vis = n => { const r = n.getBoundingClientRect(); if (!(r.width > 0 && r.height > 0 && r.top < innerHeight)) return false; for (let e = n; e; e = e.parentElement) { const st = getComputedStyle(e); if (st.visibility === "hidden" || +st.opacity < 0.05 || st.display === "none") return false; } return true; };
    const all = [...document.querySelectorAll("button, select, input, textarea, [data-act], [data-tree]")];
    return { visible: all.filter(vis).length, total: all.length };
  });

  const FLOWS = {
    // папки и проекты: снимки — папка, агент за работой, детали готовы, выбор варианта, новый проект
    default: {
      async shots() { await shot(0); await drv.openProject("bolt"); await drv.liveShot("bolt", 1); },
      scenarios: [
        ["Открыть «Болт обычный М16» из дерева", async () => { await drv.openProject("bolt"); return (await cur()).project === "bolt"; }],
        ["Понять, что дальше, и поручить агенту детали", async () => { await ui.click('[data-act="next"]'); await drv.waitAgent("bolt"); const p = await proj("bolt"); await shot(2); return p.design.state === "done" && p.design.variants.length === 1; }],
        ["Согласовать компоновку «Специальный болт»", async () => { await drv.openProject("sbolt"); await ui.click('[data-act="next"]'); return (await proj("sbolt")).layout.state === "approved"; }],
        ["Выбрать вариант кронштейна B_hub", async () => { await drv.openProject("bracket"); await shot(3); await ui.click('[data-act="choose:B_hub"]'); return (await proj("bracket")).design.chosen === "B_hub"; }],
        ["Выдать комплект по опоре под трубу", async () => { await drv.openProject("pipe_support"); await ui.click('[data-act="next"]'); await drv.waitAgent("pipe_support"); return (await proj("pipe_support")).kit.state === "ready"; }],
        ["Скачать комплект планки", async () => { await drv.openProject("plate"); await ui.click('[data-act="download"]'); return (await logOf()).includes("download:plate"); }],
        ["Создать проект «Хомут трубы Ø57» в папке «Крепёж»", async () => { await drv.openFolder("krepezh"); await ui.click('[data-act="new-project"]'); await ui.fill('[data-field="title"]', "Хомут трубы Ø57"); await ui.click('[data-act="create"]'); const s = await state(); const p = s.projects.find(x => x.title === "Хомут трубы Ø57"); const c = await cur(); return !!p && p.folder === "krepezh" && c.project === p.id; }],
        ["Описать задание и получить компоновку", async () => { await ui.fill('[data-field="brief"]', "Хомут под трубу Ø57 на стене, два болта М10, нагрузка 1 кН вниз"); await ui.click('[data-act="next"]'); const c = await cur(); await drv.waitAgent(c.project); const p = await proj(c.project); await shot(4); return p.brief.done && p.layout.state === "waiting"; }],
        ["Создать папку «Насосы»", async () => { await drv.openTree(); await ui.click('[data-act="new-folder"]'); await ui.fill('[data-field="name"]', "Насосы"); await ui.click('[data-act="create"]'); return (await state()).folders.some(f => f.name === "Насосы"); }],
        ["Удалить проект «Планка» и вернуть", async () => { await drv.openProject("plate"); await ui.click('[data-act^="delete:"]'); const gone = !(await proj("plate")); await ui.click('#toast [data-act="undo"]'); const back = !!(await proj("plate")); return gone && back; }],
      ],
    },
    // изделие из узлов и разговор: снимки — изделие, узел с вопросом, агент в узле, задача словами, всё изделие
    nodes: {
      async shots() { await shot(0); await ui.click('[data-tree="project:supports"]'); await shot(1); await ui.click('[data-tree="project:frame"]'); await drv.liveShot("frame", 2); },
      scenarios: [
        ["Открыть узел «Опоры насоса» в составе изделия", async () => { await ui.click('[data-tree="project:supports"]'); return (await cur()).project === "supports"; }],
        ["Ответить на вопрос агента в разговоре", async () => { await ui.click('[data-act^="answer:"]'); const s = await state(); return s.thread.some(m => m.question && m.question.answer != null); }],
        ["Выбрать вариант опор кнопкой в сообщении агента", async () => { await ui.click('[data-act="choose:B_wide"]'); return (await proj("supports")).design.chosen === "B_wide"; }],
        ["Поручить агенту комплект рамы одной кнопкой", async () => { await ui.click('[data-tree="project:frame"]'); await ui.click('[data-act="next"]'); await drv.waitAgent("frame"); return (await proj("frame")).kit.state === "ready"; }],
        ["Написать агенту задачу словами: компоновка кронштейна", async () => { await ui.click('[data-tree="project:pipe_bracket"]'); await ui.fill('[data-field="say"]', "Сделай компоновку кронштейна по наброску: вылет 500, 4 анкера М16"); await ui.click('[data-act="send"]'); await drv.waitAgent("pipe_bracket"); const s = await state(); await shot(3); return s.projects.find(x => x.id === "pipe_bracket").layout.state === "waiting" && s.thread.some(m => m.who === "you" && m.text.startsWith("Сделай компоновку кронштейна")); }],
        ["Согласовать компоновку кнопкой в сообщении агента", async () => { await ui.click('.msg [data-act="approve"]'); return (await proj("pipe_bracket")).layout.state === "approved"; }],
        ["Открыть изделие целиком: сводка по узлам", async () => { await ui.click('[data-tree="project:pump"]'); const c = await cur(); const strip = await page.locator(".nstrip").filter({ visible: true }).count(); return c.project === "pump" && strip > 0; }],
        ["Переключить разговор на всё изделие", async () => { await ui.click('[data-act="scope:all"]'); await shot(4); const n = await page.locator(".chat__list .msg").count(); return n >= 10; }],
        ["Добавить узел «Фундаментные болты», удалить и вернуть", async () => { await ui.click('[data-act="new-node"]'); await ui.fill('[data-field="title"]', "Фундаментные болты"); await ui.click('[data-act="create"]'); const s = await state(); const p = s.projects.find(x => x.title === "Фундаментные болты"); if (!p || p.parent !== "pump") return false; await ui.click('[data-act^="delete:"], #menu [data-act]'); const gone = !(await proj(p.id)); await ui.click('#toast [data-act="undo"]'); return gone && !!(await proj(p.id)); }],
        ["Перейти к другому изделию через «Проекты»", async () => { await ui.click('[data-act="drawer"]'); await ui.click('[data-tree="project:bolt"]'); return (await cur()).project === "bolt"; }],
      ],
    },
  };
  const flow = FLOWS[v.scenarios || "default"];
  await flow.shots();
  await page.reload();
  await page.waitForSelector(".tree, .gallery");
  await page.evaluate(() => window.proto.fast());
  count = 0;
  const r = { file: v.file, name, scenarios: [], errors, controls: ctl, actions: 0, pass: 0, flow: v.scenarios || "default" };
  for (const [title, fn] of flow.scenarios) {
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
  log(`${name}: ${r.pass}/${flow.scenarios.length}, действий ${count}, ошибок JS ${errors.length}`);
  await page.close();
}
await browser.close();
fs.writeFileSync(path.join(DIR, "results.json"), JSON.stringify(results, null, 1));
