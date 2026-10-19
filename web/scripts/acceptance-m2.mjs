// Приёмка M2: конструктор без терминала проходит сценарий из docs/architecture/05-m2-plan.md.
// node scripts/acceptance-m2.mjs <base> <outdir> [--agent]   (--agent: ставит задачу агенту и ждёт её конца)
import { chromium } from "playwright";
const [base, out] = [process.argv[2], process.argv[3]];
const withAgent = process.argv.includes("--agent");
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
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

await step("1 Проекты: список с числами", async () => {
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Проекты" }).waitFor();
  const cards = await page.locator(".card").count();
  await shot("01-projects");
  return `проектов ${cards}`;
});
await step("2 Вариант: 3D, замечание → подсветка, разрез", async () => {
  await page.goto(base + "/p/bracket/A_fork", { waitUntil: "networkidle" });
  await page.locator("canvas").waitFor();
  await page.waitForTimeout(2500);
  let refs = page.locator(".findings .ref");
  if (!(await refs.count())) {
    const show = page.getByRole("button", { name: "Показать" });
    if (await show.count()) await show.click();
    refs = page.locator(".findings .ref");
  }
  if (await refs.count()) await refs.first().click();
  await page.getByLabel("Разрез", { exact: true }).check();
  await page.waitForTimeout(800);
  await shot("02-variant");
  const sel = await page.getByText(/Снять выделение/).count();
  return sel ? "подсветка по замечанию работает" : "замечаний для подсветки нет";
});
await step("3 Пометка на модели → замечание агенту", async () => {
  await page.getByLabel("Разрез", { exact: true }).uncheck();
  await page.getByRole("button", { name: "Изометрия" }).click();
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: "Пометить на модели" }).click();
  const c = await page.locator("canvas").boundingBox();
  await page.mouse.click(c.x + c.width * 0.5, c.y + c.height * 0.5);
  await page.locator(".review__form").waitFor({ timeout: 5000 });
  await page.getByLabel("Текст замечания").fill("приёмка M2: проверь доступ ключа к анкерам");
  await page.getByRole("button", { name: "Отправить агенту" }).click();
  await page.locator(".review__item--open").last().waitFor({ timeout: 30000 });
  await shot("03-review");
  return await page.locator(".review__item--open").last().textContent();
});
if (withAgent) {
  await step("4 Задача агенту: запуск, ход, завершение", async () => {
    await page.goto(base + "/p/bracket/agent?variant=A_fork", { waitUntil: "networkidle" });
    await page.getByLabel("Текст задачи").fill("Ответь на открытые замечания конструктора через review_resolve, опираясь на измерения; файлы модели не меняй. В конце — короткий отчёт.");
    await page.getByRole("button", { name: "Запустить" }).click();
    await page.getByText(/вызов/).first().waitFor({ timeout: 120000 });
    await shot("04-agent-running");
    await page.getByText("Отчёт агента").waitFor({ timeout: 900000 });
    await page.waitForTimeout(1500);
    await shot("04-agent-done");
    return "задача выполнена";
  });
}
await step("5 Лента: разница, просмотрено, откат с предпросмотром", async () => {
  await page.goto(base + "/p/bracket/commits?variant=A_fork", { waitUntil: "networkidle" });
  await page.locator(".commit").first().waitFor();
  await page.getByRole("button", { name: "Разница" }).first().click();
  await page.getByText(/Разница по варианту|сравнивать не с чем|Различий/).first().waitFor({ timeout: 300000 });
  const agentCheck = page.getByRole("checkbox", { name: "Просмотрено" }).first();
  if (await agentCheck.count()) await agentCheck.check();
  await shot("05-feed");
  await page.getByRole("button", { name: "Откатить" }).first().click();
  const dlg = page.getByRole("dialog");
  await dlg.waitFor();
  await shot("05-feed-revert-dialog");
  await dlg.getByRole("button", { name: "Отмена" }).click();
  return "диалог отката показан и закрыт без последствий";
});
await step("6 Параметры: черновик → сохранить", async () => {
  await page.goto(base + "/p/bracket/A_fork/params", { waitUntil: "networkidle" });
  const gap = page.getByLabel(/^gap/);
  const cur = Number(await gap.inputValue());
  await gap.fill(String(cur + 5));
  await page.getByRole("button", { name: "Собрать черновик" }).click();
  await page.getByText("Черновик собран", { exact: false }).waitFor({ timeout: 400000 });
  await page.locator("canvas").waitFor({ timeout: 60000 });
  await page.waitForTimeout(2000);
  await shot("06-params-draft");
  await page.getByRole("button", { name: "Сохранить" }).click();
  await page.waitForURL("**/p/bracket/A_fork", { timeout: 60000 });
  return `gap ${cur} → ${cur + 5} сохранён коммитом`;
});
await step("7 Сравнение вариантов", async () => {
  await page.goto(base + "/p/bracket/compare", { waitUntil: "networkidle" });
  await page.getByText("Метрика").waitFor({ timeout: 400000 });
  await page.waitForTimeout(2500);
  await shot("07-compare");
  return `лучших ячеек ${await page.locator("td.best").count()}`;
});
await step("8 Выдача комплекта", async () => {
  await page.goto(base + "/p/bracket/A_fork", { waitUntil: "networkidle" });
  const closed = await page.getByText(/Выдача закрыта/).count();
  if (closed) return "выдача закрыта: есть ошибки";
  await page.getByText("Выдача", { exact: true }).click();
  const links = await page.locator(".export a").count();
  await shot("08-export");
  return `ссылок в комплекте ${links}`;
});
await step("9 Подключение агента (токены)", async () => {
  await page.goto(base + "/tokens", { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Подключение агента" }).waitFor();
  await shot("09-tokens");
  return (await page.locator(".tokens__item").count()) + " клиентов";
});
console.log(JSON.stringify({ log, errors }, null, 1));
await browser.close();
