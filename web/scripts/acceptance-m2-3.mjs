// Приёмка M2.3: ввод компоновки от конструктора — вложения к задаче агенту и инструмент attachment, правка
// компоновки на эскизе (ручки, числа, размер числом), росчерки пометок и их вид у агента
// (docs/architecture/08-m2-3-layout-input-plan.md). node scripts/acceptance-m2-3.mjs <base> <outdir> <sketch.png>
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
const [base, out, sketch] = [process.argv[2], process.argv[3], process.argv[4]];
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
const rpc = async (name, args) => {
  const r = await fetch(base + "/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message);
  return j.result;
};
const mcp = async (name, args) => {
  const res = await rpc(name, args);
  const txt = res.content.find((c) => c.type === "text")?.text ?? "{}";
  try {
    return JSON.parse(txt);
  } catch {
    return { summary: txt, content: res.content };
  }
};
const apiJson = async (path, init) => {
  const r = await fetch(base + path, init);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error ?? r.statusText);
  return j;
};

await step("0. сервер отвечает: /health, проект bracket на месте", async () => {
  const h = await (await fetch(base + "/health")).json();
  if (!h.projects.includes("bracket")) throw new Error("нет bracket");
  return `проектов ${h.projects.length}, граф ${h.graph}`;
});

let attPath = null;
await step("1. экран «Агент»: набросок загружается файлом, миниатюра, отмечен к задаче", async () => {
  await page.goto(base + "/p/bracket/agent");
  await page.waitForSelector('button:has-text("Добавить файл")');
  await page.setInputFiles('input[type="file"]', sketch);
  await page.waitForSelector(".attachments__item img");
  await page.waitForFunction(() => document.querySelector(".attachments__item input[type=checkbox]")?.checked);
  const name = await page.$eval(".attachments__name", (e) => e.textContent);
  const loaded = await page.$eval(".attachments__item img", (e) => e.naturalWidth > 0);
  if (!loaded) throw new Error("миниатюра не загрузилась");
  const items = await apiJson("/api/projects/bracket/attachments");
  attPath = items.items[0].path;
  if (items.items[0].author !== "constructor") throw new Error("автор: " + items.items[0].author);
  await shot("15-agent-attachment");
  return `${name}; коммит конструктора, ${items.items[0].width}×${items.items[0].height}`;
});

await step("2. агент: attachment отдаёт изображение, project_read перечисляет вложения", async () => {
  const res = await rpc("attachment", { project: "bracket", path: attPath });
  const kinds = res.content.map((c) => c.type);
  if (!kinds.includes("image")) throw new Error("нет image в ответе: " + kinds.join(","));
  const pr = await mcp("project_read", { project: "bracket" });
  if (!pr.attachments?.includes(attPath)) throw new Error("project_read без вложения");
  return `${kinds.join("+")}; ${res.content[0].text.split("\n")[0]}`;
});

await step("3. задача с вложением ставится из рабочего места и передаёт путь вложения", async () => {
  await page.fill('textarea[aria-label="Текст задачи"]', "По наброску опиши скелет и обстановку (приёмка M2.3).");
  await page.click('button:has-text("Запустить")');
  await page.waitForSelector(".tasks .tree__item");
  await page.waitForFunction(() => document.querySelector(".tasks")?.textContent?.includes("вложений: 1"));
  const tasks = await apiJson("/api/projects/bracket/tasks");
  const t = tasks.tasks[0];
  if (!t.attachments?.includes(attPath)) throw new Error("в задаче нет вложения");
  await page.waitForSelector(".chips a");
  await shot("15-agent-task-with-attachment");
  // агент в приёмке не запущен — снимаем задачу, чтобы проект вернулся конструктору
  await apiJson(`/api/tasks/${t.id}/stop`, { method: "POST" });
  return `задача ${t.id}, вложения: ${t.attachments.join(", ")} (остановлена)`;
});

