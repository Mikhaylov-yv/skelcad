// Общая модель макетов рабочего места SkelCAD: папки и проекты, четыре этапа изделия, «следующий шаг»,
// имитация работы агента фразами и картинками, отмена действий. Каждый макет (vNN-*.html) только рисует.
"use strict";
const IMG = "img/";
const STAGES = [
  { id: "brief", name: "Задание", hint: "Что нужно: назначение, нагрузки, к чему крепится; набросок или фото." },
  { id: "layout", name: "Компоновка", hint: "Скелет и обстановка: базы, стена или пол, зоны, нагрузки. Нужно ваше согласование." },
  { id: "design", name: "Конструкция", hint: "Детали и варианты, проверки: масса, запас K, замечания." },
  { id: "kit", name: "Комплект", hint: "STEP, эскизы с размерами, спецификация, отчёт." },
];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (x, d = 2) => (x == null ? "—" : Number(x).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: d }));
const plural = (n, a, b, c) => { const m = n % 10, h = n % 100; return n + " " + (h > 10 && h < 20 ? c : m === 1 ? a : m > 1 && m < 5 ? b : c); };
let clock = 0;
const nowStr = () => { const t = new Date(Date.now() + clock * 60000); return t.toTimeString().slice(0, 5); };

// --- Данные: то, что сейчас лежит на сервере, плюс примеры -------------------------------------
function initialState() {
  return {
    folders: [
      { id: "krepezh", name: "Крепёж" },
      { id: "opory", name: "Кронштейны и опоры" },
      { id: "primery", name: "Примеры" },
    ],
    projects: [
      {
        id: "bolt", code: "bolt_obychnyy_m16", title: "Болт обычный М16", folder: "krepezh", updated: "сегодня 15:52",
        brief: { done: true, text: "Сделай обычный болт М16, он должен стягивать изделия. Расстояние между плоскостями 100 мм.", sketch: null, by: "вы", when: "15:41" },
        layout: { state: "approved", img: "bolt-layout.svg", by: "вы", when: "15:52", bases: 4, ifaces: 1, bodies: 1,
          assumptions: ["100 мм — суммарная толщина пакета; распределение по изделиям не задано", "«обычный болт М16» — ГОСТ 7798-70, гайка ГОСТ 5915-70, шайбы ГОСТ 11371-78", "длина болта 130 из ряда ГОСТ: пакет 100 + 2 шайбы + гайка + выступ резьбы", "отверстие Ø18 (зазор 2 мм)", "усилие затяжки не задано; класс прочности уточнить", "сечение изделий 60×60 — условно, для эскиза"] },
        design: { state: "none", variants: [], chosen: null },
        kit: { state: "none", files: [] },
        history: [
          { when: "15:41", who: "вы", what: "Проект «Болт обычный М16»" },
          { when: "15:44", who: "агент", what: "скелет: ось болта М16, две опорные плоскости пакета на 100 мм, интерфейс стяжки, пакет как обстановка" },
          { when: "15:45", who: "агент", what: "параметры интерфейса стяжки — плоские значения, как требует схема" },
          { when: "15:52", who: "вы", what: "Компоновка согласована" },
        ],
      },
      {
        id: "sbolt", code: "specialnyy_bolt", title: "Специальный болт", folder: "krepezh", updated: "сегодня 14:59",
        brief: { done: true, text: "Нужен специальный болт, который стягивает элементы толщиной 150 мм, с посадочной поверхностью в центре 12 мм.", sketch: null, by: "вы", when: "14:55" },
        layout: { state: "waiting", img: "sbolt-layout.svg", by: "агент", when: "14:59", bases: 4, ifaces: 2, bodies: 1,
          assumptions: ["150 мм — суммарная толщина пакета, показан одним телом", "«посадочная поверхность в центре 12 мм» понята как гладкий поясок Ø12 длиной 12 по центру пакета — уточните", "резьба не задана, принята М12 (равна посадочному диаметру)", "нагрузки не заданы — расчёт стыка после уточнения", "сечение пакета 60×60 — условно"] },
        design: { state: "none", variants: [], chosen: null },
        kit: { state: "none", files: [] },
        last: { job: "layout", report: ["Компоновка описана: ось болта, пакет 150 мм, посадочный поясок Ø12 по центру.", "2 коммита. Деталей пока нет — жду вашего согласования.", "Уточните допущение 2: Ø12 — это диаметр, длина или и то и другое?"], steps: null },
        history: [
          { when: "14:55", who: "вы", what: "Проект «Специальный болт»" },
          { when: "14:58", who: "агент", what: "скелет компоновки: ось болта, пакет 150, посадочная поверхность Ø12 в центре, допущения A1–A5" },
          { when: "14:59", who: "агент", what: "продольная секущая плоскость для главного вида, габарит пакета 60×60" },
        ],
      },
      {
        id: "pipe_bracket", code: "kronshteyn_pod_trubu", title: "Кронштейн под трубу Ø108", folder: "opory", updated: "вчера 07:43",
        brief: { done: true, text: "Кронштейн под трубу Ø108 на стене, вылет оси 500. Нагрузка 20 кН вниз. Плита s=12 на 4 анкерах М16, два ребра.", sketch: "pipe_bracket-sketch.png", by: "вы", when: "07:43" },
        layout: { state: "none" },
        design: { state: "none", variants: [], chosen: null },
        kit: { state: "none", files: [] },
        history: [{ when: "07:43", who: "вы", what: "Проект «Кронштейн под трубу Ø108», набросок от руки" }],
      },
      {
        id: "bracket", code: "bracket", title: "Сварной кронштейн под ось Ø50", folder: "opory", updated: "2 дня назад",
        brief: { done: true, text: "Опора горизонтальной оси Ø50 на стене, вылет 220. Fv = 20 кН вниз, Fh = 4 кН от стены. Бетон B25, анкеры М16. Справа в 150 мм короб.", sketch: null, by: "вы", when: "2 дня назад" },
        layout: { state: "approved", img: "bracket-layout.png", by: "вы", when: "2 дня назад", bases: 2, ifaces: 2, bodies: 2, assumptions: ["анкеры химические М16, бетон B25", "ось — сталь 40Х, посадка H8/f7"] },
        design: { state: "done", chosen: null, variants: [
          { id: "A_fork", title: "A. Вилка из двух щёк", img: "bracket-A_fork-iso.png", sketch: "bracket-A_fork-sketch.png", mass: 17.15, kmin: 1.14, kitem: "анкеры на вырыв", errors: 0, warnings: 1, note: "запас по анкерам 1,14 < 1,5" },
          { id: "B_hub", title: "B. Ступица из трубы и два ребра", img: "bracket-B_hub-iso.png", sketch: "bracket-B_hub-sketch.png", mass: 14.35, kmin: 1.54, kitem: "шов ребра", errors: 0, warnings: 2, note: "зазор под ключ у анкера 14,5 мм; шов ребра K 1,54" },
          { id: "C_box", title: "C. Коробчатая консоль с бобышкой", img: "bracket-C_box-iso.png", sketch: "bracket-C_box-sketch.png", mass: 18.54, kmin: 1.54, kitem: "анкеры на вырыв", errors: 0, warnings: 0, note: "" },
        ] },
        kit: { state: "none", files: [] },
        last: { job: "design", report: ["Три варианта собраны и проверены. Легче всех B (14,35 кг), без замечаний — C (18,54 кг).", "У A запас по анкерам 1,14 — ниже требуемых 1,5.", "Выберите вариант для комплекта или поручите мне поднять запас у A."], steps: null },
        history: [
          { when: "2 дн.", who: "вы", what: "Проект «Сварной кронштейн под ось Ø50»" },
          { when: "2 дн.", who: "агент", what: "скелет и обстановка: стена, ось, короб" },
          { when: "2 дн.", who: "вы", what: "Компоновка согласована" },
          { when: "2 дн.", who: "агент", what: "генератор: три варианта — вилка, ступица, короб" },
          { when: "2 дн.", who: "агент", what: "вылет 200 → 220 по замечанию R2" },
        ],
      },
      {
        id: "pipe_support", code: "pipe_support", title: "Опора под трубу Ø108 на полу", folder: "opory", updated: "3 дня назад",
        brief: { done: true, text: "Опора под горизонтальную трубу Ø108 на полу: отметка оси 600, Fv = 8 кН. Плита на 4 анкерах М12.", sketch: null, by: "вы", when: "3 дня назад" },
        layout: { state: "approved", img: "pipe_support-layout.png", by: "вы", when: "3 дня назад", bases: 2, ifaces: 2, bodies: 2, assumptions: ["пол — бетон B20", "труба лежит в ложементе, не приварена"] },
        design: { state: "done", chosen: "A_tube", variants: [
          { id: "A_tube", title: "A. Стойка из трубы", img: "pipe_support-A_tube-iso.png", sketch: "pipe_support-A_tube-sketch.png", mass: 12.4, kmin: 1.62, kitem: "анкеры", errors: 0, warnings: 1, note: "сварной шов ложемента — проверить катет" },
          { id: "B_plates", title: "B. Стойка из двух пластин", img: "pipe_support-B_plates-iso.png", sketch: "pipe_support-B_plates-sketch.png", mass: 14.9, kmin: 1.71, kitem: "анкеры", errors: 0, warnings: 0, note: "" },
        ] },
        kit: { state: "none", files: [] },
        history: [
          { when: "3 дн.", who: "вы", what: "Проект «Опора под трубу Ø108 на полу»" },
          { when: "3 дн.", who: "агент", what: "скелет: пол, ось трубы на отметке 600" },
          { when: "3 дн.", who: "вы", what: "Компоновка согласована" },
          { when: "3 дн.", who: "агент", what: "два варианта стойки: труба и пластины" },
          { when: "вчера", who: "вы", what: "Выбран вариант A_tube" },
        ],
      },
      {
        id: "plate", code: "plate", title: "Планка с двумя отверстиями", folder: "primery", updated: "неделю назад",
        brief: { done: true, text: "Планка 120×40, s = 6, два отверстия Ø11 под М10 с шагом 80.", sketch: null, by: "вы", when: "неделю назад" },
        layout: { state: "approved", img: "plate-layout.png", by: "вы", when: "неделю назад", bases: 2, ifaces: 1, bodies: 1, assumptions: ["материал Ст3сп"] },
        design: { state: "done", chosen: "A_base", variants: [
          { id: "A_base", title: "A. Планка 120×40", img: "plate-A_base-iso.png", sketch: "plate-A_base-sketch.png", mass: 0.21, kmin: 2.3, kitem: "смятие", errors: 0, warnings: 0, note: "" },
          { id: "B_wide", title: "B. Планка 120×60", img: "plate-B_wide-iso.png", sketch: "plate-B_wide-sketch.png", mass: 0.32, kmin: 2.9, kitem: "смятие", errors: 0, warnings: 0, note: "" },
        ] },
        kit: { state: "ready", when: "неделю назад", files: [["STEP", "plate_A_base.step", "сборка AP242"], ["PDF", "plate_A_base_sketch.pdf", "эскиз с размерами, 3 вида"], ["PDF", "plate_A_base_spec.pdf", "спецификация"], ["PDF", "plate_A_base_report.pdf", "отчёт: запасы, допущения"]] },
        history: [
          { when: "нед.", who: "вы", what: "Проект «Планка»" },
          { when: "нед.", who: "агент", what: "два варианта планки" },
          { when: "нед.", who: "вы", what: "Выбран вариант A_base" },
          { when: "нед.", who: "агент", what: "комплект: STEP, эскиз, спецификация, отчёт" },
        ],
      },
    ],
  };
}

