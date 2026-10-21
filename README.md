# SkelCAD

**Среда совместного конструирования «ИИ-агент + инженер-конструктор», сверху вниз.**
Open source, Apache-2.0. Стадия: M0 (обобщение пилота) закрыт 16.10.2026; M1 (агентный контур:
сервер с точкой MCP, проекты в git, изолированный воркер, измерения, рендер, diff) закрыт 19.10.2026,
см. [docs/architecture/04-m1-plan.md](docs/architecture/04-m1-plan.md); M2 (рабочее место конструктора в браузере:
вход через Keycloak, 3D, лента изменений с откатом, параметры с черновиком, задачи агенту) закрыт 19.10.2026,
см. [docs/architecture/05-m2-plan.md](docs/architecture/05-m2-plan.md). M2.1 (компоновка, эскизы с размерами, сравнение) закрыт 2026-10-19; следующий этап — M3, мост к САПР.

*SkelCAD is an open-source environment where an AI agent and a design engineer develop a product
together, top-down (skeleton → units → parts → drawings). The product model, not the CAD file, is
the source of truth; the agent proposes, the engineer decides; every assumption and every check is
visible. Any MCP-capable agent, any CAD through adapters, any standard as an installable package.
English documentation will follow; design documents below are in Russian for now.*

## Идея в трёх предложениях

1. Источник истины — текстовая модель изделия (скелет, интерфейсы, узлы, детали, соединения,
   допущения, замечания, решения), геометрия OCCT и чертежи — производные.
2. Агент (любой MCP-клиент: Claude Code, Cursor, Codex, локальная модель) предлагает изменения,
   строит, проверяет правила и расчёты; конструктор смотрит 3D-diff в браузере и принимает решение.
3. Результат — либо готовый комплект (STEP AP242, спецификация, расчёт, чертежи), либо нативное
   дерево построения в САПР конструктора (SolidWorks, КОМПАС, FreeCAD, …) через рецепт построения
   и адаптер.

## Быстрый старт

```bash
uv sync --all-extras                      # Python 3.12, build123d/OCCT, пакет std-gost
uv run skelcad check-env                  # куб -> STEP, glTF, обратное чтение
uv run skelcad build examples/bracket     # три варианта кронштейна -> examples/bracket/out/, compare.html
uv run skelcad build examples/pipe_support   # опора под трубопровод: два варианта стойки
uv run skelcad check examples/bracket -v A_fork   # только правила, проверки и расчёт
uv run skelcad standards                  # установленные пакеты стандартов
uv run pytest -q
```

Сервер с точкой MCP для агента (этап M1):

```bash
uv run skelcad serve                      # http://127.0.0.1:8000: /mcp, /api, /out; без SKELCAD_TOKENS — режим разработки
SKELCAD_DATABASE_URL=embedded uv run skelcad serve   # + граф связей на встроенном Postgres (поиск, связи)
SKELCAD_TOKENS="claude-code:секрет" uv run skelcad serve
claude mcp add --transport http skelcad https://skelcad.br/mcp --header "Authorization: Bearer секрет"
docker compose -f compose/stack.yml --env-file compose/.env up -d   # сервер + изолированный воркер
```

Граф связей (M2.2, D27): сервер держит в Postgres производный индекс сущностей и связей всех проектов (базы,
интерфейсы, обстановка, узлы, детали, отверстия, крепёж, материалы, позиции каталога, размеры, замечания),
пересобираемый по коммитам и сборкам — поиск по всем проектам и блок «Связи» в рабочем месте, инструменты
`links` / `where_used` / `search` у агента. `SKELCAD_DATABASE_URL=postgresql://…` (в compose — сервис `db`,
пароль создаёт деплой); для разработки и тестов `SKELCAD_DATABASE_URL=embedded` поднимает встроенный Postgres
(`pgserver`) в `<data>/pg`. Индекс одноразовый: `POST /api/graph/reindex` пересобирает его из git.

Рабочее место в браузере (M2): экраны Проекты, Вариант (3D), Лента, Сравнение, Параметры, Агент, Подключение агента;
папка `web/` (Vite + React + TypeScript, three.js). Разработка:
`cd web && npm ci && npm run dev` — прокси на локальный `skelcad serve` (`SKELCAD_BACKEND`, по умолчанию
`http://127.0.0.1:8000`); сборка `npm run build` кладёт статику в `src/skelcad/server/static/`, сервер отдаёт её
по `/`. В образе это делает Dockerfile. Вход для браузера — `SKELCAD_AUTH=none|tokens|proxy` (см. `server/auth.py`).

Встроенный агент (задачи из workbench, контейнер `agent`): `skelcad agent --queue /data/tasks`. Провайдер модели —
любой с OpenAI-совместимым Chat Completions API: `SKELCAD_LLM_BASE_URL`, `SKELCAD_LLM_API_KEY`, `SKELCAD_LLM_MODEL`
(в compose — `LLM_BASE_URL`, `LLM_MODEL`, ключ в секрете `SKELCAD_LLM_API_KEY`); исполнитель
`SKELCAD_AGENT_RUNNER=claude-code` запускает headless Claude Code, если команда `claude` есть на машине.
Инструменты агент берёт из `/mcp` сервера с токеном `SKELCAD_AGENT_TOKEN` (клиент «workbench-agent»).
Вложения конструктора (набросок от руки, фото, экспорт доски; D28) хранятся в `attachments/` репозитория проекта
коммитом конструктора, прикладываются к задаче и уходят модели как изображения; агент смотрит их инструментом
`attachment`. Компоновку конструктор правит прямо на эскизе («Править»: ручки, точные числа, размер числом) —
каждое «Применить» — его коммит в `project.yaml` (D22).

