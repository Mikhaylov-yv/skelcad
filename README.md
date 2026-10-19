# SkelCAD

**Среда совместного конструирования «ИИ-агент + инженер-конструктор», сверху вниз.**
Open source, Apache-2.0. Стадия: M0 (обобщение пилота) закрыт 16.10.2026; M1 (агентный контур:
сервер с точкой MCP, проекты в git, изолированный воркер, измерения, рендер, diff) закрыт 19.10.2026,
см. [docs/architecture/04-m1-plan.md](docs/architecture/04-m1-plan.md). Следующий этап — M2,
рабочее место конструктора в браузере.

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
SKELCAD_TOKENS="claude-code:секрет" uv run skelcad serve
claude mcp add --transport http skelcad https://skelcad.br/mcp --header "Authorization: Bearer секрет"
docker compose -f compose/stack.yml --env-file compose/.env up -d   # сервер + изолированный воркер
```

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
| [docs/architecture/02-decisions.md](docs/architecture/02-decisions.md) | Журнал решений D1–D10: принятые, обсуждаемые, отложенные |
| [docs/architecture/03-m0-plan.md](docs/architecture/03-m0-plan.md) | План этапа M0: устройство репозитория, что переезжает из пилота, шаги и статус |
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

## Происхождение

Обобщение пилота «сварной кронштейн» (build123d: модель → геометрия → правила, проверки,
расчёт → STEP + рецепт → сравнение вариантов) и опыта собственных MCP-серверов для SolidWorks
и AutoCAD на Python/COM.

## Лицензия

Apache License 2.0, см. [LICENSE](LICENSE).