// --- Сценарии агента: шаги фразами (t), итог строкой (r), картинка (img) --------------------------
const SCRIPTS = {
  layout(p) {
    const img = p.id === "bolt" ? "bolt-layout.svg" : p.id === "sbolt" ? "sbolt-layout.svg" : p.id === "pipe_bracket" ? "pipe_bracket-layout.png" : "pipe_bracket-layout.png";
    return [
      { t: `Читаю проект «${p.title}»`, r: p.brief.sketch ? "задание и набросок" : "задание" },
      ...(p.brief.sketch ? [{ t: "Смотрю набросок", img: p.brief.sketch, r: "стена, труба Ø108, вылет 500, Fv 20 кН" }] : []),
      { t: "Смотрю каталог: крепёж и материалы", r: "размеры из таблиц пакета ГОСТ" },
      { t: "Правлю project.yaml: требования, скелет, обстановка", r: "коммит f29593f" },
      { t: "Смотрю компоновку, главный вид", img, r: "базы и зоны на месте" },
      { t: "Проверяю", r: "замечаний нет" },
      { t: "Готово: компоновка ждёт вашего согласования" },
    ];
  },
  design(p) {
    const bolt = p.id === "bolt";
    const img = bolt ? "bolt-design.svg" : "pipe_support-A_tube-iso.png";
    const sk = bolt ? "bolt-design.svg" : "pipe_support-A_tube-sketch.png";
    return [
      { t: `Читаю проект «${p.title}»`, r: "компоновка согласована" },
      { t: bolt ? "Пишу генератор деталей: болт, гайка, две шайбы" : "Пишу генератор деталей", r: "коммит 7c1e2a0" },
      { t: "Собираю вариант A_base", img, r: bolt ? "4 детали, масса 0,21 кг" : "5 деталей, масса 12,4 кг" },
      { t: "Проверяю вариант A_base", r: bolt ? "ошибок 0, предупреждений 1: класс прочности не задан" : "ошибок 0, предупреждений 1" },
      { t: "Эскиз с размерами", img: sk, r: bolt ? "130, 100, М16 — совпадают с моделью" : "размеры совпадают с моделью" },
      { t: bolt ? "Готово: 1 вариант, масса 0,21 кг" : "Готово: 1 вариант" },
    ];
  },
  kit(p) {
    const v = p.design.chosen || (p.design.variants[0] && p.design.variants[0].id) || "A_base";
    return [
      { t: `Собираю вариант ${v} с экспортом`, r: "STEP, 3 вида, эскиз" },
      { t: "Пишу спецификацию и отчёт", r: "позиции, запасы K, допущения" },
      { t: "Готово: комплект из 4 файлов" },
    ];
  },
  fix(p) {
    return [
      { t: `Читаю проект «${p.title}»`, r: "ошибки и предупреждения" },
      { t: "Правлю параметры: анкеры М16 → М20", r: "коммит 9a1c0e4" },
      { t: "Собираю и проверяю", r: "запас по анкерам 1,62" },
      { t: "Готово: ошибок нет" },
    ];
  },
};
function finishJob(p, job) {
  const when = nowStr();
  if (job === "layout") {
    const img = p.id === "bolt" ? "bolt-layout.svg" : p.id === "sbolt" ? "sbolt-layout.svg" : "pipe_bracket-layout.png";
    p.layout = { state: "waiting", img, by: "агент", when, bases: 3, ifaces: 2, bodies: 2, assumptions: ["нагрузка приложена к оси трубы, вниз", "стена — бетон B25, анкеры химические", "вылет 500 — до оси трубы"] };
    p.last = { job, report: ["Компоновка описана: базы, интерфейсы и обстановка — по заданию" + (p.brief.sketch ? " и наброску" : "") + ".", "1 коммит. Детали — после вашего согласования.", "Допущения — 3, посмотрите их под эскизом."] };
    p.history.push({ when, who: "агент", what: "скелет и обстановка по заданию: компоновка на согласование" });
  } else if (job === "design") {
    const bolt = p.id === "bolt";
    p.design = { state: "done", chosen: null, variants: [bolt
      ? { id: "A_base", title: "A. Болт М16, пакет 100", img: "bolt-design.svg", sketch: "bolt-design.svg", mass: 0.21, kmin: null, kitem: "", errors: 0, warnings: 1, note: "класс прочности болта не задан — принят 5.8" }
      : { id: "A_base", title: "A. Базовый вариант", img: "pipe_support-A_tube-iso.png", sketch: "pipe_support-A_tube-sketch.png", mass: 12.4, kmin: 1.62, kitem: "анкеры", errors: 0, warnings: 1, note: "шов ложемента — проверить катет" }] };
    p.last = { job, report: [bolt ? "Болт М16×130 ГОСТ 7798-70, гайка, две шайбы; отверстие в пакете Ø18." : "Собран базовый вариант.", "2 коммита. Ошибок нет, одно предупреждение: " + p.design.variants[0].note + ".", "Можно выдавать комплект или задать нагрузку — тогда посчитаю запас."] };
    p.history.push({ when, who: "агент", what: bolt ? "генератор деталей: болт, гайка, шайбы; вариант A_base" : "генератор деталей; вариант A_base" });
  } else if (job === "kit") {
    const v = p.design.chosen || p.design.variants[0].id;
    p.kit = { state: "ready", when, files: [["STEP", `${p.code}_${v}.step`, "сборка AP242"], ["PDF", `${p.code}_${v}_sketch.pdf`, "эскиз с размерами, 3 вида"], ["PDF", `${p.code}_${v}_spec.pdf`, "спецификация"], ["PDF", `${p.code}_${v}_report.pdf`, "отчёт: запасы, допущения"]] };
    p.last = { job, report: [`Комплект по варианту ${v}: STEP, эскиз, спецификация, отчёт.`, "Ошибок нет."] };
    p.history.push({ when, who: "агент", what: `комплект по варианту ${v}` });
  } else if (job === "fix") {
    p.design.variants.forEach(v => { v.errors = 0; if (v.kmin != null && v.kmin < 1.5) v.kmin = 1.62; });
    p.last = { job, report: ["Запас по анкерам поднят: М16 → М20, K 1,14 → 1,62.", "1 коммит."] };
    p.history.push({ when, who: "агент", what: "анкеры М20: K 1,14 → 1,62" });
  }
  p.updated = "сегодня " + when;
}

