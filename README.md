# SkelCAD

**Среда совместного конструирования «ИИ-агент + инженер-конструктор», сверху вниз.**
Open source, Apache-2.0. Стадия: проектирование (октябрь 2026), кода ещё нет.

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

## Документы

| Файл | Что это |
|---|---|
| [docs/architecture/01-vision-and-architecture.md](docs/architecture/01-vision-and-architecture.md) | Замысел, принципы, архитектура (C4), проектная модель, режимы выдачи, дорожная карта, риски |
| [docs/architecture/02-decisions.md](docs/architecture/02-decisions.md) | Журнал решений D1–D10: принятые, обсуждаемые, отложенные |
| [docs/architecture/c4.png](docs/architecture/c4.png) | C4-схема: контекст и контейнеры |
| [docs/research/reports/](docs/research/reports/) | Обзор мира: open source и коммерческие инструменты, бенчмарки, форматы обмена, пакеты стандартов, UX, дистрибуция |
| [docs/research/research_notes/](docs/research/research_notes/) | Исходные заметки исследования со ссылками |

## Принятые решения

- Название SkelCAD, лицензия Apache-2.0.
- Рабочее место — web-приложение в браузере; ядро — сервер. Self-hosted образ (`docker compose`)
  первым, публичная площадка как экземпляр того же образа, настольный вариант позже по спросу.
- У инженера на машине — только мост к его САПР, и только для передачи в САПР.
- Стандарты (ГОСТ, ISO, DIN, ASME, корпоративные) — подключаемые пакеты, в ядре ни одной таблицы.

## Происхождение

Обобщение пилота «сварной кронштейн» (build123d: модель → геометрия → правила, проверки,
расчёт → STEP + рецепт → сравнение вариантов) и опыта собственных MCP-серверов для SolidWorks
и AutoCAD на Python/COM.

## Лицензия

Apache License 2.0, см. [LICENSE](LICENSE).