Как агенту работать с проектом через MCP — [AGENTS.md](AGENTS.md).
Устройство репозитория и план этапа — в [docs/architecture/03-m0-plan.md](docs/architecture/03-m0-plan.md).
Проект для SkelCAD — папка с `project.yaml` (требования, скелет, пакеты стандартов, генератор, плагины)
и `variants/*.yaml` (параметры топологий); см. [examples/bracket](examples/bracket) (кронштейн на стене)
и [examples/pipe_support](examples/pipe_support) (опора под трубу на полу).
JSON Schema спецификации проекта, варианта и разрешённой модели — в [docs/schema](docs/schema).

## Документы

| Файл | Что это |
|---|---|
| [docs/architecture/01-vision-and-architecture.md](docs/architecture/01-vision-and-architecture.md) | Замысел, принципы, архитектура (C4), проектная модель, режимы выдачи, дорожная карта, риски |
| [docs/architecture/02-decisions.md](docs/architecture/02-decisions.md) | Журнал решений D1–D21: принятые, обсуждаемые, отложенные |
| [docs/architecture/03-m0-plan.md](docs/architecture/03-m0-plan.md) | План этапа M0: устройство репозитория, что переезжает из пилота, шаги и статус |
| [docs/architecture/05-m2-plan.md](docs/architecture/05-m2-plan.md) | План этапа M2: workbench в браузере, принципы интерфейса (ISO 9241-110, чеклист Нильсена), вход, задача агенту |
| [docs/architecture/06-m2-1-sketches-plan.md](docs/architecture/06-m2-1-sketches-plan.md) | План этапа M2.1 (закрыт): компоновочный эскиз по скелету и обстановке для согласования, эскизы с размерами по модели, сравнение вариантов в одном масштабе и наложением |
| [docs/architecture/07-m2-2-graph-plan.md](docs/architecture/07-m2-2-graph-plan.md) | План этапа M2.2 (закрыт): граф связей в Postgres — производный индекс сущностей и связей, поиск по всем проектам, блок «Связи», инструменты агента; дорожная карта M2.3–M4 (ввод компоновки, PMI и виды, дерево компоновок, мост к САПР) |
| [docs/architecture/08-m2-3-layout-input-plan.md](docs/architecture/08-m2-3-layout-input-plan.md) | План этапа M2.3 (закрыт): ввод компоновки от конструктора — набросок к задаче агенту и инструмент `attachment`, правка компоновки на эскизе ручками и числами с коммитом конструктора, росчерки пометок, пилот «набросок → скелет» |
| [docs/ui/checklist.md](docs/ui/checklist.md) | Чеклист ревью интерфейса; ревью экранов — `docs/ui/reviews/` |
| [docs/guide-workbench.md](docs/guide-workbench.md) | Руководство конструктора: рабочее место в браузере без терминала и git |
| [docs/architecture/04-m1-plan.md](docs/architecture/04-m1-plan.md) | План этапа M1: сервер с точкой MCP, изменения агента как коммиты, воркер с лимитами, diff, сценарий приёмки |
| [docs/architecture/c4.png](docs/architecture/c4.png) | C4-схема: контекст и контейнеры |
| [docs/research/reports/](docs/research/reports/) | Обзор мира: open source и коммерческие инструменты, бенчмарки, форматы обмена, пакеты стандартов, UX, дистрибуция |
| [docs/research/research_notes/](docs/research/research_notes/) | Исходные заметки исследования со ссылками |

## Принятые решения

- Название SkelCAD, лицензия Apache-2.0.
- Рабочее место — web-приложение в браузере; ядро — сервер. Self-hosted образ (`docker compose`)
  первым, публичная площадка как экземпляр того же образа, настольный вариант позже по спросу.
- У инженера на машине — только мост к его САПР, и только для передачи в САПР.
- Стандарты (ГОСТ, ISO, DIN, ASME, корпоративные) — подключаемые пакеты, в ядре ни одной таблицы.
- Агент работает через точку MCP сервера; его изменения — коммиты в git проекта; код проектов
  исполняется в изолированном воркере (решения D11–D13 в журнале).
- Система записи — git с YAML; граф связей — производный индекс в Postgres, одноразовый и пересобираемый
  (D27). Компоновка редактируется через виды, PMI — сущности модели с видами, узел дерева изделия — проект с
  распределением вниз и сводкой вверх (D22–D26).

## Происхождение

Обобщение пилота «сварной кронштейн» (build123d: модель → геометрия → правила, проверки,
расчёт → STEP + рецепт → сравнение вариантов) и опыта собственных MCP-серверов для SolidWorks
и AutoCAD на Python/COM.

## Лицензия

Apache License 2.0, см. [LICENSE](LICENSE).