// --- Ядро: состояние, выбор, отмена, следующий шаг, имитация агента ----------------------------------
const core = {
  state: initialState(), undo: [], listeners: [], log: [], speed: 650, hook: null,
  cur: { folder: "krepezh", project: null, stage: null, view: "main" },
  ui: { closed: {}, dialog: null, form: {}, details: false, sketch: {}, drawer: false },
  on(fn) { this.listeners.push(fn); },
  emit() { for (const fn of this.listeners) fn(); },
  project(id) { return this.state.projects.find(p => p.id === id) || null; },
  folder(id) { return this.state.folders.find(f => f.id === id) || null; },
  projectsIn(fid) { return this.state.projects.filter(p => p.folder === fid); },
  current() { return this.cur.project ? this.project(this.cur.project) : null; },
  // снимок для отмены: таймеры агента не сериализуются — действия, которые отменяются, его не трогают
  commit(label, fn) {
    const before = JSON.stringify(this.state);
    const out = fn();
    if (out) { toast(out); return false; }
    this.undo.push({ label, state: before });
    this.log.push(label);
    this.emit();
    return true;
  },
  undoLast() {
    const x = this.undo.pop();
    if (!x) return toast("Отменять нечего");
    this.state = JSON.parse(x.state);
    if (this.cur.project && !this.project(this.cur.project)) this.cur.project = null;
    if (!this.folder(this.cur.folder)) this.cur.folder = this.state.folders[0].id;
    this.log.push("undo:" + x.label);
    this.emit();
    toast(`Отменено: ${x.label}`);
  },
  // --- выбор
  open(pid, stage) {
    const p = this.project(pid);
    if (!p) return;
    this.cur.project = pid; this.cur.folder = p.folder; this.cur.stage = stage || this.nextOf(p).stage; this.ui.details = false; this.ui.drawer = false;
    this.log.push("open:" + pid);
    this.emit();
  },
  openFolder(fid) { this.cur.folder = fid; this.cur.project = null; this.cur.stage = null; this.emit(); },
  toggleFolder(fid) {
    if (this.cur.folder === fid && !this.cur.project) this.ui.closed[fid] = !this.ui.closed[fid];
    else { this.ui.closed[fid] = false; this.cur.folder = fid; this.cur.project = null; this.cur.stage = null; }
    this.emit();
  },
  setStage(sid) { this.cur.stage = sid; this.emit(); },
  // --- этапы и следующий шаг
  stageState(p, sid) {
    const L = p.layout.state, D = p.design.state, K = p.kit.state;
    if (sid === "brief") return p.brief.done ? "done" : "next";
    if (sid === "layout") return L === "approved" ? "done" : L === "waiting" || L === "changed" ? "wait" : L === "agent" ? "agent" : p.brief.done ? "next" : "todo";
    if (sid === "design") {
      if (D === "agent") return "agent";
      if (D === "done") return this.errors(p) ? "wait" : p.design.variants.length > 1 && !p.design.chosen ? "wait" : "done";
      return L === "approved" ? "next" : "todo";
    }
    if (K === "ready") return "done";
    if (K === "agent") return "agent";
    return D === "done" && !this.errors(p) && (p.design.chosen || p.design.variants.length === 1) ? "next" : "todo";
  },
  errors(p) { return p.design.variants.reduce((s, v) => s + (v.errors || 0), 0); },
  stages(p) { return STAGES.map(s => ({ ...s, state: this.stageState(p, s.id) })); },
  nextOf(p) {
    const L = p.layout.state, D = p.design.state, K = p.kit.state;
    if (p.agent) {
      const what = { layout: "Агент строит компоновку", design: "Агент делает детали", kit: "Агент собирает комплект", fix: "Агент устраняет ошибки" }[p.agent.job];
      return { stage: p.agent.job === "fix" ? "design" : p.agent.job, kind: "running", title: what, label: what + "…", hint: p.agent.steps.length ? p.agent.steps[p.agent.steps.length - 1].t : "", short: "у агента" };
    }
    if (!p.brief.done) return { stage: "brief", kind: "agent", title: "Опишите, что нужно", hint: "Назначение, нагрузки, к чему крепится; приложите набросок. Агент опишет скелет и покажет компоновку.", label: "Поручить агенту компоновку", act: "run:layout", short: "задание", disabled: !(p.brief.text || "").trim() };
    if (L === "none") return { stage: "layout", kind: "agent", title: "Задание принято", hint: "Агент опишет скелет и обстановку и покажет компоновку на согласование.", label: "Поручить агенту компоновку", act: "run:layout", short: "дальше: компоновка" };
    if (L === "waiting" || L === "changed") return { stage: "layout", kind: "you", title: L === "changed" ? "Компоновка изменена после согласования" : "Компоновка ждёт вашего согласования", hint: "Посмотрите эскиз и допущения. Согласуйте или поправьте прямо на эскизе.", label: "Согласовать компоновку", act: "approve", short: "ждёт согласования" };
    if (D === "none") return { stage: "design", kind: "agent", title: "Компоновка согласована", hint: "Агент сделает детали и варианты, проверит запасы и массу.", label: "Поручить агенту детали", act: "run:design", short: "дальше: детали" };
    const errs = this.errors(p), vs = p.design.variants;
    if (errs) return { stage: "design", kind: "you", title: `Ошибки: ${errs}`, hint: "Ошибки блокируют комплект. Поручите агенту устранить или поправьте параметры сами.", label: "Поручить агенту устранить", act: "run:fix", short: "ошибки" };
    if (vs.length > 1 && !p.design.chosen) return { stage: "design", kind: "you", title: `${plural(vs.length, "вариант готов", "варианта готовы", "вариантов готовы")} — выберите`, hint: "Сравните массу и запасы, выберите вариант для комплекта.", label: "Сравнить и выбрать", act: "stage:design", short: "выбрать вариант" };
    if (K === "none") return { stage: "kit", kind: "agent", title: `Вариант выбран: ${p.design.chosen || vs[0].id}`, hint: "Комплект: STEP, эскизы с размерами, спецификация, отчёт.", label: "Выдать комплект", act: "run:kit", short: "дальше: комплект" };
    return { stage: "kit", kind: "done", title: "Комплект готов", hint: "STEP, эскизы, спецификация, отчёт — скачайте или передайте в САПР.", label: "Скачать комплект", act: "download", short: "готово" };
  },
  // --- действия конструктора
  act(a, el) {
    if (this.hook && this.hook(a, el) === true) return;
    const [verb, arg] = a.split(":");
    const p = this.current();
    switch (verb) {
      case "open": return this.open(arg, el && el.dataset.stage);
      case "folder": return this.openFolder(arg);
      case "stage": return this.setStage(arg);
      case "view": this.cur.view = arg; return this.emit();
      case "next": { if (!p) return; const n = this.nextOf(p); if (n.disabled) return toast("Опишите задание — хотя бы одной фразой"); return this.act(n.act, el); }
      case "run": return this.run(p.id, arg);
      case "stop": return this.stop(p && p.id);
      case "approve": return this.commit("согласование компоновки", () => { if (!p || !["waiting", "changed"].includes(p.layout.state)) return "Согласовывать нечего"; p.layout.state = "approved"; p.layout.by = "вы"; p.layout.when = nowStr(); p.history.push({ when: nowStr(), who: "вы", what: "Компоновка согласована" }); this.cur.stage = "design"; });
      case "choose": return this.commit("выбор варианта " + arg, () => { if (!p) return "Нет проекта"; p.design.chosen = arg; p.history.push({ when: nowStr(), who: "вы", what: "Выбран вариант " + arg }); this.cur.stage = "kit"; });
      case "download": this.log.push("download:" + (p && p.id)); return toast("Комплект скачан: STEP, эскиз, спецификация, отчёт");
      case "attach": return this.commit("набросок к заданию", () => { if (!p) return "Нет проекта"; p.brief.sketch = "pipe_bracket-sketch.png"; });
      case "sketch": this.ui.sketch[arg] = !this.ui.sketch[arg]; return this.emit();
      case "details": this.ui.details = !this.ui.details; return this.emit();
      case "drawer": this.ui.drawer = !this.ui.drawer; return this.emit();
      case "new-project": this.ui.dialog = "project"; this.ui.form = { title: "", folder: (el && el.dataset.folder) || this.cur.folder, base: "" }; return this.emit();
      case "new-folder": this.ui.dialog = "folder"; this.ui.form = { name: "" }; return this.emit();
      case "cancel": this.ui.dialog = null; return this.emit();
      case "create": return this.ui.dialog === "folder" ? this.createFolder(this.ui.form.name) : this.createProject(this.ui.form);
      case "delete": return this.deleteProject(arg || (p && p.id));
      case "delete-folder": return this.deleteFolder(arg);
      case "undo": return this.undoLast();
      case "edit-layout": return toast("В макете: правка компоновки на эскизе — ручки и точные числа");
      case "mark": return toast("В макете: обвести замечание прямо на эскизе");
      case "rename": return toast("В макете: переименование");
      default: return toast("В макете это не работает: " + a);
    }
  },
  createProject({ title, folder, base }) {
    title = (title || "").trim();
    if (!title) return toast("Назовите изделие");
    const id = "p" + Date.now().toString(36);
    const code = title.toLowerCase().replace(/[^a-zа-яё0-9]+/gi, "_").replace(/^_|_$/g, "").slice(0, 32);
    const ok = this.commit("создание проекта", () => {
      this.state.projects.push({ id, code, title, folder: folder || this.cur.folder, updated: "сейчас",
        brief: { done: false, text: "", sketch: null }, layout: { state: "none" }, design: { state: "none", variants: [], chosen: null }, kit: { state: "none", files: [] },
        history: [{ when: nowStr(), who: "вы", what: `Проект «${title}»` + (base ? ` из примера ${base}` : "") }] });
      this.ui.dialog = null;
      this.cur.project = id; this.cur.folder = folder || this.cur.folder; this.cur.stage = "brief"; this.ui.closed[this.cur.folder] = false;
    });
    if (ok) toast(`Проект «${title}» создан. Опишите задание.`);
  },
  createFolder(name) {
    name = (name || "").trim();
    if (!name) return toast("Назовите папку");
    const id = "f" + Date.now().toString(36);
    this.commit("создание папки", () => { this.state.folders.push({ id, name }); this.ui.dialog = null; this.cur.folder = id; this.cur.project = null; this.cur.stage = null; });
  },
  deleteProject(pid) {
    const p = this.project(pid);
    if (!p) return toast("Нет проекта");
    if (p.agent) return toast("Проект у агента: сначала остановите задачу");
    this.commit("удаление проекта", () => { this.state.projects = this.state.projects.filter(x => x.id !== pid); if (this.cur.project === pid) { this.cur.project = null; this.cur.stage = null; } });
    toast(`Проект «${p.title}» удалён`, { undo: true });
  },
  deleteFolder(fid) {
    const f = this.folder(fid);
    if (!f) return;
    if (this.projectsIn(fid).length) return toast("Папка не пуста: сначала перенесите или удалите проекты");
    this.commit("удаление папки", () => { this.state.folders = this.state.folders.filter(x => x.id !== fid); if (this.cur.folder === fid) this.cur.folder = this.state.folders[0].id; });
    toast(`Папка «${f.name}» удалена`, { undo: true });
  },
  setBrief(pid, text) {
    const p = this.project(pid);
    if (!p) return;
    p.brief.text = text;
    const dis = !text.trim();
    document.querySelectorAll('[data-act="next"]').forEach(b => (b.disabled = dis));
  },
  // --- имитация агента: шаги по таймеру; speed = 0 — всё сразу (прогон сценариев)
  run(pid, job) {
    const p = this.project(pid);
    if (!p || p.agent) return;
    if (job === "layout" && !p.brief.done) { if (!(p.brief.text || "").trim()) return toast("Опишите задание"); p.brief.done = true; p.brief.by = "вы"; p.brief.when = nowStr(); }
    if (job === "layout") p.layout = { ...p.layout, state: "agent" };
    if (job === "design" || job === "fix") p.design.state = "agent";
    if (job === "kit") p.kit.state = "agent";
    const steps = SCRIPTS[job](p);
    p.agent = { job, steps: [], started: Date.now() };
    this.cur.stage = job === "fix" ? "design" : job;
    this.log.push("run:" + job);
    let i = 0;
    const tick = () => {
      if (!p.agent) return;
      if (i > 0) { const s = p.agent.steps[i - 1]; s.done = true; s.sec = 2 + ((i * 7) % 9); }
      if (i < steps.length) { p.agent.steps.push({ ...steps[i], done: false }); i++; this.emit(); if (this.speed) p.agent.timer = setTimeout(tick, this.speed); else tick(); }
      else { const done = p.agent.steps; p.agent = null; finishJob(p, job); if (p.last) p.last.steps = done; clock += 3; this.emit(); }
    };
    tick();
  },
  stop(pid) {
    const p = pid && this.project(pid);
    if (!p || !p.agent) return;
    clearTimeout(p.agent.timer);
    const job = p.agent.job;
    p.agent = null;
    if (job === "layout") p.layout.state = p.layout.img ? "waiting" : "none";
    if (job === "design" || job === "fix") p.design.state = p.design.variants.length ? "done" : "none";
    if (job === "kit") p.kit.state = "none";
    p.last = { job, report: ["Остановлено вами. Сделанное осталось в истории, модель не тронута."], steps: null };
    this.emit();
  },
};

