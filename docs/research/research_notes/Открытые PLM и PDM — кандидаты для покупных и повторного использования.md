# Открытые PLM и PDM — кандидаты для покупных компонентов и повторного использования узлов

Дата: 2026-10-21. Контекст: вопрос конструктора к M3 (дерево компоновок, покупные компоненты, D25): «кажется,
нужна своя база с моделями и свойствами, можем использовать ранее разработанные детали и узлы; есть ли
open-source PLM/PDM, с которой можно интегрироваться?». Быстрый обзор по открытым источникам; проверить
глубже перед M3.

| Система | Что это | Состояние (по найденному) | Чем полезна SkelCAD |
|---|---|---|---|
| **OdooPLM** (OmniaSolutions) | PLM/PDM-модули для Odoo: документы, версии BOM, маршруты изменений, 3D/2D-просмотр в браузере; коннекторы к CAD (SolidWorks, Solid Edge, Inventor, AutoCAD, ThinkDesign, FreeCAD) | активно: ветка под Odoo 19, 36 модулей, LGPL-3 (у старых версий AGPL-3); серверные модули открыты, настольный CAD-клиент проприетарный; Docker-образы, «full» вариант с конвертацией STEP → 3MF/STL/PNG | item master и BOM с версиями, закупки; интеграция по XML-RPC/JSON-RPC Odoo; подходит, если у заказчика уже Odoo |
| **InvenTree** | открытая система учёта деталей и запасов: иерархия деталей, параметры (шаблоны параметров), BOM (в т. ч. наследуемые, сравнение BOM с 2026 г.), поставщики и цены, вложения, плагины | активно (MIT), REST API с OpenAPI-схемой (версии API > 330), плагины с настройками через API | «своя база с моделями и свойствами» без тяжёлой PLM: карточка покупного компонента (параметры, поставщик, цена, файлы STEP/PDF), BOM изделия из SkelCAD → InvenTree по REST |
| **DocDokuPLM** | классическая PDM/PLM: документы, детали, BOM, управление изменениями, 3D-просмотр | разработка остановилась около 2021 г. (по обзору 2026-09-30) — придётся поддерживать форк | образец функционального охвата; как зависимость — нет |
| **LibrePLM** (модули Odoo) | PLM-модули Odoo с коннекторами CAD (AutoCAD, Inventor, SolidWorks, Solid Edge, NX, ThinkDesign), инженерный BOM из сборки, сравнение BOM | в каталоге apps.odoo.com; активность не проверялась | аналог OdooPLM; выбирать один из двух |
| **OpenMBEE MMS** | репозиторий моделей для MBSE: версии, ветки, теги, REST (MMS4 на Spring); Flexo — сервис с API SysML v2, модели в RDF | NumFOCUS-проект; активность 2023–2025, свежих релизов 2026 не найдено | не PDM, а хранилище системной модели; интересен как референс для дерева компоновок и требований (SysML v2 API — те же идеи, что D24/D27) |

Выводы для M3 (предварительно):

1. Повторное использование узлов — внутри SkelCAD: узел дерева = проект (D24), ранее разработанный проект
   подключается как узел-ссылка (покупной или свой) с интерфейсами и габаритом; граф связей уже даёт
   «где используется» по всем проектам. Отдельная PLM для этого не нужна.
2. Покупные компоненты — библиотека в SkelCAD как пакеты каталогов (по образцу `packages/std-gost`: таблицы
   плюс параметрические генераторы, например двигатели по IEC-габаритам, подшипники, насосы), источник —
   вендорские PDF/таблицы, которые агент переводит в YAML с проверкой конструктором.
3. Интеграция с внешней PLM/PDM — адаптером по REST, когда появится заказчик с Odoo (OdooPLM) или потребность
   в закупках и складе (InvenTree): SkelCAD отдаёт BOM и STEP, забирает item master. STEP AP242 с PMI — M4.

Источники: [OdooPLM на PyPI](https://pypi.org/project/odooplm/), [модуль plm в apps.odoo.com](https://apps.odoo.com/apps/modules/17.0/plm),
[обзор self-hosted PLM 2026 (DocDokuPLM, OdooPLM, GitPLM)](https://www.pistack.xyz/posts/2026-09-30-self-hosted-plm-docdokuplm-odooplm-gitplm-2026/),
[LibrePLM в apps.odoo.com](https://apps.odoo.com/apps/modules/17.0/pdm), [схема API InvenTree](https://git.invenhost.com/inventree/schema/raw/branch/main/export/336/api.yaml),
[журнал изменений InvenTree](https://git.invenhost.com/inventree/InvenTree/src/commit/6c13d9f2a2db210b8318420b7783f402b3522054/CHANGELOG.md),
[OpenMBEE: статус проектов](https://openmbee.atlassian.net/wiki/spaces/OPENMBEE/pages/629342209), [OpenMBEE Flexo SysML v2](https://openmbee.atlassian.net/wiki/spaces/OPENMBEE/pages/1181188098/Flexo+SysMLv2).
