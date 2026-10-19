# Приёмка 1: bracket

Начинаю: загружу инструменты skelcad, прочитаю проект и проверю вариант A_fork.

**1. `ToolSearch`** `{"query": "select:mcp__skelcad__project_read,mcp__skelcad__check,mcp__skelcad__files_read,mcp__skelcad__files_write,mcp__skelcad__build,mcp__skelcad__diff,mcp__skelcad__compare,mcp__skelcad__context_search,mcp__skelcad__context_lookup,mcp__skelcad__measure,mcp__skelcad__render,mcp__skelcad__revert,mcp__skelcad__history,mcp__skelcad__model_query,mcp__skelcad__context_tables", "max_results": 15}`

> 

**2. `project_read`** `{"project": "bracket"}`

> bracket: «Сварной кронштейн под ось Ø50», варианты: A_fork, B_hub, C_box

**3. `check`** `{"project": "bracket", "variant": "A_fork", "all": true}`

**4. `files_read`** `{"project": "bracket", "path": "variants/A_fork.yaml"}`

**5. `files_read`** `{"project": "bracket", "path": "project.yaml"}`

**6. `context_tables`** `{"project": "bracket"}`

**7. `history`** `{"project": "bracket", "limit": 10}`

> A_fork: ошибка 0, предупреждение 3, информация 27; K_min 1.14 (Анкер: совместное действие N и V, треб. 1.5)

> bracket/variants/A_fork.yaml: 13 строк

> bracket/project.yaml: 55 строк

> таблицы: welds (7), tubes (2), sheet (2), fasteners (3), anchors (3), fits (3), materials (2)

> 34e9c92 2026-10-19T09:59 SkelCAD: Проект bracket из шаблона bracket

**8. `context_lookup`** `{"project": "bracket", "table": "anchors", "key": "M16"}`

> anchors[M16]

**9. `context_lookup`** `{"project": "bracket", "table": "anchors", "key": "M20"}`

> anchors[M20]

**10. `context_lookup`** `{"project": "bracket", "table": "fasteners", "key": "M20"}`

> fasteners[M20]

**11. `context_lookup`** `{"project": "bracket", "table": "fasteners", "key": "M16"}`

> fasteners[M16]

**12. `files_read`** `{"project": "bracket", "path": "plugins/calc.py"}`

> bracket/plugins/calc.py: 250 строк

**13. `files_read`** `{"project": "bracket", "path": "generators/bracket.py"}`

> bracket/generators/bracket.py: 601 строк

**14. `build`** `{"project": "bracket", "variant": "A_fork"}`

> A_fork: масса 15.33 кг, габарит 270×250×290 мм, деталей 3, швы 848 мм, K_min 1.14 (Анкер: совместное действие N и V); замечания: ошибка 0, предупреждение 3, информация 27

**15. `check`** `{"project": "bracket", "scope": "calc"}`

**16. `context_lookup`** `{"project": "bracket", "table": "materials", "key": "St3sp"}`

> A_fork: ошибка 0, предупреждение 1, информация 7; K_min 1.14 (Анкер: совместное действие N и V, треб. 1.5) ⏎ B_hub: ошибка 0, предупреждение 1, информация 6; K_min 1.14 (Анкер: совместное действие N и V, треб. 1.5) ⏎ C_box: ошибка 0, предупреждение 1, информация 6; K_min 1.14 (Анкер: совместное действие N и V, треб. 1.5)

> materials[St3sp]

**17. `files_write`** `{"project": "bracket", "files": {"project.yaml": "# Пилот SkelCAD: сварной кронштейн под ось Ø50 на бетонной стене (пара кронштейнов).\nid: bracket\ntitle: \"Сварной кронштейн под ось Ø50\"\ndescription: >\n  Опорная плита на химических анкерах и несущие элементы, через которые проходит ось.\n  Три топологии (вилка / ступица / коробка) сравниваются по массе, швам и запасу K.\nlang: ru\ncoordinate_…`

> коммит 7bac9b6 «Анкеры M16 → M20: запас по совместному действию N+V был 1.14 < 1.5 во всех вариантах»: project.yaml

**18. `build`** `{"project": "bracket", "variant": "A_fork"}`

**19. `diff`** `{"project": "bracket", "variant": "A_fork", "a": "HEAD~1", "b": "HEAD"}`

> A_fork: масса 15.63 кг, габарит 280×250×290 мм, деталей 3, швы 848 мм, K_min 1.54 (Опорная плита: изгиб у анкера); замечания: ошибка 0, предупреждение 2, информация 28

