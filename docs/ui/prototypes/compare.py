"""Сводная страница сравнения макетов: python3 compare.py → index.html (по results.json, variants.json, picks.json)."""

import json
from html import escape
from pathlib import Path

DIR = Path(__file__).parent
variants = json.loads((DIR / "variants.json").read_text(encoding="utf-8"))
results = json.loads((DIR / "results.json").read_text(encoding="utf-8"))
picks = json.loads((DIR / "picks.json").read_text(encoding="utf-8")) if (DIR / "picks.json").exists() else {"top": [], "notes": {}}
SHOTS_DEFAULT = ["папка", "агент за работой", "детали готовы", "выбор варианта", "новый проект: компоновка"]

rows, cards = [], []
for v in variants:
    r = results.get(v["file"])
    if not r:
        continue
    key = v["file"][:3]
    top = key in picks["top"]
    n = len(r["scenarios"])
    rows.append(
        f'<tr class="{"top" if top else ""}"><td><a href="{v["file"]}" target="_blank">{escape(r["name"])}</a>'
        f'{" <span class=pick>выбран</span>" if top else ""}{" <span class=muted>(сценарии по узлам)</span>" if v.get("scenarios") == "nodes" else ""}</td>'
        f'<td class="n {"ok" if r["pass"] == n else "bad"}">{r["pass"]} / {n}</td><td class="n">{r["actions"]}</td>'
        f'<td class="n">{r["controls"]["visible"]} / {r["controls"]["total"]}</td><td class="n">{len(r["errors"])}</td>'
        f'<td>{escape("; ".join(s["title"] for s in r["scenarios"] if not s["ok"]) or "—")}</td></tr>'
    )
    shots = "".join(
        f'<a href="shots/{key}-{v["file"][4:-5]}-{s}.png" target="_blank" title="{t}"><img src="shots/{key}-{v["file"][4:-5]}-{s}.png" alt="{t}"><span>{t}</span></a>'
        for s, t in enumerate(v.get("shots", SHOTS_DEFAULT))
        if (DIR / "shots" / f"{key}-{v['file'][4:-5]}-{s}.png").exists()
    )
    per = "".join(f'<span class="sc {"" if s["ok"] else "bad"}" title="{escape(s["title"])}">{s["actions"]}</span>' for s in r["scenarios"])
    note = picks["notes"].get(key, "")
    cards.append(
        f'<section class="v {"top" if top else ""}" id="{key}"><h3><a href="{v["file"]}" target="_blank">{escape(r["name"])}</a>'
        f'{" <span class=pick>выбран</span>" if top else ""}</h3><p class="idea">{escape(v["idea"])}</p>'
        f'<p class="pm"><b>+</b> {escape(v["plus"])}<br><b>−</b> {escape(v["minus"])}</p>'
        f'<div class="shots">{shots}</div>'
        f'<div class="meta"><span>действий по сценариям:</span><span class="per">{per}</span><span>всего {r["actions"]}</span></div>'
        f'{f"<p class=note>{escape(note)}</p>" if note else ""}</section>'
    )