await step("4. компоновка: «Править» — ручки, перетаскивание, число, «Применить» = коммит конструктора", async () => {
  await page.goto(base + "/p/bracket/A_fork?mode=layout&ref=surrounding%3Awall_body");
  await page.waitForSelector(".sketch svg", { timeout: 60000 });
  await page.click('button:has-text("Править")');
  await page.waitForSelector(".sketch .handles [data-handle]");
  const handles = await page.$$eval(".sketch .handles [data-handle]", (els) =>
    els.map((e) => e.getAttribute("data-handle")),
  );
  const t0 = Number(await page.$eval('input[aria-label="толщина"]', (e) => e.value));
  const t = await page.$('.sketch .handles [data-handle="t"]');
  const b = await t.boundingBox();
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width / 2 + 30, b.y + b.height / 2, { steps: 6 });
  await page.mouse.up();
  await page.waitForSelector(".sketch .handles .ghost");
  const t1 = Number(await page.$eval('input[aria-label="толщина"]', (e) => e.value));
  if (!(t1 > t0)) throw new Error(`толщина не выросла: ${t0} → ${t1}`);
  await shot("16-layout-edit-draft");
  const ext0 = Number(await page.$eval('input[aria-label="протяжённость (полуразмер)"]', (e) => e.value));
  await page.fill('input[aria-label="протяжённость (полуразмер)"]', String(ext0 + 10));
  await page.fill('input[aria-label="Сообщение коммита (необязательно)"]', "приёмка M2.3: стена с эскиза");
  await page.click('.edit button:has-text("Применить")');
  await page.waitForSelector(".edit .ok", { timeout: 60000 });
  await page.waitForFunction((v) => Number(document.querySelector('input[aria-label="толщина"]')?.value) === v, t1, {
    timeout: 90000,
  });
  const commits = await apiJson("/api/projects/bracket/commits?limit=1");
  const c = commits.commits[0];
  if (c.author !== "constructor" || c.message !== "приёмка M2.3: стена с эскиза")
    throw new Error(`${c.author}: ${c.message}`);
  const lay = await apiJson("/api/projects/bracket/layout?variant=A_fork");
  if (lay.approval.state !== "changed") throw new Error("согласование: " + lay.approval.state);
  await shot("16-layout-edit-applied");
  return `ручки ${handles.join(",")}; толщина ${t0} → ${t1}, протяжённость ${ext0} → ${ext0 + 10}; ${c.commit} ${c.author}`;
});

await step("5. размер числом: клик по размеру, новое значение сдвигает базу по оси размера", async () => {
  const dimText = await page.$('.sketch .dims text[data-ref="dim:wall-axle_axis"]');
  const db = await dimText.boundingBox();
  await page.mouse.click(db.x + db.width / 2, db.y + db.height / 2);
  await page.waitForSelector("#dim-value");
  const old = Number(await page.inputValue("#dim-value"));
  await page.fill("#dim-value", String(old + 15));
  await page.click('.edit button:has-text("Применить")');
  await page.waitForFunction(() => !document.querySelector("#dim-value"), null, { timeout: 60000 });
  await page.waitForFunction(
    (v) => document.querySelector(".sketch__foot")?.textContent?.includes(v),
    String(old + 15),
    { timeout: 90000 },
  );
  const commits = await apiJson("/api/projects/bracket/commits?limit=1");
  await shot("16-layout-edit-dim");
  return `${old} → ${old + 15}; ${commits.commits[0].message}`;
});

await step("6. росчерк: «Обвести на эскизе» → форма → review.yaml; агент видит словами и в PNG", async () => {
  await page.click('button:has-text("Править")'); // выйти из правки
  await page.click('button:has-text("Обвести на эскизе")');
  await page.waitForSelector(".sketch--drawing");
  const box = await (await page.$(".sketch")).boundingBox();
  const cx = box.x + box.width * 0.42;
  const cy = box.y + box.height * 0.5;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  for (const [dx, dy] of [
    [40, -30],
    [80, 0],
    [60, 40],
    [10, 50],
    [-20, 10],
    [0, -30],
  ])
    await page.mouse.move(cx + dx, cy + dy, { steps: 4 });
  await page.mouse.up();
  await page.waitForSelector(".review__form");
  const note = await page.textContent(".review__form .small.muted");
  await page.fill('textarea[aria-label="Текст замечания"]', "приёмка M2.3: здесь оставить место под ключ");
  await page.click('button:has-text("Отправить агенту")');
  await page.waitForFunction(
    () => document.querySelectorAll(".sketch .strokes polyline[data-stroke]").length > 0,
    null,
    { timeout: 60000 },
  );
  await shot("17-stroke-saved");
  const rl = await mcp("review_list", { project: "bracket" });
  const item = rl.items.find((i) => i.text.startsWith("приёмка M2.3"));
  if (!item?.stroke || !rl.summary.includes("росчерк на виде main")) throw new Error("review_list без росчерка");
  const png = await rpc("render", { project: "bracket", variant: "A_fork", view: "main", layout: true });
  if (!png.content.some((c) => c.type === "image")) throw new Error("render(layout) без картинки");
  const lay = await apiJson("/api/projects/bracket/layout?variant=A_fork");
  if (!(lay.views.main.marks >= 1)) throw new Error("на эскизе нет пометок");
  const svg = await (await fetch(base + lay.views.main.svg_url)).text();
  if (!svg.includes(`data-mark="${item.id}"`)) throw new Error("в SVG агента нет росчерка " + item.id);
  await mcp("review_resolve", { project: "bracket", id: item.id, answer: "приёмка: учёл" });
  return `${note}; ${item.id}: точек ${item.stroke.points.length}; пометок на виде ${lay.views.main.marks}`;
});

await browser.close();
log.push({ step: "ошибки страницы", ok: errors.length === 0, ms: 0, info: errors.join("; ") });
writeFileSync(`${out}/acceptance.json`, JSON.stringify(log, null, 2));
for (const l of log) console.log(`${l.ok ? "OK " : "FAIL"} ${l.step} (${l.ms} мс) ${l.info}`);
process.exit(log.every((l) => l.ok) ? 0 : 1);
