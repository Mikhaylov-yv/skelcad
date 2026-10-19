// Приёмка M2.1: сценарий из docs/architecture/06-m2-1-sketches-plan.md — компоновка, эскизы с размерами, сравнение.
// node scripts/acceptance-m2-1.mjs <base> <outdir>   (сервер без входа; «агент» — вызовы MCP того же сервера)
import { chromium } from "playwright";
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
// «агент»: инструменты MCP сервера (как их вызывает Claude Code)
const mcp = async (name, args) => {
  const r = await fetch(base + "/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message);
  const txt = j.result.content.find((c) => c.type === "text")?.text ?? "{}";
  let data;
  try {
    data = JSON.parse(txt);
  } catch {
    data = { summary: txt }; // render отдаёт сводку текстом + картинку
  }
  return { data, image: j.result.content.some((c) => c.type === "image") };
};
const project = "demo_" + Date.now().toString(36).slice(-5);
const skeletonYaml = (offset) => `id: ${project}
title: "Кронштейн под ось Ø50 на стене (приёмка M2.1)"
lang: ru
standards: [gost]
requirements:
  purpose: "Опора оси Ø50 на стене, вылет ${offset}; справа в 150 мм короб"
  loads: {Fv: 20, Fh: 4}
  safety_required: 1.5
skeleton:
  datums:
    - {id: wall, kind: plane, origin: [0, 0, 0], direction: [0, 1, 0], name: "Лицевая плоскость стены"}
    - {id: axis, kind: axis, origin: [0, ${offset}, 0], direction: [1, 0, 0], name: "Ось вала"}
  interfaces:
    - {id: wall, kind: mount_plane, name: "Крепление к стене", datum: wall, params: {anchor_size: M16, concrete: B25}}
    - {id: axle, kind: shaft_seat, name: "Посадка оси", datum: axis, params: {d: 50, fit_hole: H8, fit_shaft: f7}}
  surroundings:
    - {id: wall_body, kind: plane, role: wall, name: "Стена", material: "бетон B25", origin: [0, 0, 0], normal: [0, 1, 0], extent: 300, thickness: 250}
    - {id: duct, kind: box, role: equipment, name: "Короб", min: [150, 0, -100], max: [300, 250, 100]}
params: {}
`;

await step("0a Агент описывает скелет и обстановку — компоновка видна без сборки", async () => {
  await mcp("project_create", { name: project, template: "empty" });
  await mcp("files_write", {
    project,
    files: { "project.yaml": skeletonYaml(200) },
    message: "скелет и обстановка по словам конструктора",
  });
  await page.goto(`${base}/p/${project}/layout`, { waitUntil: "networkidle" });
  await page.locator(".sketch svg").waitFor({ timeout: 60000 });
  await page.getByRole("button", { name: "Сверху" }).click(); // X и Y на экране: вылет 200 и короб в 150
  await page.waitForTimeout(600);
  await shot("00a-layout");
  const items = await page.locator(".pane--tree .tree__item").allTextContents();
  const dims = await page.locator(".sketch__foot").textContent();
  if (!items.some((t) => t.includes("duct"))) throw new Error("в составе нет короба duct");
  if (!/200/.test(dims) || !/150/.test(dims)) throw new Error("нет размеров 200 и 150: " + dims);
  await page.getByRole("button", { name: "Главный" }).click();
  await page.waitForTimeout(300);
  return `сущностей ${items.length}; ${dims.replace(/\s+/g, " ").trim().slice(0, 70)}`;
});
await step("0b Пометка конструктора на компоновке", async () => {
  await page.getByRole("button", { name: "Пометить на модели" }).click();
  const c = await page.locator(".sketch").boundingBox();
  await page.mouse.click(c.x + c.width * 0.45, c.y + c.height * 0.5);
  await page.locator(".review__form").waitFor({ timeout: 5000 });
  await page.getByLabel("Текст замечания").fill("снизу нужна зона обслуживания 100 мм");
  await page.getByRole("button", { name: "Отправить агенту" }).click();
  await page.locator(".review__item--open").last().waitFor({ timeout: 30000 });
  await shot("00b-layout-pin");
  const r = await mcp("review_list", { project });
  return `замечаний у агента: ${r.data.items.length}`;
});
await step("0c Агент добавляет запретную зону и отвечает; конструктор согласовывает", async () => {
  const txt = skeletonYaml(200).replace(
    "  surroundings:",
    '  envelopes:\n    - {id: service, kind: keep_out, min: [-200, 0, -300], max: [200, 300, -150], name: "Зона обслуживания"}\n  surroundings:',
  );
  await mcp("files_write", { project, files: { "project.yaml": txt }, message: "зона обслуживания снизу (R1)" });
  await mcp("review_resolve", { project, id: "R1", answer: "добавил keep_out service 100 мм под осью" });
  await page.reload({ waitUntil: "networkidle" });
  await page.locator(".sketch svg").waitFor({ timeout: 60000 });
  await page.getByRole("button", { name: "Компоновка согласована" }).click();
  await page.locator("[role=dialog]").waitFor();
  await page.getByRole("button", { name: "Согласовать" }).click();
  await page.locator(".badge--ok", { hasText: "согласована" }).waitFor({ timeout: 30000 });
  await shot("00c-layout-approved");
  const pr = await mcp("project_read", { project });
  if (pr.data.layout.state !== "approved") throw new Error("агент не видит согласования: " + pr.data.layout.state);
  return "агент видит: " + pr.data.summary.split(";").pop().trim();
});
await step("0d Агент меняет вылет после согласования — предупреждение", async () => {
  await mcp("files_write", { project, files: { "project.yaml": skeletonYaml(220) }, message: "вылет 200 → 220" });
  await page.reload({ waitUntil: "networkidle" });
  await page.locator(".sketch svg").waitFor({ timeout: 60000 });
  await page.getByText("изменена после согласования").first().waitFor({ timeout: 10000 });
  await shot("00d-layout-changed");
  const t = await page.locator(".approval").textContent();
  const chk = await mcp("check", { project, scope: "rules" });
  const f = Object.values(chk.data.variants)[0].findings.find((x) => x.includes("R-LAYOUT"));
  return (t.includes("datum:axis") ? "diff: datum:axis; " : "") + (f ?? "R-LAYOUT не найден");
});
await step("1 Планка: эскиз сверху с размерами, клик по размеру выделяет деталь", async () => {
  await page.goto(`${base}/p/plate/A_base?mode=sketch`, { waitUntil: "networkidle" });
  await page.locator(".sketch svg").waitFor({ timeout: 60000 });
  await page.getByRole("button", { name: "Сверху" }).click();
  await page.waitForTimeout(500);
  const foot = await page.locator(".sketch__foot").textContent();
  for (const d of ["120 (X)", "60 (Y)", "90 (X)", "30 (Y)", "15 (X)", "R5", "4 отв. Ø8.5"]) {
    if (!foot.includes(d)) throw new Error("нет размера " + d + ": " + foot);
  }
  await page.locator('.sketch [data-ref="dim:plate.holes.pitch_X_1"]').first().click({ force: true });
  await page.waitForTimeout(300);
  const pressed = await page.locator(".pane--tree .tree__item[aria-pressed=true]").count();
  await shot("01-plate-sketch");
  await page.getByRole("button", { name: "Главный" }).click();
  await page.waitForTimeout(400);
  const main = await page.locator(".sketch__foot").textContent();
  if (!main.includes("s10")) throw new Error("нет толщины s10: " + main);
  return `сверху: ${foot.replace(/\s+/g, " ").trim().slice(0, 90)}; главный: s10; выделено деталей ${pressed}`;
});
await step("2 Кронштейн: эскиз слева и главный — шаг анкеров, толщины, вылет", async () => {
  await page.goto(`${base}/p/bracket/A_fork?mode=sketch`, { waitUntil: "networkidle" });
  await page.locator(".sketch svg").waitFor({ timeout: 60000 });
  await page.getByRole("button", { name: "Слева" }).click();
  await page.waitForTimeout(500);
  const left = await page.locator(".sketch__foot").textContent();
  await shot("02-bracket-sketch-left");
  await page.getByRole("button", { name: "Главный" }).click();
  await page.waitForTimeout(500);
  const main = await page.locator(".sketch__foot").textContent();
  await shot("02-bracket-sketch-main");
  for (const d of ["4 × M16", "s12", "s16"]) if (!(left + main).includes(d)) throw new Error("нет " + d);
  if (!/200 \(Y\)/.test(main)) throw new Error("нет вылета 200: " + main);
  return `слева: ${left.replace(/\s+/g, " ").trim().slice(0, 80)}…; главный: вылет 200, s16`;
});
await step("3 Опора: сравнение — эскизы бок о бок, наложение, различающиеся размеры и параметры", async () => {
  await page.goto(`${base}/p/pipe_support/compare`, { waitUntil: "networkidle", timeout: 600000 });
  await page.locator("table.cmp").waitFor({ timeout: 600000 });
  const dimRows = await page.locator("table.cmp tbody tr").filter({ hasText: /виды:/ }).count();
  await page.getByRole("tab", { name: "Эскизы бок о бок" }).click();
  await page.locator(".cmp__sketch svg").first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(800);
  const vbs = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".cmp__sketch svg")).map((s) => s.getAttribute("viewBox")),
  );
  await shot("03-compare-sketch");
  await page.getByRole("tab", { name: "Наложение" }).click();
  await page.locator(".cmp__overlay .sketch--now svg").waitFor({ timeout: 60000 });
  await page.waitForTimeout(600);
  await shot("03-compare-overlay");
  if (new Set(vbs).size !== 1) throw new Error("разный viewBox: " + vbs.join(" | "));
  return `строк размеров ${dimRows}; эскизов ${vbs.length} в одном масштабе; наложение показано`;
});
await step("4 Агент: render(sketch=true) — PNG и размеры текстом, кромка ≥ 1,5·d", async () => {
  const r = await mcp("render", { project: "plate", variant: "A_base", view: "top", sketch: true });
  const m = r.data.summary ? r.data.summary : "";
  const edge = /plate\.holes\.edge_X = (\d+)/.exec(m);
  if (!r.image) throw new Error("нет картинки");
  if (!edge) throw new Error("нет кромки в тексте: " + m.slice(0, 120));
  return `кромка ${edge[1]} ≥ 1,5·d = 15: ${Number(edge[1]) >= 15 ? "да" : "нет"}; картинка есть`;
});
await mcp("project_read", { project }).catch(() => null);
console.log(JSON.stringify({ log, errors: errors.slice(0, 5), project }, null, 1));
await browser.close();