scen = results[variants[0]["file"]]["scenarios"] if variants and variants[0]["file"] in results else []
scen_nodes = next((results[x["file"]]["scenarios"] for x in variants if x.get("scenarios") == "nodes" and x["file"] in results), [])
scen_nodes_html = ('<p class="muted">Изделие из узлов и разговор (05):</p><ol class="sc">' + "".join(f"<li>{escape(s['title'])}</li>" for s in scen_nodes) + "</ol>") if scen_nodes else ""
html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Макеты рабочего места SkelCAD</title>
<style>
body {{ margin: 0; padding: 24px 20px 60px; font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #1b1f24; background: #f3f4f6; }}
.wrap {{ max-width: 1240px; margin: 0 auto; }}
h1 {{ font-size: 26px; margin: 0 0 6px; }} h2 {{ font-size: 19px; margin: 30px 0 10px; }} h3 {{ font-size: 16px; margin: 0 0 4px; }}
a {{ color: #1f5fbf; }} .muted {{ color: #5b6470; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; border: 1px solid #dde2e8; border-radius: 8px; font-size: 13px; }}
th, td {{ padding: 7px 10px; border-top: 1px solid #dde2e8; text-align: left; vertical-align: top; }} th {{ background: #f8f9fb; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #5b6470; border-top: 0; }}
td.n {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }} .ok {{ color: #1b7f3b; }} .bad {{ color: #b42318; font-weight: 600; }}
tr.top td {{ background: #eaf1fb; }}
.pick {{ display: inline-block; margin-left: 6px; padding: 0 8px; border-radius: 999px; background: #1f5fbf; color: #fff; font-size: 11px; vertical-align: middle; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(560px, 1fr)); gap: 16px; }}
.v {{ background: #fff; border: 1px solid #dde2e8; border-radius: 10px; padding: 14px 16px; }} .v.top {{ border-color: #1f5fbf; box-shadow: 0 0 0 1px #1f5fbf; }}
.idea {{ margin: 0 0 6px; }} .pm {{ margin: 0 0 10px; color: #5b6470; font-size: 13px; }} .pm b {{ color: #1b1f24; display: inline-block; width: 12px; }}
.shots {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }} .shots a {{ display: flex; flex-direction: column; gap: 3px; font-size: 11px; color: #5b6470; text-decoration: none; text-align: center; }}
.shots img {{ width: 100%; aspect-ratio: 16 / 10; object-fit: cover; object-position: top; border: 1px solid #dde2e8; border-radius: 4px; background: #fff; }}
.meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; margin: 10px 0 4px; font-size: 12px; color: #5b6470; }}
.per {{ display: flex; gap: 3px; flex-wrap: wrap; }} .sc {{ display: inline-block; min-width: 22px; text-align: center; padding: 0 4px; border-radius: 4px; font-size: 11px; background: #e8f4ec; color: #1b7f3b; }} .sc.bad {{ background: #fcebe9; color: #b42318; }}
.note {{ margin: 8px 0 0; padding: 8px 10px; border-radius: 6px; background: #fbf3e4; color: #9a5b00; font-size: 13px; }}
.stages {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0; }} .stages div {{ background: #fff; border: 1px solid #dde2e8; border-radius: 8px; padding: 10px 12px; font-size: 13px; }} .stages b {{ display: block; margin-bottom: 4px; }}
ol.sc {{ columns: 2; margin: 6px 0; }} .rule {{ padding: 10px 12px; border-left: 3px solid #1f5fbf; background: #fff; margin: 8px 0; }}
</style></head><body><div class="wrap">
<h1>Рабочее место SkelCAD: пять макетов сквозного сценария</h1>
<p class="muted">После первого сравнения конструктор выбрал направление «Рабочий стол» (03) и уточнил: слева нужна навигация по узлам одного изделия, а не по проектам; справа — единое место общения с агентом. Это сделано в макете 05 «Узлы и разговор» на изделии из нескольких узлов (насосный агрегат на раме).</p>
<p class="muted">Повод — замечание конструктора после проекта «Болт обычный М16»: интерфейс перегружен, главная страница должна быть деревом папок с названиями проектов, непонятно, что делать после согласования компоновки, нужно больше графики и меньше текста. Макеты собраны с чистого листа на одной модели данных: проекты, которые сейчас лежат на сервере (болт, специальный болт), и примеры (кронштейн, опора, планка). Каждый макет прогнан одним и тем же набором из {len(scen)} сценариев конструктора: действия считает Playwright (щелчок, клавиша = 1; ввод текста = 2). Открыть макет — щелчок по названию; всё работает локально, без сервера.</p>

<h2>Сквозной сценарий, общий для всех макетов</h2>
<div class="stages">
<div><b>1. Задание</b>Что нужно: назначение, нагрузки, к чему крепится; набросок или фото. Пишет конструктор.</div>
<div><b>2. Компоновка</b>Скелет и обстановка по заданию — делает агент, показывает эскиз. Конструктор согласует или правит на эскизе.</div>
<div><b>3. Конструкция</b>Детали, варианты, проверки: масса, запас K, замечания — делает агент. Конструктор сравнивает и выбирает вариант.</div>
<div><b>4. Комплект</b>STEP, эскизы с размерами, спецификация, отчёт — собирает агент по выбранному варианту. Конструктор скачивает.</div>
</div>
<div class="rule">У проекта всегда один следующий шаг, и он написан словами: «Поручить агенту детали», «Согласовать компоновку», «Выбрать вариант», «Выдать комплект». Янтарным — когда решение за конструктором, синим — когда ход у агента. Та же короткая строка стоит у проекта в дереве. Ход работы агента — фразами и картинками, на которые он смотрел; сырое — свёрнуто.</div>

<h2>Сводка</h2>
<table><tr><th>Макет</th><th>Сценарии</th><th>Действий</th><th>Контролов видно / всего</th><th>Ошибок JS</th><th>Не прошло</th></tr>{"".join(rows)}</table>
<p class="muted">Число действий одинаково там, где сценарий сводится к одному щелчку по «следующему шагу»; разница появляется на обзоре папки и на доступе к дереву.</p>

<h2>Макеты</h2>
<div class="grid">{"".join(cards)}</div>

<h2>Сценарии прогона</h2>
<p class="muted">Папки и проекты (01–04):</p>
<ol class="sc">{"".join(f"<li>{escape(s['title'])}</li>" for s in scen)}</ol>
{scen_nodes_html}
<p class="muted">Скрипт: <code>node run.mjs</code> (Playwright из <code>web/node_modules</code>) → <code>results.json</code> и <code>shots/</code>; затем <code>python3 compare.py</code> → эта страница.</p>
</div></body></html>"""
(DIR / "index.html").write_text(html, encoding="utf-8")
print("index.html:", len(html), "bytes")
