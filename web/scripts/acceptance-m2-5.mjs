// Приёмка M2.5 (D32): рабочее место с составом изделия, этапами, следующим шагом и разговором — на локальном
// сервере (restart-dev.sh, :8499, без входа, без агента: задачи встают в очередь и останавливаются руками).
// node web/scripts/acceptance-m2-5.mjs [shots-dir]
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.SKELCAD_URL || "http://127.0.0.1:8499";
const SHOTS = process.argv[2] || "";
const log = (...a) => fs.writeSync(1, a.join(" ") + "\n");
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(30000); // первые запросы после старта сервера (копия шаблона, индекс связей) бывают долгими
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message.slice(0, 160)));
// ответы 404/400 на запросы, которые экран обрабатывает сам (отчёт несобранного варианта, компоновка без скелета), не ошибки
page.on("console", (m) => { if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) errors.push("console: " + m.text().slice(0, 160)); });
const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `22-${name}.png`) }); };
const api = async (method, url, body) => {
  const r = await page.request.fetch(BASE + url, { method, data: body, headers: { "Content-Type": "application/json" } });
  return { status: r.status(), json: r.headers()["content-type"]?.includes("json") ? await r.json() : null, headers: r.headers() };
};
const results = [];
const run = async (title, fn) => {
  try {
    const ok = await fn();
    results.push([title, !!ok]);
    log(`  ${ok ? "ok  " : "FAIL"} ${title}`);
  } catch (e) {
    results.push([title, false]);
    log(`  FAIL ${title} — ${e.message.split("\n")[0].slice(0, 160)}`);
  }
};
// прогон повторяемый: свои проекты создаёт и убирает сам, выбор варианта у примера снимает
const cleanup = async () => {
  for (const name of ["rama", "nasosnyy_agregat", "priemka_planka"]) {
    const a = await api("GET", `/api/projects/${name}/tasks`);
    if (a.json?.active) await api("POST", `/api/tasks/${a.json.active.id}/stop`);
    await api("DELETE", `/api/projects/${name}`).catch(() => null);
  }
  const f = await api("GET", "/api/folders");
  for (const fo of f.json?.folders ?? []) if (fo.title === "Насосы") await api("DELETE", `/api/folders/${fo.id}`);
  const b = await api("GET", "/api/projects/bracket/tasks");
  if (b.json?.active) await api("POST", `/api/tasks/${b.json.active.id}/stop`);
  await api("POST", "/api/projects/bracket/choose", { variant: "" });
};
await cleanup();
await api("POST", "/api/projects", { name: "priemka_planka", title: "Планка (приёмка)", template: "plate" });

