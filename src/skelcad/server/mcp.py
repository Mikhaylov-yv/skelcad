"""Точка MCP: регистрация инструментов в SDK (тонкий слой над `tools.Tools`).

Имя клиента (по токену) кладёт в контекст middleware приложения; оно становится автором коммитов.
"""

from __future__ import annotations

import base64
from contextvars import ContextVar
from functools import partial

from anyio import to_thread
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.transport_security import TransportSecuritySettings

from skelcad.server.tools import Server, Tools

CURRENT_CLIENT: ContextVar[str] = ContextVar("skelcad_client", default="anonymous")

INSTRUCTIONS = """SkelCAD — среда конструирования «агент + инженер», сверху вниз: модель изделия (YAML + генератор на
Python) — источник истины, геометрия и чертежи — производные. Ты предлагаешь и строишь, конструктор решает.

Проекты живут на сервере (project_list). Проект — папка: project.yaml (требования, скелет, пакеты стандартов,
генератор, плагины, параметры), variants/*.yaml (параметры топологий), generators/*.py, plugins/*.py.
Любое изменение — files_write с осмысленным сообщением: один вызов = один коммит в git под твоим именем.
Конструктор видит историю (history) и откатывает лишнее; тупиковый шаг отменяй сам (revert).

Цикл: project_read → (скелет и обстановка → render(layout=True) → согласование конструктором) → check/build →
measure/context_search → files_write → build → diff → … → compare. Компоновку (skeleton: datums, interfaces,
envelopes, surroundings; requirements) конструктор согласовывает в рабочем месте; её состояние — в project_read.
Сводка — первая строка ответа; большие данные запрашивай срезами (model_query path=...).
Связи между сущностями — индекс в базе: links (окрестность сущности), where_used (где используется, по всем
проектам), search (поиск по всем проектам). Бери окрестность, а не весь YAML.
Вложения конструктора (набросок от руки, фото, экспорт доски) — в project_read → attachments; смотри их
инструментом attachment(project, path). Набросок переводи в скелет и обстановку: опорное (стена, пол, труба,
ответная деталь) — surroundings и datums, где изделие крепится и что несёт — interfaces и нагрузки, подписанные
числа — размеры, неподписанное оцени по пропорциям и запиши в assumptions; покажи render(layout=True) и жди
согласования.
Единицы: мм, кН, кг. Замечания уровня error блокируют приёмку — не оставляй их.
"""


