# Доставка параметрической модели в коммерческие CAD с редактируемым деревом построения (форматы обмена, feature-level transfer, API нативной перестройки, round-trip, чертежи) — состояние на 2026

Примечание по методу: все найденные источники — открытый веб (вендорская документация, help-порталы, форумы, Habr, arXiv, PyPI/GitHub). Пометка **[маркетинг]** — утверждение вендора без независимой проверки; **[документация]** — официальный help/API reference; **[форум/опыт]** — свидетельство практиков. Несколько важных первичных источников оказались недоступны (ap242.org — ошибка TLS-сертификата/соединения; страница Elysium elysium-global.com — сертификат; mbx-if.org/home/cax/recommended-practices — 404, но старая страница cax_recommPractice.php открылась).

---

## Вопрос 1. Что реально переносят форматы обмена: STEP AP203/214/242 (в т.ч. ed2/ed3 — construction history, PMI), JT, 3MF, glTF, DXF/DWG, IFC — и какие CAD это импортируют

### Takeaway
Ни один из массовых нейтральных форматов в 2026 году не доставляет редактируемое дерево построения в коммерческие CAD: STEP AP242 (все три редакции) несёт B-rep, сборку, цвета/слои/имена, валидационные свойства, PMI (графическое и семантическое), кинематику, тесселяцию, user-defined attributes, а в ed3 — «hole features» и ассоциативность геометрия↔топология, но **ни одной Recommended Practice CAx-IF по construction history / procedural modelling не существует**, и ни один найденный CAD не заявляет импорт процедурной истории из STEP. JT, glTF, 3MF — визуализационные/производственные форматы без истории; IFC содержит процедурную геометрию (extrusion/revolution), но её «параметричность» теряется при экспорте сложных форм в B-rep.

### Cited Findings