> bracket/A_fork: 34e9c92 → 7bac9b6 ⏎ parts: изменено base_plate (holes, name, outline) ⏎ fasteners: изменено anchor_a00 (position, size), anchor_a01 (position, size), anchor_a10 (position, size), anchor_a11 (position, size) ⏎ assumptions: изменено G8 (text) ⏎ interfaces: изменено wall (params) ⏎ units: изменено bracket (derived) ⏎ derived: изменено анкеры по X, ±мм 90→95, опорная плита, мм 270×290×16→280×290×16 ⏎ mass_kg: 15.33 → 15.63 (+0.3) ⏎ K_min: 1.14 → 1.54 (+0.4) ⏎ габарит: [270, 250, 290]…

**20. `compare`** `{"project": "bracket", "rebuild": true}`

**21. `render`** `{"project": "bracket", "variant": "A_fork", "view": "main", "highlight": "fastener:anchor_a11"}`

> Масса изготавливаемых деталей, кг: A_fork=15.63; B_hub=14.35; C_box=18.54 (лучший: B_hub) ⏎ Габарит X×Y×Z, мм: A_fork=280×250×290; B_hub=250×238×290; C_box=270×253×290 ⏎ Число деталей: A_fork=3; B_hub=4; C_box=6 (лучший: A_fork) ⏎ Заготовки: A_fork=лист δ16 — 1 шт, лист δ12 — 2 шт; B_hub=лист δ16 — 1 шт, труба 76×14 — 1 шт, лист δ10 — 2 шт; C_box=лист δ16 — 1 шт, труба 76×14 — 1 шт, лист δ8 — 4 шт ⏎ Длина швов, мм: A_fork=848; B_hub=1166; C_box=1911 (лучший: A_fork) ⏎ Минимальный запас K: A_fork…

> bracket/A_fork: вид main, подсветка fastener:anchor_a11 — {'svg': 'https://skelcad.br/out/bracket/A_fork/views/A_fork_main_fastener-anchor_a11.svg', 'png': 'https://skelcad.br/out/bracket/A_fork/views/A_fork_main_fastener-anchor_a11.png'} [изображение] [Image: source: /home/mikhaylov_yv/.claude/projects/-tmp-claude-1000--home-mikhaylov-yv-dew-pet-projects-skelcad-e067c686-c450-440b-83b2-743017440ced-scratchpad/c3b382fa-1bed-4000-9fba-3c652de01d2f/tool-results/mcp-skelcad-blob-1792404723928-sz3qm…

**Готово: запас по анкерам A_fork поднят с 1.14 до 1.74 за один коммит, масса выросла на 0.3 кг.**

**Что менял.** Один коммит `7bac9b6` в project.yaml: размер анкера в скелете (интерфейс wall) M16 → M20 и текст допущения G8 под М20. Вариант A_fork.yaml и генератор не трогал. Откатов не было.

**Почему именно так.** Расчёт анкеров не зависит от топологии, и K_NV = 1.14 был одинаков у всех трёх вариантов. Поэтому правка на уровне проекта честнее, чем локальная для A_fork. Рост высоты щёк (height_ratio) к цели не приводит: даже при 1.3 получается лишь K ≈ 1.28, а масса растёт сильнее. Больше анкеров генератор не умеет без переписывания.

**A_fork до и после:**

| Показатель | До | После |
|---|---|---|
| K анкер N+V | 1.14 | 1.74 |
| K отрыв по бетону | 1.51 | 2.26 |
| K шпилька | 2.66 | 4.15 |
| K_min (теперь изгиб плиты у анкера) | 1.14 | 1.54 |
| Масса, кг | 15.33 | 15.63 |
| Плита, мм | 270×290×16 | 280×290×16 |

Плита стала шире на 10 мм из-за ключа Ø40 вместо Ø34. Шаг анкеров и доступ ключа проверены правилами без замечаний.

**Сравнение по всем вариантам после правки.** K_min везде 1.54. Масса: B_hub 14.35, A_fork 15.63, C_box 18.54 кг. Длина швов: A_fork 848, B_hub 1166, C_box 1911 мм. Страница сравнения: https://skelcad.br/out/bracket/compare.html

**Оставшиеся замечания по A_fork.** Два предупреждения R-WELD-ACCESS на внутренних швах щёк: щель 100×234 мм, глубина/ширина 2.3 > 2.0. Это не связано с анкерами и было до правки. Лечится либо технологически (варить до установки второй щеки или удлинённый наконечник), либо увеличением gap в варианте. Ошибок нет.

**Принятые допущения.**
- Несущая способность M20 (N_Rd 30 кН, V_Rd 24 кН, h_ef 170 мм) взята из условного каталога пилота. Перед выпуском заменить данными производителя (ETA), это уже записано в G8.
- Глубина заделки 170 мм укладывается в стену ≥ 250 мм. Край стены по-прежнему считается далёким (G7).
- Следующий лимитирующий запас K = 1.54 по изгибу плиты у анкера близок к требуемому. Если нагрузки уточнятся вверх, плиту придётся утолщать до 18 мм.

---
Итог: ходов 22, вызовов инструментов 21, время 146 с, стоимость $1.91