def build_mcp(srv: Server) -> FastMCP:
    t = Tools(srv)
    mcp = FastMCP(
        "skelcad",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/mcp",
        max_request_body_size=8 * 1024 * 1024,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    async def run(fn, *a, **kw):
        return await to_thread.run_sync(partial(fn, *a, **kw))

    def client() -> str:
        return CURRENT_CLIENT.get()

    # ---------------- проекты
    @mcp.tool()
    async def project_list() -> dict:
        """Проекты на сервере: имя, название, варианты, последний коммит; доступные шаблоны."""
        return await run(t.project_list)

    @mcp.tool()
    async def project_create(name: str, template: str | None = None, origin: str | None = None) -> dict:
        """Создать проект (git-репозиторий) из шаблона (см. project_list.templates) или пустой (template=empty).
        name — строчные латинские буквы, цифры, «-», «_». origin — адрес удалённого git-репозитория
        (пустой репозиторий, ветка main): сервер будет пушить туда каждый коммит и подтягивать правки конструктора."""
        return await run(t.project_create, name, template, client(), origin)

    @mcp.tool()
    async def project_read(project: str, section: str | None = None) -> dict:
        """Спецификация проекта (project.yaml), список вариантов, файлов и вложений конструктора (attachments —
        смотри инструментом attachment). section: requirements | skeleton | params | assumptions | variants |
        standards | generator | plugins — вернуть только этот раздел."""
        return await run(t.project_read, project, section)

    @mcp.tool()
    async def review_list(project: str, status: str | None = "open") -> dict:
        """Замечания конструктора агенту из review.yaml (пометки на модели: деталь, точка в мм, текст; росчерк
        на компоновочном эскизе: вид и точки в мм — место обведено или показано стрелкой, смотри его на
        render(layout=True, view=<вид росчерка>)). status: open (по умолчанию) | resolved | all. Открытые
        замечания — часть задачи: ответь на каждое через review_resolve после того, как учёл его (или объясни,
        почему не учитываешь)."""
        return await run(t.review_list, project, status)

    @mcp.tool()
    async def review_resolve(project: str, id: str, answer: str) -> dict:
        """Закрыть замечание конструктора ответом (коммит «ответ на R1: …»). answer — что сделано или почему нет."""
        return await run(t.review_resolve, project, id, answer, client())

    @mcp.tool()
    async def model_query(project: str, variant: str | None = None, path: str | None = None) -> dict:
        """Разрешённая модель варианта (после генератора) — срезами. Без path: сводка (узлы, детали, derived).
        path: parts | parts[id=base_plate] | parts[role=rib] | welds | fasteners | units[0].parts |
        skeleton.interfaces | requirements | assumptions | derived.
        Списки можно индексировать [0] и фильтровать [ключ=значение]."""
        return await run(t.model_query, project, variant, path)

    # ---------------- файлы и история
    @mcp.tool()
    async def files_read(project: str, path: str) -> dict:
        """Содержимое файла проекта: project.yaml, variants/<v>.yaml, generators/<g>.py, plugins/<p>.py."""
        return await run(t.files_read, project, path)

    @mcp.tool()
    async def files_write(project: str, files: dict[str, str | None], message: str) -> dict:
        """Записать файлы проекта и закоммитить одним коммитом. files: {путь: содержимое}, None — удалить файл.
        message — что и зачем изменено (как сообщение коммита). Один вызов = одно логическое изменение."""
        return await run(t.files_write, project, files, message, client())

    @mcp.tool()
    async def history(project: str, limit: int = 20, path: str | None = None) -> dict:
        """История коммитов проекта: кто, когда, что менял. path — только по файлу."""
        return await run(t.history, project, limit, path)

    @mcp.tool()
    async def revert(project: str, commit: str, message: str | None = None) -> dict:
        """Отменить коммит (git revert) новым коммитом. Для тупиковых шагов; историю не переписывает."""
        return await run(t.revert, project, commit, message, client())

    # ---------------- контекст
    @mcp.tool()
    async def standards_list() -> dict:
        """Установленные пакеты стандартов и их таблицы."""
        return await run(t.standards_list)

    @mcp.tool()
    async def context_tables(project: str) -> dict:
        """Таблицы контекста проекта (пакеты стандартов + локальные): ключи и поля."""
        return await run(t.context_tables, project)

    @mcp.tool()
    async def context_lookup(project: str, table: str, key: str) -> dict:
        """Запись таблицы: materials[St3sp], fasteners[M16], anchors[M16], tubes…"""
        return await run(t.context_lookup, project, table, key)

    @mcp.tool()
    async def context_search(project: str, query: str, table: str | None = None) -> dict:
        """Поиск по ключам и полям таблиц контекста (подстрока): «M20», «76x», «С245»."""
        return await run(t.context_search, project, query, table)

    # ---------------- сборка и проверки
    @mcp.tool()
    async def build(project: str, variant: str | None = None, export: bool = True) -> dict:
        """Построить вариант(ы): модель → геометрия → правила/проверки/расчёт → артефакты (STEP, glTF, SVG,
        report.json) и ссылки на них. Без variant — все варианты. Сводка: масса, габарит, K_min, замечания.
        export=False — быстрее, но 3D/STEP/SVG не обновляются (в отчёте остаются ссылки прошлой сборки);
        перед отчётом конструктору собирай с export=True, иначе он увидит в workbench старую геометрию."""
        return await run(t.build, project, variant, export)

    @mcp.tool()
    async def check(project: str, variant: str | None = None, scope: str = "all", all: bool = False) -> dict:  # noqa: A002
        """Правила, проверки геометрии и расчёт без экспорта. scope: all | rules (над моделью) |
        geometry (пересечения, контакт, тела интерфейсов) | calc (расчётные позиции). all=True — и info."""
        return await run(t.check, project, variant, scope, all)

    @mcp.tool()
    async def compare(project: str, variants: list[str] | None = None, rebuild: bool = False) -> dict:
        """Сравнить варианты по метрикам (масса, швы, K_min, метрики проекта); страница compare.html.
        Берёт готовые отчёты сборки, недостающие строит; rebuild=True — перестроить все."""
        return await run(t.compare, project, variants, rebuild)

    @mcp.tool()
    async def diff(project: str, variant: str, a: str = "HEAD~1", b: str = "HEAD") -> dict:
        """Что изменилось между двумя коммитами в варианте: сущности модели по id (добавлено/удалено/изменённые
        поля), геометрия деталей (объём, добавлено/убрано мм³, смещение центроида), сводка (масса, габарит,
        швы, K по позициям), появившиеся и ушедшие замечания. a, b — хеши из history или HEAD~N."""
        return await run(t.diff, project, variant, a, b)

    # ---------------- измерения и виды
    @mcp.tool()
    async def measure(project: str, variant: str, op: str, args: dict | None = None) -> dict:
        """Измерить на геометрии варианта. op и args:
        list — какие тела есть; mass {a?} — масса деталей (кг); cog {a?} — центр тяжести;
        bbox {a?} — габарит (мм); distance / clearance {a, b} — расстояние между телами и ближайшие точки;
        interference {a, b} — объём пересечения (мм³);
        section {a?, origin:[x,y,z], normal:[nx,ny,nz]} — площадь сечения;
        part {a} — сводка по детали (объём, масса, ЦТ, габарит, модель).
        Ссылки a/b: part:<id> | fastener:<id> | body:<id> | assembly | assembly+ (с крепежом и телами)."""
        return await run(t.measure, project, variant, op, args)

    @mcp.tool()
    async def render(
        project: str,
        variant: str | None = None,
        view: str = "iso",
        highlight: str | None = None,
        layout: bool = False,
        sketch: bool = False,
    ) -> list:
        """Посмотреть вариант глазами: PNG-проекция (видимые и скрытые линии). view: iso | main | left | top.
        highlight — подсветить тело красным (part:<id>, fastener:<id>, body:<id>). Файлы SVG/PNG — по ссылкам.
        layout=True — компоновочный эскиз (view: main | left | top): базы и интерфейсы скелета, зоны, обстановка
        (skeleton.surroundings), нагрузки стрелками, размеры положений; детали варианта тонкой линией, если
        генератор работает. Строится по project.yaml без сборки — смотри его, когда описал скелет и обстановку,
        и перед тем, как просить конструктора согласовать компоновку (состояние — в project_read → layout).
        sketch=True — эскиз варианта с размерами по модели (view: main | left | top): габариты, толщины «s»,
        шаги и диаметры отверстий, трубы, крепёж, положения скелета. Размеры возвращаются и текстом — проверяй
        по ним свою работу перед отчётом конструктору; лишние размеры скрывай через раздел sketch.hide варианта."""
        if layout:
            res = await run(t.render_layout, project, variant, "main" if view == "iso" else view)
        elif sketch:
            if not variant:
                raise ValueError("укажите variant")
            res = await run(t.render_sketch, project, variant, "main" if view == "iso" else view)
        else:
            if not variant:
                raise ValueError("укажите variant")
            res = await run(t.render, project, variant, view, highlight)
        out: list = [res["summary"]]
        if res.get("png_base64"):
            out.append(Image(data=base64.b64decode(res["png_base64"]), format="png"))
        elif res.get("svg_text"):
            out.append(res["svg_text"][:20000])
        return out

    # ---------------- вложения конструктора (M2.3, D28)
    @mcp.tool()
    async def attachment(project: str, path: str) -> list:
        """Вложение конструктора из attachments/ проекта (список — project_read → attachments): набросок от руки,
        фото, экспорт доски. png / jpg / webp — как изображение; svg и первая страница pdf — растром; .excalidraw —
        сводка элементов текстом (сам JSON — files_read). Набросок — исходный документ компоновки: по нему опиши
        скелет и обстановку в project.yaml, покажи render(layout=True) и дождись согласования конструктора."""
        res = await run(t.attachment, project, path)
        out: list = [res["summary"]]
        if res.get("png_base64"):
            out.append(Image(data=base64.b64decode(res["png_base64"]), format=res.get("format") or "png"))
        return out

    # ---------------- граф связей (M2.2, D27)
    @mcp.tool()
    async def links(
        project: str,
        ref: str,
        variant: str | None = None,
        hops: int = 1,
        kinds: list[str] | None = None,
        direction: str = "both",
    ) -> dict:
        """Связи сущности по индексу: окрестность на hops шагов (1–4). ref — kind:id[/kind:id]: interface:wall,
        datum:axle_axis, part:base_plate/hole:a00, unit:u1, load:Fv, item:anchor/M16, material:St3sp.
        direction: out — что сущность содержит и на что ссылается; in — кто ссылается на неё; both — всё.
        kinds — типы связей: contains, locates, mounts, applies, joins, fastens, made_of, selects, uses, annotates,
        checks, reviews, computes. variant — ограничить уровень варианта одним вариантом (уровень проекта виден
        всегда). Сводка — текстом; nodes / edges — данными. Дешевле, чем читать YAML целиком."""
        return await run(t.links, project, ref, variant, hops, kinds, direction)

    @mcp.tool()
    async def where_used(ref: str, project: str | None = None) -> dict:
        """Где используется сущность: по всем проектам (project не задан) или в одном. Примеры: item:anchor/M16,
        material:St3sp, standard:gost, interface:wall, datum:wall. Ответ: кто ссылается и каким типом связи."""
        return await run(t.where_used, ref, project)

    @mcp.tool()
    async def search(query: str, project: str | None = None, kind: str | None = None, limit: int = 50) -> dict:
        """Поиск сущностей по всем проектам по подстроке в id, имени, роли, примечании, тегах («M16», «стена»,
        «cheek»). kind — вид: project, variant, datum, interface, envelope, surrounding, load, constraint, unit,
        part, hole, weld, fastener, material, item, dim, finding, calc, review, assumption, standard, metric."""
        return await run(t.search, query, project, kind, limit)

    return mcp