**STEP AP242 — редакции и содержимое**
- AP242 ed1 (2014) задуман как замена AP203 и AP214 для машиностроительных данных; добавил 533 определения для кинематики, сборочных ограничений и PMI; введены tessellated_face/_solid/_shell; retired 53 сущности AP214 (в основном кинематика) — [STEP Tools, notes_ap242](https://downloads.steptools.com/docs/stp_aim/notes_ap242.html) [документация]
- AP242 ed2 (2020) добавил ~400 определений: семантические допуски, additive setup, улучшенные тесселированные модели и point cloud, новые типы hole features, A3M (annotated 3D model equivalence), electrical wire harness — [STEP Tools, notes_ap242e3](https://downloads.steptools.com/docs/stp_aim/notes_ap242e3.html) [документация]
- AP242 ed3 (декабрь 2022) добавил определения для presentation, features и model associativity: `geometry_to_topology_item_association`, `topology_to_geometry_model_association`, `data_equivalence_criterion_assessment_association`; features — `basic_round_hole`, `basic_round_hole_occurrence`, `basic_round_hole_occurrence_in_assembly`; PMI leader lines (`annotation_to_model_leader_line`, `auxiliary_leader_line`). Имя схемы не менялось между редакциями, различие только по ASN.1 id `{ 1 0 10303 442 4 1 4 }` — [STEP Tools, notes_ap242e3](https://downloads.steptools.com/docs/stp_aim/notes_ap242e3.html) [документация]
- Страницы STEP Tools по ed1 и ed3 **не упоминают** procedural/construction history, ISO 10303-55/108/111/112, `procedural_shape_representation` или user-defined attributes — [notes_ap242](https://downloads.steptools.com/docs/stp_aim/notes_ap242.html), [notes_ap242e3](https://downloads.steptools.com/docs/stp_aim/notes_ap242e3.html)
- Академическая работа NTNU: потенциал STEP представлять «knowledge elements, such as construction history» подтверждён, но «STEP AP242 is not yet implemented in commercial CAD systems» (на момент публикации, несколько лет назад) — [NTNU Open](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2395690)
- ISO work item по следующей редакции AP242 упоминает «process planning in the domain model» в гармонизации с AP238/AP239; про construction history не сказано — [ISO 84300 (under publication)](https://libnor.isolutions.iso.org/standard/84300.html)

**CAx-IF / MBx-IF — что реально тестируется и реализуется**
- CAx-IF — закрытая группа тестирования трансляторов STEP (с 1999 г.), подгруппа MBx-IF, посвящённая реализации и тестированию AP242; два тестовых раунда в год; результат — Recommended Practices — [MBx-IF CAx Implementor Group](https://www.mbx-if.org/home/cax/implementor-group/), [cax_introduction](https://www.mbx-if.org/cax/cax_introduction.php)
- Полный список Recommended Practices CAx-IF (19 документов, актуальные версии): Kinematics v1.3 (2025-10-20), Product & Assembly Structure v4.0 (2025-10-20), Alternative Shapes v1.0 (2025-12-03), Composite Materials v4.4, Cross-Domain Exchange for Downstream Uses v1.0 (2026-01-29), External References v3.1, Geometric and Assembly Validation Properties v4.6 (2023-04-21), Model Styling and Organization v1.10 (2025-08-01) (цвета/слои/имена), PDM Schema Usage Guide v4.3, Persistent IDs v1.8 (2026-03-13), PMI Representation and Presentation (AP242) v4.1 (2024-06-20), PMI Polyline Presentation (AP203/AP214) v2.3, PMI Unicode String Specification v1.0, STEP File Compression v1.3, Supplemental Geometry v1.3, Tessellated 3D Geometry v1.1, User Defined Attributes v1.8 (2021-02-18). **Ни одного документа по construction history / procedural modelling нет** — [MBx-IF Recommended Practices](https://www.mbx-if.org/cax/cax_recommPractice.php) [документация]

**Импорт AP242 в конкретных CAD**
- SolidWorks импортирует PMI из NX, Creo и STEP AP242 как «semantic noneditable annotations»; требуется лицензия MBD — [SolidWorks Help 2024, Import PMI](https://help.solidworks.com/2024/English/SolidWorks/Sldworks/c_import_pmi.htm) [документация]; подтверждение требования MBD-лицензии — [Datakit news](https://www.datakit.com/en/news/exchanging-3d-models-with-pmi-using-step-61.html)
- SOLIDWORKS MBD 2017 начал экспортировать STEP 242 c PMI; на тот момент — presentation PMI, с надеждой на семантический экспорт позже — [SolidWorks Help 2017, STEP 242 PMI export](https://help.solidworks.com/2017/English/SolidWorks/sldworks/c_step_242_pmi_export.htm), [EngineersRule](https://www.engineersrule.com/?p=1801)
- KOMPAS-3D v23/v24: импорт и экспорт STEP в AP203, AP214, AP242 — [help.ascon.ru KOMPAS 24](https://help.ascon.ru/KOMPAS/24/en-US/990_glava123_obmen_informaciej_.html), [KOMPAS 23](https://help.ascon.ru/KOMPAS/23/en-US/990_glava123_obmen_informaciej_.html) [документация]; **о PMI (графическом или семантическом) в справке KOMPAS по STEP ничего не сказано**
- Creo: импорт AP242 поддерживает «PMI graphical representations» для деталей и сборок (presentation, не semantic) — [PTC About STEP Files](https://support.ptc.com/help/creo/creo_pma/r9.0/usascii/data_exchange/interface/About_STEP_Files.html)
- NX: AP242-транслятор — отдельная лицензия; с лицензией STEP242 импортируются любые STEP (AP203/214/242); CAM-продукты транслятор не содержат — [Siemens Support PL8525112](https://support.sw.siemens.com/en-US/okba/PL8525112/Is-it-possible-to-import-AP203/214-format-through-AP242-translator/index.html), [PL8719253](https://support.sw.siemens.com/en-US/okba/PL8719253/Solid-Edge-CAM-Pro-can-not-import-STEP-files/index.html)
- Solid Edge 2022 и AP242: размеры (PMI), сохранённые в AP242, могут «драйвить» модель после реимпорта — но только в synchronous/direct-edit моделлере, не в history-based — [dezignstuff blog](https://dezignstuff.com/?p=12251) [форум/опыт]
- Отрицательный пример: графическое PMI, экспортированное Open CASCADE в STEP, не подхватывается другими CAD — [OCCT forum](https://dev.opencascade.org/content/exported-pmi-graphical-presentation-step-not-picked-other-cad-tools)

**JT**
- ISO 14306 (JT): формат для «3D visualization and interrogation of lightweight geometry and PMI derived from CAD»; несёт фасеты с компрессией, визуальные атрибуты (света, текстуры, материалы), PMI, B-rep с метаданными, конфигурации, стриминг; текущая редакция ISO 14306-4:2026 (Version 3, апрель 2026); не определяет runtime-архитектуру — [ISO 14306](https://www.iso.org/standard/86064.html), [ISO 14306:2017](https://iteh.es/catalog/standards/iso/18fd19fd-36e6-452c-8494-aebda2332a93/iso-14306-2017)

**3MF**
- 3MF Boolean Operations Extension v1.1.1 (20.03.2025) — «extension to the core 3MF specification», только с Core 1.x — [3MF Boolean Ops v1.1.1 PDF](https://3mf.io/wp-content/uploads/sites/106/2025/04/3MF_Boolean_Operations_Extension_v1_1_1.pdf); Volumetric/Implicit Extension (функции, 3D images, level sets, implicit nodes) — pre-release v0.8.0, на странице спецификаций заявлена v1.0.0 (даты противоречат: 02/27/2025 vs 11/13/2025) — [3MF Volumetric v0.8.0](https://3mf.io/wp-content/uploads/sites/106/2025/02/3MF_Volumetric_Extension_v0.8.0.pdf), [3mf.io/spec](https://3mf.io/spec/); стандартизуется как ISO/IEC 25422, Boolean extension — clause 10 — [VDE preview ISO/IEC 25422](https://www.vde-verlag.de/iec-normen/preview-pdf/info_isoiec25422{ed1.0}en.pdf)

**glTF**
- HOOPS Exchange: для glTF «Boundary Representation (B-rep) Unsupported by format», CAD-данные (B-rep, PMI, exact model definitions) не поддерживаются — [Tech Soft 3D glTF Reader](https://docs.techsoft3d.com/hoops/exchange/start/format/gltf_reader.html) [документация]
- Zoo (KittyCAD) построили собственное расширение glTF для описания B-rep в JSON-метаданных и обещали подать в Khronos; статус подачи не подтверждён — [zoo.dev glTF extension](https://zoo.dev/gltf-format-extension) [маркетинг]
- CAD Exchanger: glTF — полигональные представления + структура сборки + материалы, столбец B-Rep пустой — [cadexchanger.com/formats](https://cadexchanger.com/formats/)

**DXF/DWG**
- DIMENSION в DXF — generic entity; AutoCAD требует анонимный блок с отрисовкой размера из LINE/TEXT; ezdxf не учитывает все DIMSTYLE-переменные и ориентируется на BricsCAD; не все возможности DIMENSION поддерживаются во всех версиях DXF (R12 особенно ограничен) — [ezdxf Linear Dimension tutorial](https://ezdxf.readthedocs.io/en/stable/tutorials/linear_dimension.html) [документация]
- Creo при импорте DXF может связать неассоциативные размеры с геометрией опцией «Automatically associate dimensions» — т.е. связь восстанавливается на стороне импортёра, а не хранится в DXF — [PTC interface config options](https://support.ptc.com/help/creo/creo_pma/r12/usascii/data_exchange/interface/interface_configuration_options.html)

**IFC**
- Archicad: параметрический режим экспорта IFC пишет элементы как extruded/revolved geometry, сохраняя thickness/height/reference line; morphs, objects, shells и некоторые стены/балки с нестандартным профилем «always exported using BREP»; в BREP-пути элементы становятся «non-editable elements, and their parameters are lost» — [Graphisoft Help AC29, Geometry Conversion for IFC Export](https://help.graphisoft.com/AC/29/INT/_AC29_Help/121_IFC/121_IFC-37.htm) [документация]

### Inferences
- Для задачи «редактируемое дерево в SolidWorks/KOMPAS» STEP любого AP — транспорт только для B-rep + метаданных (имена, цвета, слои, сборка, PMI, validation properties). Construction history в AP242 существует как потенциал схемы (модули ISO 10303-55/108/111/112), но без CAx-IF Recommended Practice и без известных реализаций это «бумажная» возможность.
- Семантическое PMI через AP242 работает в экосистеме SolidWorks только при лицензии MBD и как неизменяемые аннотации; KOMPAS его импорт/экспорт не документирует.
- IFC — единственный из перечисленных форматов, где процедурная геометрия (extrusion/revolution) действительно переносится и читается, но это BIM-домен; для машиностроительных CAD роли не играет.

### Gaps
- Не удалось получить первичный текст ISO 10303-242 ed2/ed3 (платный) и страницы ap242.org (ошибка соединения/сертификата): точный перечень «procedural» сущностей в AP242 и их статус (нормативный vs. не рекомендованный к реализации) не подтверждён.
- Нет источника, прямо заявляющего, что какой-либо коммерческий CAD импортирует construction history из STEP; отсутствие найдено только «по умолчанию» (нет RP CAx-IF, нет упоминаний у вендоров).
- Статус B-rep-расширения glTF от Zoo в Khronos не проверен.
- KOMPAS-3D: нет данных о семантическом PMI в STEP.

---

## Вопрос 2. Подходы к переносу уровня фич: распознавание фич на STEP (CoreTechnologie, Datakit, Elysium, Spatial, FeatureWorks, Fusion, Inventor), AP242 construction history, ISO 14649, FeatureScript, macro features, iLogic, FreeCAD

### Takeaway
В 2026 году «дерево построения из чужого CAD» реально доставляют только коммерческие native-to-native трансляторы (CoreTechnologie 3D_Evolution Feature Based / 3D_Feature, Elysium CADfeature), читающие **нативные** бинарные файлы, а не STEP; из STEP дерево можно лишь **распознать** эвристически (SolidWorks FeatureWorks, Autodesk Feature Recognition для Inventor) с ограниченным набором типов фич. Fusion и KOMPAS распознавания фич не имеют. ISO 14649 (STEP-NC) — про производственные фичи для ЧПУ, промышленного внедрения не найдено.

### Cited Findings

**CoreTechnologie 3D_Evolution Feature Based / 3D_Feature**
- Переносит feature history tree и параметры, детали и сборки, эскизы фич с ограничениями и аннотациями, 3D PMI и метаданные; native readers извлекают историю, фичи, параметры и B-REP «directly from the binary file» без лицензии/API исходной CAD; «adaptive optimization of the model's history» под типы фич целевой системы; ремастеринг выполняют «3D_Evolution Feature Based plug-ins» в целевой CAD; есть Compare (максимальное отклонение, визуализация в CT/3D PDF); поддерживаются CATIA V5, NX, Creo, SOLIDWORKS, Inventor; success rate и ограничения не приведены, цен нет — [CoreTechnologie Feature-based conversion](https://coretechnologie.com/products/3d-evolution/Feature-based-conversion/) [маркетинг]
- Есть «smart Feature Based checker», выявляющий проблемы до реконструкции — [там же](https://coretechnologie.com/?p=3741)
- Выделен отдельный продукт 3D_Feature (spin-off фичевой технологии), «preserving design history trees, parameters, sketches, and features» — [presseportal](https://www.presseportal.de/pm/165742/6319278) [маркетинг]
- Брошюра 3D_Evolution 2025 — [PDF](https://coretechnologie.com/wp-content/uploads/2025/11/3D_Evolution-Broschuere-2025.pdf)

**Elysium CADfeature**
- Поддерживаемые системы (без разделения на источник/цель): CATIA V5 R30–R36 (V5-6R2020–2026), NX 1980–2606, Creo Parametric 5.0–12.4, Creo Elements/Direct 18.1–20.8, SOLIDWORKS 2020–2026, Inventor 2021–2027, Solid Edge 2020–2026; транслирует фичи «using the feature tools and history from the original CAD system», сборочные сопряжения, ассоциативные 2D-чертежи (листы, виды, масштабы, аннотации, размеры, обновляющиеся с 3D), атрибуты/PMI, косметические резьбы и стандартные детали; QA Reports (геометрия, mass properties, max deviation) — [Elysium CADfeature](https://www.elysium.co.jp/en/products/cadfeature/) [маркетинг]
- GoEngineer (реселлер): сохраняет feature history, сборочные связи и ассоциативные чертежи; «falls back to B-rep recovery when a feature can't be translated»; CADfeature Viewer накладывает исходную и целевую модель — [GoEngineer](https://www.goengineer.com/en-us/elysium-cad-feature) [маркетинг]
- Исторически: v10.0 (2010) добавила чертежи и 64-bit — [Airframer](https://www.airframer.com/news/release/10698); v11.3 — HTML-отчёты и автоматические QA-проверки ремастеринга — [GfxSpeak](https://gfxspeak.com/archives/cadfeature-assurance-workflow/)

**Datakit**
- Общая декларация: инструменты Datakit переносят «2D, 3D, geometric, topological, attributes, construction history, FD&T, and Features with adjustable control parameters» — [datakit.com product](https://datakit.com/en/product.php) [маркетинг]; CrossManager — standalone batch-конвертер (движок + read/write-модули по форматам); конкретно история фич документирована только для плагина импорта CATIA V5 в SOLIDWORKS («get information from the history tree») — [CADimensions Datakit](https://www.cadimensions.com/products/software/solidworks-design/extensions/datakit-crosscad-crossmanager/); сторонняя оценка: CrossManager «primarily a translator», результат зависит от представления фич в source/target — [FitGap](https://us.fitgap.com/products/032843/crossmanager)

**SolidWorks FeatureWorks (распознавание на импортированном B-rep)**
- Распознаёт extrude/revolve, chamfers, constant/variable fillets, ribs, drafts, holes (simple, taper, countersunk, counterbored) — [SolidWorks Help 2018 Overview](https://help.solidworks.com/2018/English/SolidWorks/fworks/c_Overview_of_FeatureWorks.htm), [2012](https://help.solidworks.com/2012/english/SolidWorks/fworks/c_Overview_of_FeatureWorks.htm) [документация]
- Для cut-extrude распознаются только end conditions Blind, Through All, Up to Next; extended end conditions — только с resize tool — [Recognizing Features Automatically 2018](https://help.solidworks.com/2018/English/SolidWorks/fworks/t_recognizing_features_automatically.htm)
- Неподдерживаемые фичи: диалог предупреждает; можно удалить или замапить как thicken; mapping только для boss/cut loft, boss/cut sweep, non-legacy holes — [step-by-step 2015](https://help.solidworks.com/2015/English/SOLIDWORKS/fworks/t_Recognizing_Features_Using_step_by_step.htm)
- FeatureWorks API: не поддерживает combining, re-recognizing features, recognizing patterns, Local Feature Recognition и Recognize Similar — [FeatureWorks API Getting Started 2022](https://help.solidworks.com/2022/english/api/fworksapi/GettingStarted-fworksapi.html) [документация]
- Входные форматы: STEP, IGES, SAT (ACIS), VDA-FS, Parasolid — [TriMech blog](https://store.trimech.com/blog/when-do-i-need-featureworks/page/8)
- Учебник FeatureWorks в SOLIDWORKS 2025 существует (функция жива) — [SW 2025 tutorial](https://help.solidworks.com/2025/English/swconntutorial/c_FeatureWorks_Tutorial_Overview.htm)

**Autodesk Inventor — Feature Recognition add-in**
- Бесплатный add-in в Autodesk App Store, версия 1.0.15 (обновлён 16.06.2026), поддерживает Inventor 2025/2026/2027; конвертирует нейтральные модели (STEP, SAT, IGES) в «full-featured Autodesk Inventor models», automatic или interactive mapping; help — FRHelp.chm в bundle — [Autodesk App Store](https://marketplace.autodesk.com/apps/6110f8fb-76fa-4630-92f3-a641fddb15e1) [маркетинг/документация]

**Autodesk Fusion**
- Импортированные модели открываются в direct modeling без timeline: «no history, sketches, or relationships were imported»; «Capture Design History» кладёт импорт в base feature и записывает только последующие правки — [Autodesk forum (Jeff Strater)](https://forums.autodesk.com/t5/fusion-design-validate-document/capture-design-history-off-after-import/m-p/7500154/highlight/true), [direct modeling tutorial](https://www-pt.autodesk.com/learn/ondemand/curated/direct-modeling-with-fusion/43yJpL2EJKH1kCt2r4Xjbi); с января 2025 при включённой настройке дизайн открывается с timeline и base feature — [форум, пост инженера Autodesk](https://forums.autodesk.com/t5/fusion-design-validate-document/capture-design-history-off-after-import/m-p/12769824/highlight/true) [форум/опыт]
- Convert Mesh: методы Faceted и Prismatic (объединяет группы граней в призматические грани — ближайшее к «распознаванию»); операция Parametric создаёт фичу в timeline — [Autodesk Help MESH-CONVERT-TO-SOLID](https://help.autodesk.com/cloudhelp/ENU/Fusion-Mesh/files/MESH-CONVERT-TO-SOLID.htm) [документация]
- Сторонний fusion-reconstruct-mcp обещает LLM-восстановление параметрической модели из STL/3MF «feature by feature» — зрелость не проверена — [glama.ai listing](https://glama.ai/mcp/servers/vygejrwtta)

**KOMPAS-3D**
- С v20 читает SolidWorks, Inventor, NX, CATIA, Creo, Solid Edge «без предварительной конвертации»; в v24 — чтение Creo/Inventor/CATIA/Solid Edge средствами ядра C3D; для чтения чужих форматов используется транслятор партнёра; после открытия SLDPRT модель «можно переработать: удалить отверстия, фаски, добавить элементы» — [Habr/АСКОН ретроспектива](https://habr.com/en/companies/ascon/articles/785950), [KOMPAS v24 Highlights](https://ascon.net/upload/iblock/3e3/1tdi1jt9l5p2tfnnm2r30xwgiuf7gzgd/KOMPAS_3D_v24_Highlights.pdf), [комментарии](https://habr.com/ru/companies/ascon/articles/785950/comments). **Нигде не заявлен перенос дерева построения**; результат импорта детали — один файл KOMPAS — [help.ascon.ru import](https://help.ascon.ru/KOMPAS/23/en-US/990_123_1_import.html)
- На ascon.net есть страница «3D Model Recognition» — [ascon.net](https://ascon.net/products/cad/3d-model-recognition/) (содержимое не удалось проверить в этой сессии)

**ISO 14649 (STEP-NC)**
- STEP-NC (AP238 + ISO 14649) — результат 10-летних усилий по замене G/M-кодов (ISO 6983); описывает device-independent tool paths и «CAM independent volume removal features»; разработка в ISO TC184/SC1 WG7 и SC4 WG3 Team 24 — [KoreaScience](https://koreascience.or.kr/article/JAKO200011922271854.page), [Loughborough](https://dspace.lboro.ac.uk/dspace-jspui/handle/2134/5064); обзор 2013 — демонстрации расширений модели — [Bristol/core.ac.uk roadmap](https://core.ac.uk/works/18591738). Данных о коммерческом внедрении контроллерами/CAM в 2024–2026 не найдено.

**Onshape FeatureScript / macro features / iLogic / FreeCAD — как механизмы «нативной параметрической фичи»**
- Onshape: custom FeatureScript-фича добавляется через REST тем же маршрутом, что и стандартная (POST features, тело — feature JSON); отличие — поле `namespace` c documentId/versionId/elementId Feature Studio; рекомендация — добавить фичу в UI, выгрузить JSON списка фич и копировать структуру; FeatureScript «sandboxed within a single feature», API может добавлять/удалять фичи — [Onshape forum 18560](https://forum.onshape.com/discussion/18560/how-do-i-add-a-custom-feature-i-wrote-in-featurescript-to-my-partstudio-using-the-api), [forum 11476](https://forum.onshape.com/discussion/11476/access-to-api-methods-from-feature-script) [форум/официальный сотрудник]
- SolidWorks macro feature: `IFeatureManager::InsertMacroFeature3` — ProgId COM-компонента, реализующего `ISwComFeature` (rebuild/edit/security callbacks); параметры хранятся в фиче и доступны через `IMacroFeatureData`; VBA-вариант — массив из 9 строк (файл/модуль/процедура); BaseName сериализуется и не меняется — [SW API 2026 InsertMacroFeature3](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~InsertMacroFeature3.html), [Inserting Macro Features guide](https://help.solidworks.com/2018/english/api/sldworksapiprogguide/macro_features/inserting_macro_features.htm), [Rebuild Function](https://help.solidworks.com/2017/English/api/sldworksapiprogguide/macro_features/Rebuild_Function.htm) [документация]
- Inventor API: старый `ExtrudeFeatures.AddByDistanceExtent` удалён; текущий паттерн — `CreateExtrudeDefinition` → `SetDistanceExtent` → `ExtrudeFeatures.Add` — [Autodesk forum](https://forums.autodesk.com/t5/inventor-programming-ilogic/edit-an-existing-extrusion-with-ilogic-vba/m-p/8452007), [Inventor API 2025 sample](https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-API/files/ExtrudeFeatures_AddByDistanceExtent_Sample.htm), [CreateExtrudeDefinition](https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-API/files/ExtrudeFeatures_CreateExtrudeDefinition.htm) [документация]
- FreeCAD: headless-режим (FreeCADCmd) для «scripting, automation, and embedding»; модули из Mod/ (PartDesign, Part) могут не находиться без добавления в sys.path; пример на 1.0.2 — [FreeCAD wiki Headless](https://wiki.freecad.org/Headless_FreeCAD); скриптинг PartDesign со Sketcher-ограничениями (Coincident, Horizontal, DistanceX, Radius, Fixed) — [wiki Scripting PartDesign Workbench](https://wiki.freecad.org/Scripting_PartDesign_Workbench) [документация/community wiki]

### Inferences
- Для сценария «внешняя модель → SolidWorks/KOMPAS» коммерческие feature-based трансляторы бесполезны напрямую: они требуют на входе нативный файл CATIA/NX/Creo/SW/Inventor/Solid Edge, а KOMPAS как цель ни у CoreTechnologie, ни у Elysium не заявлен.
- Распознавание фич (FeatureWorks, Inventor Feature Recognition) покроет призматические детали (extrude/revolve/hole/fillet/chamfer), но не восстановит замысел (эскизные ограничения, уравнения, паттерны в SW API не распознаются). Это «путь по умолчанию» для B-rep, но не замена нативной перестройке.
- Macro feature (SW) и FeatureScript (Onshape) — механизмы, позволяющие внедрить **собственную** параметрическую фичу с callback на rebuild; это единственный способ сохранить связь с внешней моделью внутри дерева, а не только воспроизвести его.

### Gaps
- Нет независимых бенчмарков доли успешно переносимых фич у CoreTechnologie/Elysium — только вендорские формулировки и наличие Compare/QA-инструментов (косвенно признающих расхождения).
- Статус Spatial 3D InterOp и Geomagic в контексте фич не исследован (в найденных источниках не фигурируют).
- Содержимое страницы ascon.net «3D Model Recognition» не проверено — неясно, есть ли у KOMPAS распознавание фич на импортированном теле.
- Коммерческое внедрение ISO 14649/AP238 в 2024–2026 — не найдено.

---

## Вопрос 3. Программные API нативной перестройки и их известные ограничения: SolidWorks (COM/.NET, Python/pywin32, макросы, диалоги, локаль, производительность), KOMPAS-3D API5/API7/KsAPI, AutoCAD (.NET/COM/LISP/accoreconsole), Inventor, FreeCAD, Onshape REST

### Takeaway
Все перечисленные API позволяют строить нативное дерево программно; практические «грабли» документированы: в SolidWorks — late-binding pywin32 (вызов свойств без аргументов), имена объектов в `SelectByID2` локализованы в записанных макросах, диалоги/обновление дерева (нужно `CommandInProgress`, `EnableFeatureTree`/`EnableFeatureTreeWindow`), события только pre-edit; в KOMPAS — две/три несовместимые ветки API (API5/API7/KsAPI), документация в SDK/PDF «KOMPAS-Invisible», зависимость номеров ячеек штампа от стиля, подавление диалогов через `HideMessage`; AutoCAD в headless `accoreconsole` не имеет диалогов и теряет часть LISP-команд; Onshape — REST `addPartStudioFeature` с хрупким JSON.

### Cited Findings

**SolidWorks API**
- pySldWrap (PyPI, v0.2 от 20.11.2022): обёртка над pywin32/win32com; функции `connect_sw(version)`, `open_part`, `open_assembly`, `edit_dimension_sketch`, `edit_dimension_extrude`, `edit_pattern`, `save_model`, `export_to_step`, `mass_properties`; SolidWorks должен быть запущен заранее; Python ≥3.6 — [PyPI pySldWrap](https://pypi.org/project/pySldWrap/) [документация пакета]
- Pitfall late-binding pywin32: члены SOLIDWORKS COM непоследовательно экспонированы; обращение к свойству может вызвать метод без аргументов (случай с `GetFaces`, выглядящий как одноэлементный результат) — [solidworks-mcp README via glama](https://glama.ai/mcp/servers/rj1elu3jbn) [форум/опыт одного разработчика]; альтернатива — comtypes (solidworks-automation-skill использует pywin32 и comtypes) — [sourcepulse](https://www.sourcepulse.org/projects/30907696)
- Локаль/имена: записанные макросы используют `SelectByID2("Front Plane", "PLANE", ...)` — имя по-английски — [SW forum 90163](https://forum.solidworks.com/thread/90163), [3DSwym](https://3dswym.3dexperience.3ds.com/question/solidworks-user-forum/selecting-the-front-plane-in-solidworks-api_WVBSYIdET1qIIaWGUhW8tA); пустое имя даёт COM-ошибку (SW2016, C#) — [3DSwym](https://3dswym.3dexperience.3ds.com/question/solidworks-user-forum/unable-to-use-selectbyid2-in-c_17cN-IreQb2av5qv0i2pIQ); тип «REFPLANE» вместо «PLANE» не выбирает плоскость — [Scribd debugging tips](https://www.scribd.com/document/437837216/Solidworks-API-Vba-Debugging-Tips); выбор по координатам граней ненадёжен при смене вида — [SelectByID2 2024](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SelectByID2.html) [документация]
- Языконезависимая идентификация типов: `IFeature::GetTypeName2` возвращает строковый тип (напр. «RefPlane», Chamfer, Fillet, Extrusion, Boss, Cut, Revolution; «ICE» для Instant3D) — [GetTypeName2 2022](https://help.SOLIDWORKS.com/2022/english/api/sldworksapi/SOLIDWORKS.interop.sldworks~SOLIDWORKS.interop.sldworks.ifeature~gettypename2.html), [2010](https://help.solidworks.com/2010/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeature~gettypename2.html); сопряжения — `MateCoincident` и т.п. — [GetTypeName 2026](https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeature~GetTypeName.html) [документация]
- Производительность: `ISldWorks::CommandInProgress` = true на время пачки вызовов (только для out-of-process) — [CommandInProgress 2015](https://help.solidworks.com/2015/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~CommandInProgress.html); `IFeatureManager::EnableFeatureTree` отключает обновление дерева (дерево может устареть), `EnableFeatureTreeWindow` блокирует взаимодействие пользователя с деревом — [EnableFeatureTree 2019](https://help.solidworks.com/2019/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~EnableFeatureTree.html), [EnableFeatureTreeWindow 2024](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~EnableFeatureTreeWindow.html) [документация]
- Python-обёртка OpenDoc6 и 10+ кодов ошибок открытия — [CSDN (кит.)](https://bbs.csdn.net/weixin_29189003/article/details/100178995)
- Community MCP-серверы для SolidWorks (все — Windows + локальный SW): vespo92/SolidworksMCP-TS (alpha, большинство инструментов не проверены на живом SW) — [glama](https://glama.ai/mcp/servers/iip0039kw7); haunchen/solidworks-mcp (Python, Streamable HTTP, протестирован только SW2021) — [mcpservers.org](https://mcpservers.org/zh-TW/servers/haunchen/solidworks-mcp); arhamgarg/solidworks-mcp (один инструмент `solidgen`, LLM пишет pywin32-скрипт) — [glama](https://glama.ai/mcp/servers/@arhamgarg/solidworks-mcp/inspect); alisamsam/solidworks-mcp («production-ready», 22 инструмента, SW 2023–2025 — самооценка) — [glama](https://glama.ai/mcp/servers/gc6fgz84qm); solidworks-mcp-server npm 3.1.3 — [README](https://cdn.jsdelivr.net/npm/solidworks-mcp-server@3.1.3/README.md)

**KOMPAS-3D API**
- Три ветки: API5 (`KompasObject`; базовые операции — чертежи, фрагменты, спецификации, компоненты сборок, выдавливание/вращение; «основа для большинства задач»), API7 (`IKompasAPIObject`; + параметрические переменные, события интерфейса, расширенные настройки), KsAPI (новый кроссплатформенный Windows/Linux, C++, только главный поток) — [Habr 890110](https://habr.com/ru/articles/890110), [Habr 860636 (Linux-порт)](https://habr.com/ru/articles/860636), [Habr 323078](https://habr.com/ru/articles/323078)
- Документация: справка API входит в SDK (опция при установке); PDF «Руководство пользователя KOMPAS-Invisible (API КОМПАС-3D)» на сайте АСКОН; SDK-модули написаны для Delphi (в Lazarus нужен `{$mode delphi}`); цикл статей Сергея Норсеева; раздел прикладного программирования на форуме АСКОН — [Habr 890110](https://habr.com/ru/articles/890110)
- Python/API7: `win32com.client.Dispatch("Kompas.Application.7")`, `gencache.EnsureModule` с GUID `{69AC2981-37C0-4379-84FD-5DD2F3C0A520}` (API7) и `{75C9F5D0-B5B8-4526-8681-9903C567D2ED}` (константы); требуется KOMPAS ≥ v14, Python 3, pywin32; получение `IDrawingDocument`/`IKompasDocument2D` требует `QueryInterface` (SDK прояснил только в v16); `HideMessage = ksHideMessageNo` подавляет диалоги ответом «нет»; имена процессов `KOMPAS*` различаются по версиям; номера ячеек штампа зависят от стиля оформления — [Habr 323078](https://habr.com/ru/articles/323078), [GitHub Weltraum](https://github.com/Weltraum/Article-Python-in-aid-of-the-designer-Tames-API-Kompas-3D) [опыт]
- Python/API5 пример (`Kompas10API5`) — [C3D Labs 2016 PDF](https://c3dlabs.com/upload/pdf/b10/2016_05_SiG_API_C3D.pdf); пакет `kompas-tools` на PyPI (v0.1–0.3, январь 2024; содержание не раскрыто) — [piwheels](https://www.piwheels.org/project/kompas-tools); неофициальный конспект API с Python-подключением — [context7 kompas-api-doc](https://context7.com/dwnmf/kompas-api-doc)
- KOMPAS-Macro записывает действия пользователя как Python-команды в файл, который можно редактировать и вешать на кнопку; API доступен для C#, C++, Python; построение сложных моделей «чисто из кода» громоздко — автор советует параметрическую модель с внешними переменными; данные в storage объекта удаляются при редактировании свойства в UI — [Habr 890110](https://habr.com/ru/articles/890110)
- АСКОН использует Python для тестирования KOMPAS-3D (внутренний опыт) — [Habr/АСКОН 743498](https://habr.com/en/companies/ascon/articles/743498)

**AutoCAD / nanoCAD**
- `accoreconsole.exe` — консольный движок без GUI; рассчитан на .scr-скрипты и плагины; FILEDIA=0, диалогов нет — [Autodesk forum](https://forums.autodesk.com/t5/net-forum/set-filedia-doesn-t-work-in-accoreconsole-with-specific-argument/m-p/13913842/highlight/true); LISP-команды, работающие в AutoCAD, могут давать «Unknown command» в консоли — [CADTutor](https://www.cadtutor.net/forum/topic/61706-accoreconsole-issues-with-simple-lisp-scr-file/); сравнение plug-in vs headless — [velog](https://velog.io/@tonyisback/AutoCAD-API-제어-방식-Plug-In-vs-headless) [форум/опыт]
- nanoCAD: NrxGate и .NET API (C++/.NET), MultiCAD API и MultiCAD .NET API (кроссплатформенные приложения, работают и в AutoCAD через MultiCAD Enabler после регистрации в Клубе разработчиков), COM API (JScript/VBScript), LISP — [nanoCAD Help software extensions](https://nanocad.com/learning/online-help/software-extensions), [Habr/Нанософт 188326](https://habr.com/en/companies/nanosoft/articles/188326), [133723](https://habr.com/en/companies/nanosoft/articles/133723) [документация]

**Onshape REST**
- Base URL `https://cad.onshape.com/api/v16`; POST features (`addPartStudioFeature`) добавляет фичу в Feature List; POST featurescript — исполняет сниппет — [APIs.io Onshape PartStudio](https://apis.apievangelist.com/store/onshape-partstudio-api/); «Error processing json» и зависимость формата от версии API — [forum comment 119263](https://forum.onshape.com/discussion/comment/119263); MCP-обёртка — [hedless/onshape-mcp](https://github.com/hedless/onshape-mcp)

**Autodesk Fusion API**
- Добавление extrude через Python API (`adsk.fusion`, `ExtrudeFeatures.addSimple` / `createInput`) — [Autodesk blog](https://blog.autodesk.io/fusion-api-add-simple-extrude-feature-and-add-by-input/) [документация]

### Inferences
- Для Python-автоматизации SolidWorks и KOMPAS единая техническая база — COM через pywin32 (early binding через `gencache.EnsureModule` снимает часть проблем late binding). Для обеих систем требуется запущенный GUI-процесс (нет headless-режима), в отличие от AutoCAD (`accoreconsole`) и FreeCAD (`FreeCADCmd`).
- Локализация в SolidWorks бьёт по именам объектов (плоскости, фичи), но не по типам (`GetTypeName2`): надёжный рецепт — идентифицировать объекты по типу/позиции в дереве и собственным именам, а не по UI-названиям.
- У KOMPAS главный риск не диалоги, а фрагментация API (API5/API7/KsAPI) и слабая открытая документация: практики опираются на SDK-справку и Habr-статьи Норсеева/АСКОН.

### Gaps
- Не найдено официальной документации SolidWorks по подавлению модальных диалогов из API (кроме косвенных: `CommandInProgress`, `EnableFeatureTreeWindow`); поведение при ошибках rebuild (диалог «Rebuild errors») не задокументировано в найденных источниках.
- Для KOMPAS не найден открытый пример на Python создания 3D-фич (эскиз + выдавливание) через API7 — найденные примеры работают с 2D-чертежами; интерфейсы `IPart7`/`IExtrusion` в веб-источниках не подтверждены.
- Python-обёртки для Inventor (win32com) — только вывод по аналогии с VBA, рабочих скриптов не найдено.
- Undo/транзакции в KOMPAS API и производительность пакетной перестройки — источников нет.

---

## Вопрос 4. Существующие проекты/статьи «рецепт/манифест → нативные фичи» (JSON-скрипты фич, CAD-нейтральные feature-модели, semantic CAD exchange, code-as-CAD)

### Takeaway
Подход «нейтральное описание фич → реплей через API целевой CAD» имеет академическую традицию (BYU NPCF/XML 2016–2019, Gao 2010, IJACSA 2026 JSON NX→ZW3D, патент US 7,492,364) и свежую волну «code-as-CAD» (Fusion 360 Gallery JSON, CadQuery-генерация: CAD-Recode, Text-to-CadQuery, CAD-Coder), но **ни одного зрелого open-source проекта, воспроизводящего JSON-рецепт в SolidWorks и KOMPAS одновременно, не найдено**; ближайшие аналоги — исследовательские прототипы и MCP-серверы ранней стадии.

### Cited Findings
- Wang & Zhang, «Migration Method for Parametric Features in Heterogeneous CAD Systems» (IJACSA, 2026): трёхстадийная миграция через JSON — извлечение параметров фич из API источника, идентификация топологии, валидация, перестройка; прототип-плагин NX → ZW3D; мотивация — геометрический обмен не несёт construction history и constraints — [IJACSA PDF](https://thesai.org/Downloads/Volume17No7/Paper_18-Migration_Method_for_Parametric_Features.pdf)
- BYU (Sadler et al., CAD 2019): XML-формат для генерации параметрических деталей в нескольких CAD, скрипты пишутся независимо от CAD и транслируются в модель — [CAD 165 2019 PDF](https://design.byu.edu/s/CAD_165_2019_923-935.pdf); диссертации BYU по Neutral Parametric Canonical Form (NPCF), NX и CATIA в многопользовательском режиме — [BYU etd/5688](https://scholarsarchive.byu.edu/etd/5688), [etd/6222](https://scholarsarchive.byu.edu/etd/6222)
- Gao (IJPLM 2010): обмен feature-операциями как «neutral modelling commands» в реальном времени — [Inderscience](https://www.inderscience.com/filter.php?aid=36487)
- Патент US 7,492,364 «Universal Feature Object»: нейтральный формат feature-based 3D моделей для нескольких CAD — [Google Patents](https://patents.google.com/patent/US7492364B2); US 7,277,835 «Boundary representation per feature» — [Google Patents](https://patents.google.com/patent/US7277835)
- Fusion 360 Gallery (SIGGRAPH 2021): 8 625 дизайнов sketch+extrude с последовательностью построения; Fusion 360 Gym — среда, где построение CAD-программы трактуется как MDP; репозиторий AutodeskAILab/Fusion360GalleryDataset с инструментами реконструкции геометрии через Fusion API (`tools/`, `regraphnet`) — [arXiv 2010.02392](https://arxiv.org/abs/2010.02392v1), [Autodesk Research](https://www.research.autodesk.com/publications/fusion-360-gallery/), [GitHub](https://github.com/AutodeskAILab/Fusion360GalleryDataset)
- CAD-Recode (ICCV 2025): point cloud → Python (CadQuery) код; обучен на 1 млн процедурно сгенерированных последовательностей; код читаем off-the-shelf LLM для редактирования и QA — [CADRecode ICCV 2025 PDF](https://orbilu.uni.lu/bitstream/10993/67036/1/CADRecode_ICCV_2025.pdf)
- Text-to-CadQuery (arXiv 2505.06507): 170k CadQuery-аннотаций к Text2CAD, лучший exact match 69,3% — [HF papers](https://huggingface.co/papers/2505.06507); CAD-Coder (NeurIPS 2025): SFT + GRPO с геометрическим reward (Chamfer), «CadQuery scripts can be executed directly to verify» — [NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/564a224e88f2490f3c1deaae877d37e3-Abstract-Conference.html), [arXiv 2505.19713](https://arxiv.org/abs/2505.19713v1); Text2CAD-Bench (arXiv 2605.18430) — [PDF](https://arxiv.org/pdf/2605.18430)
- MCP-серверы для SolidWorks как «LLM-реплей» (см. вопрос 3), fusion-reconstruct-mcp — [glama](https://glama.ai/mcp/servers/vygejrwtta); solidworks-automation-skill (pywin32+comtypes) — [sourcepulse](https://www.sourcepulse.org/projects/30907696)

### Inferences
- Общий паттерн у всех работающих систем: нейтральное описание ограничено «каноническими» фичами (sketch с constraints, extrude/revolve/hole/fillet/chamfer/pattern), а трансляция в каждую CAD — отдельный плагин/адаптер поверх её API (как у BYU, у IJACSA, у CoreTechnologie «plug-ins in target CAD»). Это и есть реалистичная архитектура для SolidWorks+KOMPAS: JSON-манифест фич → адаптеры на pywin32 (SW API / KOMPAS API7).
- Code-as-CAD (CadQuery) даёт переносимый и верифицируемый артефакт, но CadQuery исполняется в OCCT, а не в целевых CAD — он решает генерацию, а не доставку дерева.

### Gaps
- Open-source проект, реплеящий один манифест в SolidWorks и KOMPAS, не найден (поиски по GitHub/habr дали только одно-CAD инструменты).
- JSON-схема Fusion 360 Gallery не извлечена со страницы README (нужно читать `docs/reconstruction.md`).
- Статус «Semantic CAD exchange» как термина/проекта — релевантных источников не найдено.

---

## Вопрос 5. Чертежи: доставка DXF/DWG/SVG/PDF с размерами, привязанными к геометрии; штампы ЕСКД/ISO/ASME через API

### Takeaway
Ассоциативность размеров с геометрией достигается только внутри нативной CAD (SolidWorks `InsertModelAnnotations3` из модели; KOMPAS — ассоциативные виды с модели), а DXF/SVG/PDF несут размеры как «нарисованные» объекты; восстановление связи при импорте DXF — эвристика импортёра (пример Creo). Заполнение основной надписи ЕСКД в KOMPAS программно задокументировано (ksStamp / GetStamp / ksTextLine), для nanoCAD/AutoCAD — через блоки с атрибутами.

### Cited Findings
- SolidWorks `IDrawingDoc::InsertModelAnnotations3(Option, Types, AllViews, DuplicateDims, HiddenFeatureDims, UsePlacementInSketch)` вставляет модельные аннотации в выбранный/все виды; Option: 0 — вся модель, 1 — выбранная фича, 2 — выбранный компонент, 3 — только сборочные размеры (до SW2008 SP3 документация была неверной) — [SW API 2024](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDrawingDoc~InsertModelAnnotations3.html), пример — [VB.NET 2020](https://help.solidworks.com/2020/English/api/sldworksapi/Insert_Model_Annotations_Example_VBNET.htm) [документация]; сообщение, что Option 3 не сработал — [3DSwym](https://3dswym.3dexperience.3ds.com/post/solidworks-user-forum/getting-assembly-dimensions-in-a-drawing_bMKA0hDxQ_CkjESvvGDfCw) [форум]
- KOMPAS основная надпись (API5): указатель на штамп через `GetStamp()`/`GetStampEx(номер_листа, с 1)` у `ksDocument2D`, `ksSpcDocument`, `ksDocumentTxt`; запись строк — `ksTextLine` интерфейса `ksStamp` с `ksTextLineParam` (через `GetParamStruct(ko_TextLineParam=29)`); чтение `ksGetStampColumnText` только между `ksOpenStamp()` и `ksCloseStamp()` (иначе NULL); сложные случаи — `ksDynamicArray` — [Habr/АСКОН 337288 (Норсеев, ч.4)](https://habr.com/en/companies/ascon/articles/337288), [Habr 350516 (ч.5)](https://habr.com/company/ascon/blog/350516), [Habr 359232](https://habr.com/post/359232/) [опыт/документация в статьях]
- KOMPAS/Python: чтение ячеек штампа и техтребований через API7 (`LayoutSheets`, `ViewsAndLayersManager.Views`, `ISymbols2DContainer`); номера ячеек не универсальны — зависят от стиля (библиотека и номер стиля); масштаб может быть в другой ячейке — [Habr 323078](https://habr.com/ru/articles/323078) [опыт]
- Переменные модели KOMPAS могут подставляться в текст через ссылки (техтребования, текст размера) — [Habr 890110](https://habr.com/ru/articles/890110)
- DXF: DIMENSION generic + анонимный блок; ezdxf рендерит сам и не покрывает все DIMSTYLE — [ezdxf](https://ezdxf.readthedocs.io/en/stable/tutorials/linear_dimension.html); GDAL использует анонимный блок при наличии — [GDAL ticket 7120](https://trac.osgeo.org/gdal/ticket/7120)
- Creo: «Automatically associate dimensions» при импорте DXF связывает неассоциативные размеры с геометрией — [PTC](https://support.ptc.com/help/creo/creo_pma/r12/usascii/data_exchange/interface/interface_configuration_options.html)
- nanoCAD: MultiCAD .NET — вставка блоков с атрибутами (путь для штампов), запуск в AutoCAD через MultiCAD Enabler — [Habr/Нанософт 188326](https://habr.com/en/companies/nanosoft/articles/188326)
- Elysium CADfeature переносит ассоциативные 2D-чертежи между нативными CAD (листы, виды, масштабы, размеры, обновляющиеся с 3D) — [Elysium](https://www.elysium.co.jp/en/products/cadfeature/) [маркетинг]

### Inferences
- Если нужен чертёж с «живыми» размерами — его надо генерировать в целевой CAD из доставленной модели (SW: виды + `InsertModelAnnotations3`; KOMPAS: ассоциативные виды + заполнение штампа через `ksStamp`), а DXF/PDF отдавать как производные.
- ЕСКД-штамп в KOMPAS — встроенный (стили оформления), программный доступ есть, но привязка к номерам ячеек требует фиксировать стиль оформления в манифесте.

### Gaps
- Для SolidWorks не найдено источников по заполнению title block (sheet format + custom properties) через API в этом исследовании — нужна отдельная проверка `ISheet`/`IModelDocExtension.CustomPropertyManager`.
- Для AutoCAD/nanoCAD готовых ЕСКД-решений по API (кроме блоков с атрибутами) не найдено; СПДС/Механика-модули не исследованы.
- SVG как носитель размеров — источников нет (вывод: чисто графика).

---

## Вопрос 6. Самый практичный путь в 2026 доставить редактируемые нативные фичи в SolidWorks и KOMPAS из внешней модели; open-source прецеденты

### Takeaway
Единственный путь, обеспечивающий настоящее дерево в обеих системах, — программная перестройка через нативные API (SolidWorks COM/.NET или Python-pywin32; KOMPAS API5/API7 через COM/pywin32) из нейтрального описания фич; STEP+распознавание (FeatureWorks) годится как fallback для SolidWorks, для KOMPAS fallback — только B-rep с прямым редактированием. Open-source прецедентов «один манифест → SW и KOMPAS» нет; есть одноцелевые обёртки (pySldWrap, SolidWorks MCP-серверы, Python-примеры KOMPAS API7).

### Cited Findings
- SolidWorks: нативная фича с callback — `InsertMacroFeature3` + `ISwComFeature` ([SW API 2026](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~InsertMacroFeature3.html)); Python-обёртка pySldWrap ([PyPI](https://pypi.org/project/pySldWrap/)); FeatureWorks как fallback с перечисленными ограничениями ([SW Help](https://help.solidworks.com/2018/English/SolidWorks/fworks/c_Overview_of_FeatureWorks.htm))
- KOMPAS: API5 покрывает выдавливание/вращение и документы ([Habr 890110](https://habr.com/ru/articles/890110)); Python-подключение к API7 ([Habr 323078](https://habr.com/ru/articles/323078)); KsAPI как будущее кроссплатформенное API (Linux) ([Habr 860636](https://habr.com/ru/articles/860636)); импорт чужих нативных форматов без заявленного переноса дерева ([Habr/АСКОН 785950](https://habr.com/en/companies/ascon/articles/785950))
- Коммерческая альтернатива для SW как цели — CoreTechnologie/Elysium, но вход — нативные файлы других CAD; KOMPAS в списках целей отсутствует ([CoreTechnologie](https://coretechnologie.com/products/3d-evolution/Feature-based-conversion/), [Elysium](https://www.elysium.co.jp/en/products/cadfeature/))
- Академический прецедент той же архитектуры (JSON → плагин целевой CAD) — [IJACSA 2026](https://thesai.org/Downloads/Volume17No7/Paper_18-Migration_Method_for_Parametric_Features.pdf), [BYU 2019](https://design.byu.edu/s/CAD_165_2019_923-935.pdf)

### Inferences
- Практичная архитектура-2026: (1) канонический манифест фич (sketch+constraints, extrude/revolve/hole/fillet/chamfer/pattern, переменные/уравнения); (2) адаптер SW на pywin32/.NET, адаптер KOMPAS на pywin32 API5/API7; (3) STEP как параллельный B-rep-канал для верификации (сравнение объёма/массы, как делают CoreTechnologie Compare и Elysium QA); (4) опционально macro feature в SW для хранения ссылки на внешний манифест.
- Rebuild «из кода» в KOMPAS по свидетельству практиков громоздок — разумно опираться на параметрическую модель-шаблон с внешними переменными, где это возможно.

### Gaps
- Нет публичных данных о производительности пакетной перестройки (сотни фич) через COM в SW/KOMPAS.
- Нет сведений о поддержке KsAPI из Python (KsAPI — C++).

---

## Вопрос 7. Round trip: инженер правит в CAD → внешняя модель узнаёт об изменении

### Takeaway
Полноценные webhooks есть только у облачных систем (Onshape: `onshape.model.lifecycle.changed` и др.; Fusion Data API — webhooks на milestones в 2022, статус design-change webhooks не подтверждён); в десктопных SW/KOMPAS — только внутрипроцессные события (SW: `FeatureEditPreNotify`, `RegenPostNotify2`; KOMPAS API7: «события интерфейса») плюс сравнение состояния/файлов.

### Cited Findings
- Onshape webhooks: регистрация POST `/api/v6/webhooks` (event, `options.collapseEvents`, url, `companyId`/`documentId`); события `onshape.document.lifecycle.created`, `onshape.document.lifecycle.statechange`, `onshape.model.lifecycle.createversion`, `onshape.model.lifecycle.changed`, `onshape.model.translation.complete`, `onshape.user.lifecycle.updateappsettings`, `onshape.comment.create`; мета `webhook.register/unregister/ping`; тестовое уведомление при регистрации (без 200 — регистрация отменяется); очистка неактивных хуков (`isTransient=false`); дубликаты не дедуплицируются; HTTPS с признанным CA — [Onshape webhook docs](https://onshape-public.github.io/docs/app-dev/webhook/) [документация]; практические проблемы (не приходит translation.complete, сложно проверить регистрацию) — [forum 14469](https://forum.onshape.com/discussion/14469/how-to-use-webhooks-for-translations), [comment 100698](https://forum.onshape.com/discussion/comment/100698/) [форум]
- Fusion Data API (GA, июль 2022): webhooks уведомляют серверное приложение при создании milestone; данные на тот момент read-only — [APS blog](https://aps.autodesk.com/blog/fusion-data-apis-are-now-generally-available); MFGDM: desktop API экспонирует `mfgdmModelId`, `timestamp`, событие `MFGDMDataReadyEvent` для согласования с GraphQL-сервисом — [MFGDMAPI_UM](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/MFGDMAPI_UM.htm) [документация]
- SolidWorks события: `DPartDocEvents.FeatureEditPreNotify` — начало редактирования определения фичи — [SW API 2019](https://help.solidworks.com/2019/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.DPartDocEvents_FeatureEditPreNotifyEventHandler.html); `RegenPostNotify2` — после rebuild/rollback (параметр — фича под rollback bar или null) — [SW API 2015](https://help.solidworks.com/2015/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.DPartDocEvents_RegenPostNotify2EventHandler.html); `EquationEditorPostNotify` — [SW API 2024](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.DPartDocEvents_EquationEditorPostNotifyEventHandler.html); разработчики не находят события «конец редактирования фичи» — [3DSwym](https://3dswym.3dexperience.3ds.com/question/solidworks-user-forum/featurepostedit-events-listener-in-sw-api_NLAQqB_QTBedUxU9Shb2og); события документа надо подписывать при активации документа, а не при загрузке add-in — [3DSwym](https://3dswym.3dexperience.3ds.com/question/solidworks-user-forum/registering-for-drawing-events-in-vb-net-addin_Y632pLbgQLqWHu2JENnB9Q) [документация/форум]
- KOMPAS API7 добавляет «события интерфейса» к API5 — [Habr 890110](https://habr.com/ru/articles/890110); данные в storage объекта удаляются при редактировании свойства в UI (риск потери внешних меток) — там же

### Inferences
- В SW практичный round-trip: add-in подписывается на `RegenPostNotify2`/`FeatureEditPreNotify`, после rebuild читает дерево (`GetTypeName2`, параметры фич) и диффит с манифестом; для KOMPAS — аналогично через события API7 либо пост-фактум сравнение модели по сохранённому файлу.
- Хранить идентификаторы фич манифеста в именах фич/пользовательских свойствах надёжнее, чем в storage (который в KOMPAS может быть удалён при правке свойства).

### Gaps
- Полный список событий KOMPAS API7 и их семантика — не найдены в открытых источниках.
- Существует ли `FeatureEditPostNotify` в SW — не подтверждено (не найдена страница).
- Современный статус webhooks на изменение дизайна в Fusion MFGDM — не подтверждён.

---

## Вопрос 8. Российская специфика: документация и сообщество по KOMPAS-3D API, nanoCAD API, автоматизация штампов ЕСКД

### Takeaway
Для KOMPAS-3D официальная документация — справка в SDK и PDF «KOMPAS-Invisible», а живое знание — блог АСКОН на Habr (цикл Норсеева по API5 на C++ Builder/Delphi, статьи о Python, KsAPI и Linux-порте) и форум АСКОН; штамп ЕСКД программно доступен через `ksStamp`. nanoCAD предлагает .NET/MultiCAD .NET/COM/LISP с переносимостью MultiCAD-приложений в AutoCAD; примеров автоматизации основной надписи ЕСКД для nanoCAD по API в открытом вебе не найдено.

### Cited Findings
- Документация KOMPAS API: справка в SDK (опция установки), PDF «Руководство пользователя KOMPAS-Invisible (API КОМПАС-3D)» на сайте АСКОН; ресурсы — блог АСКОН на Habr, цикл Норсеева, раздел прикладного программирования форума АСКОН — [Habr 890110](https://habr.com/ru/articles/890110)
- Цикл «Работа с API КОМПАС-3D» (Норсеев): ч.4 — основная надпись, ч.5 — сложные приёмы записи — [Habr 337288](https://habr.com/en/companies/ascon/articles/337288), [Habr 350516](https://habr.com/company/ascon/blog/350516); сборник статей kompas_3d — [Habr](https://habr.com/en/users/kompas_3d/articles/page4)
- Python + KOMPAS API7 (чертежи, штампы, техтребования) — [Habr 323078](https://habr.com/ru/articles/323078), код — [GitHub Weltraum](https://github.com/Weltraum/Article-Python-in-aid-of-the-designer-Tames-API-Kompas-3D)
- Linux-порт и KsAPI: API экспортных функций, API5, API7 — только Windows; KsAPI — C++, кроссплатформенный, главный поток; файлы Windows читаются в Linux — [Habr 860636](https://habr.com/ru/articles/860636)
- Учебные/научные материалы по API KOMPAS: [АСКОН sig_12.2011_mgu](https://ASCON.RU/source/articles/sig_12.2011_mgu.pdf), [БГТУ (Зинович)](https://elib.belstu.by/bitstream/123456789/43077/1/%d0%97%d0%b8%d0%bd%d0%be%d0%b2%d0%b8%d1%87_%d0%9f%d1%80%d0%b8%d0%bc%d0%b5%d0%bd%d0%b5%d0%bd%d0%b8%d0%b5.pdf), [СГУГиТ 2021](https://geosib.sgugit.ru/upload/geosibir/sborniki/2021/tom7-2/044-050.pdf)
- nanoCAD API: NrxGate/.NET, MultiCAD/.NET, COM (JScript/VBScript), LISP — [nanoCAD Help](https://nanocad.com/learning/online-help/software-extensions); MultiCAD .NET приложения работают в nanoCAD и AutoCAD (через MultiCAD Enabler, Клуб разработчиков) — [Habr/Нанософт 188326](https://habr.com/en/companies/nanosoft/articles/188326), [133723](https://habr.com/en/companies/nanosoft/articles/133723)
- KOMPAS STEP AP203/214/242 импорт/экспорт — [help.ascon.ru](https://help.ascon.ru/KOMPAS/24/en-US/990_glava123_obmen_informaciej_.html)

### Inferences
- Для русскоязычной команды наиболее воспроизводимый стек: KOMPAS API5/API7 через pywin32 по рецепту Habr 323078 + SDK-справка; штамп — `ksStamp`, при этом стиль оформления надо фиксировать явно.
- Будущая переносимость на Linux-KOMPAS потребует KsAPI (C++), что исключает текущий pywin32-путь.

### Gaps
- Прямой URL PDF «KOMPAS-Invisible» и актуальная версия SDK (v23/v24) не найдены в этой сессии.
- Нет публичных примеров автоматизации основной надписи ЕСКД для nanoCAD через API; СПДС/«Механика» не исследованы.
- Содержимое страницы ascon.net «3D Model Recognition» — не проверено.