// --- Кусочки интерфейса: общие для всех макетов ------------------------------------------------------
const KIND_DOT = { you: "wait", agent: "todo", running: "agent", done: "done" };
function toast(message, { undo = false } = {}) {
  let box = document.getElementById("toast");
  if (!box) { box = document.createElement("div"); box.id = "toast"; document.body.appendChild(box); }
  box.innerHTML = `<span>${esc(message)}</span>${undo ? `<button data-act="undo">Вернуть</button>` : ""}`;
  box.style.display = "flex";
  clearTimeout(toast.t); toast.t = setTimeout(() => (box.style.display = "none"), undo ? 8000 : 3500);
}
function pic(src, { h = 240, alt = "", cls = "", fit = "contain" } = {}) {
  return src
    ? `<figure class="pic ${cls}" style="height:${h}px"><img src="${IMG}${src}" alt="${esc(alt)}" style="object-fit:${fit}"></figure>`
    : `<figure class="pic empty ${cls}" style="height:${h}px">${esc(alt || "картинки пока нет")}</figure>`;
}
function facts(items) {
  return `<div class="facts">${items.filter(Boolean).map(([k, v, cls]) => `<div><span class="k">${esc(k)}</span><span class="v ${cls || ""}">${v}</span></div>`).join("")}</div>`;
}
function treeHtml({ tools = true } = {}) {
  const s = core.state;
  return `<div class="tree">${tools ? `<div class="tree__tools"><button class="sm" data-act="new-project" title="Новый проект в выбранной папке">+ Проект</button><button class="sm" data-act="new-folder" title="Новая папка">+ Папка</button></div>` : ""}<div class="tree__list" data-keep="tree">${s.folders.map(f => {
    const open = !core.ui.closed[f.id], ps = core.projectsIn(f.id);
    return `<div class="tfold ${open ? "open" : ""} ${core.cur.folder === f.id && !core.cur.project ? "sel" : ""}" data-tree="folder:${f.id}"><span class="chev">▸</span><span>${esc(f.name)}</span><span class="count">${ps.length}</span></div>${open ? (ps.length ? ps.map(projRow).join("") : `<div class="empty">пусто — <a href="#" data-act="new-project" data-folder="${f.id}">новый проект</a></div>`) : ""}`;
  }).join("")}</div></div>`;
}
function projRow(p) {
  const n = core.nextOf(p);
  return `<div class="tproj ${core.cur.project === p.id ? "sel" : ""}" data-tree="project:${p.id}" title="${esc(n.title)}"><i class="dot ${KIND_DOT[n.kind]}"></i><span class="name">${esc(p.title)}</span><span class="st">${esc(n.short)}</span></div>`;
}
function nextHtml(p, { size = "", stop = true, stack = false } = {}) {
  const n = core.nextOf(p);
  const cls = { you: "wait", agent: "", running: "agent", done: "done" }[n.kind];
  const btn = n.kind === "running" ? (stop ? `<button class="sm" data-act="stop">Остановить</button>` : "")
    : n.kind === "done" ? `<button data-act="download">Скачать</button>`
    : `<button class="primary ${size}" data-act="next" ${n.disabled ? "disabled" : ""}>${esc(n.label)}</button>`;
  return `<div class="next ${cls} ${stack ? "stack" : ""}" data-next><div class="t"><b>${n.kind === "running" ? `<span class="spin"></span> ${esc(n.title)}` : esc(n.title)}</b><span>${esc(n.hint)}</span></div>${btn}</div>`;
}
function stepsHtml(steps, { h = 110, live = false } = {}) {
  return `<ol class="asteps">${steps.map(s => `<li class="astep ${live && !s.done ? "live" : ""}"><span class="g ${s.done ? "ok" : ""}">${s.done ? "✓" : live ? `<span class="spin"></span>` : "·"}</span><div class="txt">${esc(s.t)}${s.done && s.r ? ` <span class="r">— ${esc(s.r)}</span>` : ""}${s.done && s.img ? `<div class="img" style="height:${h}px"><img src="${IMG}${s.img}" alt=""></div>` : ""}</div></li>`).join("")}</ol>`;
}
function agentHtml(p, { h = 110, idle = true } = {}) {
  if (p.agent) return `<div class="agent">${stepsHtml(p.agent.steps, { h, live: true })}</div>`;
  if (p.last) {
    const n = p.last.steps ? p.last.steps.length : 0;
    return `<div class="agent"><div class="report"><b>Агент: ${{ layout: "компоновка", design: "детали", kit: "комплект", fix: "исправление" }[p.last.job]}</b><ul>${p.last.report.map(l => `<li>${esc(l)}</li>`).join("")}</ul></div>${n ? `<details class="more" ${core.ui.details ? "open" : ""}><summary data-act="details">Как работал агент: ${plural(n, "шаг", "шага", "шагов")}</summary>${stepsHtml(p.last.steps, { h })}</details>` : ""}</div>`;
  }
  return idle ? `<p class="muted xs">Агент свободен. Следующий шаг — в карточке выше.</p>` : "";
}
function briefHtml(p, { h = 220 } = {}) {
  if (!p.brief.done) {
    return `<div style="display:flex;flex-direction:column;gap:10px"><label class="field">Что нужно сделать<textarea data-field="brief" placeholder="Назначение, нагрузки (кН), к чему крепится, габариты. Например: кронштейн под трубу Ø108 на стене, вылет 500, нагрузка 20 кН вниз" oninput="core.setBrief('${p.id}', this.value)">${esc(p.brief.text || "")}</textarea></label><div style="display:flex;gap:10px;align-items:center">${p.brief.sketch ? pic(p.brief.sketch, { h: 120, alt: "набросок" }) : ""}<button data-act="attach">${p.brief.sketch ? "Заменить набросок" : "Добавить набросок или фото"}</button></div></div>`;
  }
  return `<div style="display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start"><div style="flex:1 1 260px;min-width:0"><p style="font-size:15px;line-height:22px">${esc(p.brief.text)}</p><p class="muted xs" style="margin-top:6px">${esc(p.brief.by)} · ${esc(p.brief.when)}</p></div>${p.brief.sketch ? `<div style="flex:1 1 300px">${pic(p.brief.sketch, { h, alt: "набросок конструктора" })}</div>` : ""}</div>`;
}
function layoutHtml(p, { h = 360, actions = true } = {}) {
  const L = p.layout;
  if (L.state === "none" || (L.state === "agent" && !L.img)) return pic(null, { h: Math.min(h, 160), alt: p.brief.done ? "компоновки ещё нет — агент опишет скелет по заданию" : "компоновка появится после задания" });
  const st = L.state === "approved" ? `<span class="pill done">✓ согласована · ${esc(L.by)} · ${esc(L.when)}</span>` : L.state === "agent" ? `<span class="pill agent">у агента</span>` : `<span class="pill wait">ждёт вашего согласования</span>`;
  const acts = actions && L.state !== "agent" ? `<div style="display:flex;gap:8px;flex-wrap:wrap">${L.state !== "approved" ? `<button class="primary" data-act="approve">Согласовать компоновку</button>` : ""}<button class="ghost" data-act="edit-layout">Поправить на эскизе</button><button class="ghost" data-act="mark">Обвести замечание</button></div>` : "";
  const as = L.assumptions && L.assumptions.length ? `<details class="more"><summary>Допущения агента: ${L.assumptions.length}</summary><ul class="xs muted" style="margin:6px 0 0;padding-left:18px">${L.assumptions.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>` : "";
  return `<div style="display:flex;flex-direction:column;gap:10px"><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">${st}${facts([["базы", L.bases], ["интерфейсы", L.ifaces], ["обстановка", L.bodies]])}</div>${pic(L.img, { h, alt: "компоновочный эскиз" })}${acts}${as}</div>`;
}
function variantCard(p, v, { h = 150, choose = true } = {}) {
  const chosen = p.design.chosen === v.id, sk = core.ui.sketch[v.id];
  const warn = v.kmin != null && v.kmin < 1.5;
  return `<div class="var ${chosen ? "chosen" : ""}" data-var="${v.id}"><div class="t"><span>${esc(v.title)}</span>${chosen ? `<span class="pill agent">выбран</span>` : ""}</div>${pic(sk ? v.sketch : v.img, { h, alt: v.title })}${facts([["масса, кг", fmt(v.mass)], ["K min", v.kmin == null ? "—" : fmt(v.kmin), warn ? "error" : ""], ["замечания", v.errors ? `<span class="error">${v.errors} ош.</span>` : v.warnings ? `${v.warnings} пред.` : "нет", v.errors ? "error" : v.warnings ? "warn" : ""]])}${v.note ? `<p class="xs muted">${esc(v.note)}</p>` : ""}<div class="actions"><button class="sm ghost" data-act="sketch:${v.id}">${sk ? "3D" : "Эскиз"}</button>${choose && !chosen && p.design.variants.length > 1 ? `<button class="sm" data-act="choose:${v.id}">Выбрать</button>` : ""}</div></div>`;
}
function designHtml(p, { h = 150 } = {}) {
  if (!p.design.variants.length) return pic(null, { h: 140, alt: p.layout.state === "approved" ? "деталей ещё нет — поручите агенту" : "детали — после согласования компоновки" });
  return `<div class="vars">${p.design.variants.map(v => variantCard(p, v, { h })).join("")}</div>`;
}
function kitHtml(p) {
  if (p.kit.state !== "ready") return pic(null, { h: 120, alt: p.design.state === "done" ? "комплект соберётся по выбранному варианту" : "комплект — после деталей" });
  return `<div class="files">${p.kit.files.map(([ext, n, s]) => `<div class="file"><span class="ext">${ext}</span><span class="n">${esc(n)}</span><span class="s">${esc(s)}</span><button class="sm quiet" data-act="download">Скачать</button></div>`).join("")}</div>`;
}
function historyHtml(p, n = 6) {
  const h = p.history.slice(-n).reverse();
  return `<ul class="hist">${h.map(x => `<li><span class="w">${esc(x.when)}</span><b>${esc(x.who)}</b><span>${esc(x.what)}</span></li>`).join("")}</ul>`;
}
function dialogHtml() {
  const d = core.ui.dialog;
  if (!d) return "";
  const f = core.ui.form;
  if (d === "folder") return `<div class="veil" data-act="cancel"><form class="dlg" onclick="event.stopPropagation()" onsubmit="event.preventDefault(); core.act('create')"><h2>Новая папка</h2><label class="field">Название<input type="text" data-field="name" autofocus value="${esc(f.name)}" oninput="core.ui.form.name = this.value"></label><div class="actions"><button type="button" data-act="cancel">Отмена</button><button type="submit" class="primary" data-act="create">Создать</button></div></form></div>`;
  return `<div class="veil" data-act="cancel"><form class="dlg" onclick="event.stopPropagation()" onsubmit="event.preventDefault(); core.act('create')"><h2>Новый проект</h2><label class="field">Название изделия<input type="text" data-field="title" autofocus placeholder="например, Хомут трубы Ø57" value="${esc(f.title)}" oninput="core.ui.form.title = this.value"></label><label class="field">Папка<select data-field="folder" onchange="core.ui.form.folder = this.value">${core.state.folders.map(x => `<option value="${x.id}" ${x.id === f.folder ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></label><label class="field">Начать с<select data-field="base" onchange="core.ui.form.base = this.value"><option value="">пустого проекта — задание опишете словами и наброском</option><option value="bracket">копии примера «Кронштейн на стене»</option><option value="pipe_support">копии примера «Опора под трубу»</option></select></label><div class="actions"><button type="button" data-act="cancel">Отмена</button><button type="submit" class="primary" data-act="create">Создать</button></div></form></div>`;
}
function howHtml(lines, id = "how") {
  return `<details class="more how" ${core.ui[id] ? "open" : ""}><summary onclick="core.ui['${id}'] = !core.ui['${id}']">Как работать</summary><ol>${lines.map(l => `<li>${l}</li>`).join("")}</ol></details>`;
}
// Меню правой кнопки по дереву.
let menuItems = [];
function showMenu(e, items) {
  let m = document.getElementById("menu");
  if (!m) { m = document.createElement("div"); m.id = "menu"; document.body.appendChild(m); }
  menuItems = items;
  m.innerHTML = items.map((it, i) => it === "|" ? "<hr>" : `<button type="button" class="${it.danger ? "danger" : ""}" data-menu="${i}">${esc(it.label)}</button>`).join("");
  m.style.display = "block";
  const w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = Math.min(e.clientX, innerWidth - w - 8) + "px";
  m.style.top = Math.min(e.clientY, innerHeight - h - 8) + "px";
}
function hideMenu() { const m = document.getElementById("menu"); if (m) m.style.display = "none"; }
function treeMenu(ref) {
  const [kind, id] = ref.split(":");
  if (kind === "folder") return [
    { label: "Новый проект здесь", run: () => core.act("new-project", { dataset: { folder: id } }) },
    { label: "Новая папка", run: () => core.act("new-folder") },
    { label: "Переименовать", run: () => core.act("rename") },
    "|",
    { label: "Удалить папку", danger: true, run: () => core.act("delete-folder:" + id) },
  ];
  return [
    { label: "Открыть", run: () => core.open(id) },
    { label: "Переименовать", run: () => core.act("rename") },
    "|",
    { label: "Удалить проект", danger: true, run: () => core.act("delete:" + id) },
  ];
}
document.addEventListener("click", e => {
  const mi = e.target.closest("[data-menu]");
  if (mi) { const it = menuItems[+mi.dataset.menu]; hideMenu(); if (it && it.run) it.run(); return; }
  if (!e.target.closest("#menu")) hideMenu();
  const t = e.target.closest("[data-act], [data-tree]");
  if (!t) return;
  if (t.tagName === "A") e.preventDefault();
  if (t.dataset.tree) { const [kind, id] = t.dataset.tree.split(":"); kind === "folder" ? core.toggleFolder(id) : core.open(id); return; }
  if (t.dataset.act === "details") return; // <summary> сам раскрывается, состояние держим для перерисовки
  if (t.closest("form") && t.dataset.act === "create") return; // submit формы — через onsubmit
  core.act(t.dataset.act, t);
});
document.addEventListener("toggle", e => { if (e.target.querySelector && e.target.querySelector('[data-act="details"]')) core.ui.details = e.target.open; }, true);
document.addEventListener("contextmenu", e => {
  const t = e.target.closest("[data-tree]");
  if (!t) return;
  e.preventDefault();
  showMenu(e, treeMenu(t.dataset.tree));
});
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "я" || e.code === "KeyZ") && !e.target.matches("input, textarea")) { e.preventDefault(); core.undoLast(); }
  if (e.key === "Escape") { core.ui.dialog = null; hideMenu(); core.emit(); }
});
function mount(render, { name, how, act } = {}) {
  core.hook = act || null;
  window.proto = { name, how, core, state: () => core.state, cur: () => core.cur, log: () => core.log, fast() { core.speed = 0; }, next: pid => core.nextOf(core.project(pid)) };
  const draw = () => {
    const keep = [...document.querySelectorAll("[data-keep]")].map(n => [n.dataset.keep, n.scrollTop, n.scrollLeft]);
    const focus = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.field : null;
    render();
    for (const [k, t, l] of keep) { const n = document.querySelector(`[data-keep="${k}"]`); if (n) { n.scrollTop = t; n.scrollLeft = l; } }
    if (core.ui.jump) { core.ui.jump = false; const n = document.querySelector("[data-next]"); if (n) n.scrollIntoView({ block: "center" }); }  // открыли проект — к карточке «что дальше»
    if (focus) { const n = document.querySelector(`[data-field="${focus}"]`); if (n) { n.focus(); if (n.setSelectionRange && n.type !== "select-one") n.setSelectionRange(n.value.length, n.value.length); } }
    else if (core.ui.dialog) { const n = document.querySelector(".dlg [autofocus]"); if (n) n.focus(); }
  };
  core.on(draw);
  draw();
}