await run("Стартовый экран: папки, проекты картинками, «что дальше» у каждого", async () => {
  await page.goto(BASE + "/");
  await page.waitForSelector(".gallery .gcard");
  const cards = await page.locator(".gallery .gcard").count();
  const pills = await page.locator(".gallery .pill").count();
  await shot("start");
  return cards >= 3 && pills === cards && (await page.locator('[data-tree="folder:all"]').count()) === 1;
});
await run("Новая папка «Насосы»", async () => {
  await page.click('[data-act="new-folder"]');
  await page.fill('[data-field="name"]', "Насосы");
  await page.click('[data-act="create"]');
  await page.waitForSelector('[data-tree="folder:nasosy"]');
  return true;
});
await run("Новый проект в папке — открывается рабочее место на этапе «Задание»", async () => {
  await page.click('[data-tree="folder:nasosy"]');
  await page.click('[data-act="new-project"]');
  await page.fill('[data-field="title"]', "Насосный агрегат");
  await page.click('[data-act="create"]');
  await page.waitForURL(/\/p\/nasosnyy_agregat/);
  await page.waitForSelector('[data-node="nasosnyy_agregat"]');
  const cur = await page.locator(".steps__item.cur").innerText();
  const next = await page.locator("[data-next]").innerText();
  return cur.includes("Задание") && next.includes("Опишите, что нужно");
});
await run("Задание — первое сообщение агенту: задача в очереди, проект у агента, остановить", async () => {
  await page.fill('[data-field="say"]', "Насосный агрегат К 100-65-200 на раме, рама на полу на анкерах, всасывание DN80 слева");
  await page.click('[data-act="send"]');
  await page.waitForSelector(".next--agent", { timeout: 20000 });
  const running = (await page.locator("[data-next]").innerText()).includes("Агент строит компоновку");
  await page.waitForSelector(".msg--you");
  await shot("brief-sent");
  await page.click('[data-next] button:has-text("Остановить")');
  await page.waitForFunction(() => document.querySelector("[data-next]")?.textContent?.includes("Задание принято"), null, { timeout: 20000 });
  const btn = await page.locator('[data-act="run:layout"]').count();
  return running && btn === 1;
});
await run("«+ Узел» — узел внутри изделия, состав и крошки", async () => {
  await page.click('.ntree__tools button:has-text("Узел")');
  await page.fill('[data-field="title"]', "Рама");
  await page.click('[data-act="create"]');
  await page.waitForURL(/\/p\/rama/);
  await page.waitForSelector('[data-node="rama"]');
  const rows = await page.locator(".ntree .nrow").count();
  const crumbs = await page.locator(".crumbs").innerText();
  await page.click('[data-node="nasosnyy_agregat"]');
  await page.waitForSelector('.steps__item:has-text("Узлы")');
  await shot("product-nodes");
  return rows === 2 && crumbs.includes("Насосный агрегат") && crumbs.includes("Рама");
});
await run("«Согласовать компоновку» — агент продолжает сам (задача «детали» в очереди)", async () => {
  await page.goto(BASE + "/p/priemka_planka");
  await page.waitForSelector('[data-act="approve"]');
  await page.click('[data-act="approve"]');
  await page.waitForFunction(() => document.querySelector("[data-next]")?.textContent?.includes("Агент делает детали"), null, { timeout: 20000 });
  await page.waitForSelector(".msg--sys:has-text('Агент продолжает сам')");
  await shot("approved-auto");
  await page.click('[data-next] button:has-text("Остановить")');
  await page.waitForFunction(() => document.querySelector("[data-next]")?.textContent?.includes("Компоновка согласована"), null, { timeout: 20000 });
  return (await page.locator('[data-act="run:design"]').count()) === 1;
});
await run("Конструкция: 3D, полоса вариантов, «Выбрать» — отметка выбранного", async () => {
  await page.goto(BASE + "/p/bracket/s/design");
  await page.waitForSelector(".strip__it");
  const n = await page.locator(".strip__it").count();
  await page.click('[data-act^="choose:"]');
  await page.waitForSelector('.strip__it:has-text("выбран")');
  await page.waitForSelector("canvas", { timeout: 20000 });
  await shot("design");
  return n === 3;
});
await run("Сравнение и параметры встроены вкладками", async () => {
  await page.click('.tabs button:has-text("Сравнение")');
  await page.waitForSelector("table");
  await page.click('.tabs button:has-text("Параметры")');
  await page.waitForSelector("form.params__form, .params__form");
  return true;
});
await run("Комплект: файлы и zip", async () => {
  await page.goto(BASE + "/p/bracket/s/kit");
  await page.waitForSelector(".files .file");
  const r = await page.request.get(BASE + "/api/projects/bracket/kit.zip");
  await shot("kit");
  return r.status() === 200 && (r.headers()["content-type"] || "").includes("zip");
});
await run("История коммитов — вкладка справа", async () => {
  await page.click('.wb__sidetabs button:has-text("История")');
  await page.waitForSelector(".commit");
  return (await page.locator(".commit").count()) > 0;
});
await run("Удалить узел — в корзину, «Вернуть» возвращает", async () => {
  await page.goto(BASE + "/p/rama");
  await page.waitForSelector('[data-act="delete:rama"]');
  await page.click('[data-act="delete:rama"]');
  await page.waitForURL(/\/p\/nasosnyy_agregat/);
  await page.waitForSelector('[data-act="undo"]');
  await page.click('[data-act="undo"]');
  await page.waitForURL(/\/p\/rama/);
  return (await page.locator('[data-node="rama"]').count()) === 1;
});
await run("Старые адреса ведут в рабочее место", async () => {
  await page.goto(BASE + "/p/bracket/commits");
  await page.waitForURL(/\/p\/bracket\?r=history/);
  await page.goto(BASE + "/p/bracket/A_fork?mode=layout");
  await page.waitForURL(/\/p\/bracket\/s\/layout\?v=A_fork/);
  return true;
});
await cleanup();
await browser.close();
const pass = results.filter(([, ok]) => ok).length;
log(`M2.5: ${pass}/${results.length}, ошибок JS ${errors.length}${errors.length ? "\n" + errors.slice(0, 5).join("\n") : ""}`);
process.exit(pass === results.length && errors.length === 0 ? 0 : 1);
