# Мировая практика: компоновка, PMI, дерево узлов, база связей

Собрано 2026-10-20 по обсуждению после M2.1 (универсальность от планки до большого насоса, вход от руки,
PMI как в NX, дерево компоновок, база данных). Выводы вошли в решения D22–D27 (`docs/architecture/02-decisions.md`)
и дорожную карту (`07-m2-2-graph-plan.md`). Ролик конструктора: «Черчение в NX. Урок 14. Технические условия
(PMI)», канал «Уроки NX» (расшифровку YouTube не отдал; содержание взято по устройству PMI в NX).

## Выводы

- **Стадии.** Pahl & Beitz: concept → embodiment → detail design, внутри embodiment — preliminary layout и
  definitive layout. VDI 2221: модульная структура, предварительные проекты модулей, общий проект (дерево
  компоновок). ЕСКД: эскизный проект, технический проект, рабочая документация. ASME Y14.24: conceptual design
  layout, design approval layout, detailed design layout, geometric study. Наше «Компоновка согласована» =
  design approval layout.
- **Модель как источник истины (MBD).** ASME Y14.41, ISO 16792, ГОСТ Р 2.052-2024: аннотации — данные,
  привязанные к геометрии; собраны в сохранённые виды с плоскостями аннотаций; чертёж производен. NX: PMI с
  видами модели, группа «Технические условия» (примечания, шероховатость, базы, допуски формы и расположения).
- **Скелет и распределение.** Creo (skeleton, publish/copy geometry, space claims) и NX WAVE (geometry linker,
  control structure): скелет публикует интерфейсы и объёмы, детали ссылаются на опубликованное, скелет
  перестраивается первым и не входит в спецификацию. Инженерия систем (NASA SE Handbook, ECSS): распределение
  требований и бюджетов вниз с запасами, ICD как контракт между соседями, сводка вверх, TPM. DSM (Eppinger,
  Browning): где резать дерево — по минимуму связей.
- **Хранение.** PLM (Teamcenter, Windchill, Aras) — реляционная база, связи как объекты, версии в логике
  приложения; Onshape — собственные микроверсии; новая волна — версии поверх графа объектов (Speckle: объекты по
  хешу и таблица замыканий; SysML v2 API: проекты, коммиты, ветки, теги над элементами и связями; TerminusDB;
  Dolt). Для заводов и плотин — ISO 15926 на RDF и BIM. Вывод: git с YAML уже даёт то, за чем идут остальные;
  не хватает запросов по связям → производный индекс в Postgres (D27).
- **Ввод от руки.** Free2CAD, CadVLM, CAD-Assistant показывают, что распознавание набросков — рабочая тема;
  для компоновки проще мультимодальная модель + наш рендер для проверки. Редакторы для web: Excalidraw (MIT,
  React-компонент), tldraw (водяной знак или платная лицензия), JSketcher / Chili3D / planegcs — эскизники с
  ограничениями, для профилей деталей позже.

## Методология проектирования

- Pahl G., Beitz W. Engineering Design: A Systematic Approach (Springer). Главы по embodiment design, чеклисты.
- VDI 2221 Blatt 1:2019 — <https://6sku3uaup9f9.din.de/en/technical-rule/vdi-2221-blatt-1/311603768>;
  Blatt 2 — <https://6sku3uaup9f9.din.de/en/technical-rule/vdi-2221-blatt-2/311603776>.
- ASME Y14.24, типы чертежей (слайды Gaston, DTIC) —
  <https://ndia.dtic.mil/wp-content/uploads/2008/technical/GastonEngineeringDrawingsY14_24a.pdf>;
  оглавление Y14.24-2020 — <https://www.asme.org/getmedia/2d6774a6-0321-4321-9875-67deec5f0341/Y14-24-2020-Table-of-Contents.pdf>.
- ГОСТ 2.103-2013 — <https://meganorm.ru/mega_doc/norm/gost_gosudarstvennyj-standart/2/gost_2_103-2013_mezhgosudarstvennyy_standart_edinaya_sistema.html>;
  ГОСТ 2.119-2013 — <https://ru.wikisource.org/wiki/ГОСТ_2.119—2013>;
  приказ о ГОСТ Р 2.052-2024 (вместо ГОСТ 2.052-2021 с 2026-01-01) — <https://pravo.ppt.ru/prikaz/rosstandart/n-1708-st-306513>;
  проект ГОСТ Р 2.053 (электронная структура изделия) — <https://test.tk482.ru/sites/default/files/downloads/or_gost_r_2.053_eskd._esi._osnovnye_polozheniya_v3.pdf>.

## MBD и PMI

- ISO 16792:2021, превью — <https://webstore.ansi.org/preview-pages/ISO/preview_ISO+16792-2021.pdf>;
  MBD и история ASME Y14.41 — <https://en.wikipedia.org/wiki/Model-based_definition>.
- Siemens NX: What's new in NX MBD — <https://blogs.sw.siemens.com/nx-design/whats-new-in-nx-model-based-definition/>;
  NX tips and tricks: PMI — <https://blogs.sw.siemens.com/designcenter/nx-tips-and-tricks-pmi/>;
  вебинар ATA «Principles and Workflows for PMI Using NX» — <https://ata-e.com/wp-content/uploads/2024/11/PMIWebinar_7June2016.pdf>;
  виды и камеры NX (документация HOOPS Exchange) — <https://docs.techsoft3d.com/exchange/latest/start/format/plm_nx_reader.html>.
- STEP AP242: фактшит ProSTEP — <https://www.prostep.org/mediathek/fact-sheets/iso-10303-242>;
  заметки STEP Tools по редакции 3 — <https://www.steptools.com/docs/stp_aim/notes_ap242e3.html>;
  рекомендации MBX-IF (PMI, внешние ссылки, структура) — <https://www.mbx-if.org/home/?p=194>.

## Top-down и инженерия систем

- Creo top-down design (содержание курса) — <https://caeuniversity.com/courses/top-down-design-tools/contents>;
  LEAP о скелетах и space claims — <https://leapaust.com.au/blog/?p=5216>;
  NX WAVE — <https://resources.skill-lync.com/branches/mechanical-engineering/questions/design-cad/nx-wave-geometry-linker>.
- NASA Systems Engineering Handbook — <https://www.nasa.gov/sites/default/files/atoms/files/nasa_systems_engineering_handbook_0.pdf>;
  NASA-HDBK-1009A (SysML, TPM) — <https://standards.nasa.gov/system/files/tmp/2025-03-12-NASA-HDBK-1009A.pdf>;
  MSFC-HDBK-3173 (лист распределения требований) — <https://standards.nasa.gov/sites/default/files/standards/MSFC/C/0/msfc-hdbk-3173_rev_c.pdf>.
- Eppinger S., Browning T. Design Structure Matrix Methods and Applications — <https://stuff.mit.edu/people/eppinger/SDE-MIT/DSM_Book.html>.

## Хранение данных изделия

- Speckle: схема объектов и хеширование — <https://docs.speckle.systems/developers/data-schema/object-schema>;
  таблица замыканий (обсуждение) — <https://speckle.community/t/speckle-2-0-stream-object-structure/1130/10>.
- SysML v2 API Cookbook (коммиты, ветки, теги, элементы) — <https://github.com/Systems-Modeling/SysML-v2-API-Cookbook>;
  клиент Python — <https://github.com/Systems-Modeling/SysML-v2-API-Python-Client>.
- TerminusDB — <https://terminusdb.com/?p=4332>; Dolt, сценарии — <https://dolthub.com/docs/introduction/use-cases>.
- Aras: связи как объекты — <https://community.aras.com/blog/labs/aras-fundamentals-customizing-relationships-with-the-relationshiptype/15877>;
  «где используется» — <https://docs.aras.com/aras-innovator-release-37/finding-where-used-and-comparing-sourcing-items-37>.
- Onshape: микроверсии и слияние — <https://www.onshape.com/en/blog/under-the-hood-how-collaboration-works>.
- Apache AGE поверх Postgres — <https://snowflake.com/en/blog/engineering/graph-queries-postgres-apache-age>;
  когда граф, а когда SQL — <https://www.resumelens.org/blog/sql/sql-graph-databases-vs-relational>.
- Autodesk Manufacturing Data Model через GraphQL — <https://autodesk.com/autodesk-university/ru/class/Explore-the-Power-of-the-Autodesk-Manufacturing-Data-Model-and-APIs-Using-GraphQL-2023>;
  ISO/TS 15926-11:2023 (RDF для промышленных объектов) — <https://www.iso.org/es/contents/data/standard/07/90/79005.html>.

## Ввод от руки и редакторы для web

- @excalidraw/excalidraw (MIT) — <https://npmjs.com/@excalidraw/excalidraw>; лицензия tldraw — <https://tldraw.dev/legal/tldraw-license>;
  JSketcher — <https://github.com/xibyte/jsketcher>; planegcs (солвер FreeCAD в WebAssembly) —
  <https://cdn.jsdelivr.net/npm/@salusoft89/planegcs@1.1.7/README.md>; Chili3D (AGPL) — <https://github.com/xiangechen/chili3d>.
- SketchGraphs — <https://arxiv.org/pdf/2007.08506>; Free2CAD — <https://geometry.cs.ucl.ac.uk/projects/2022/free2cad/>;
  CadVLM — <https://arxiv.org/pdf/2409.17457>; CAD-Assistant — <https://alphaxiv.org/overview/2412.13810v3>;
  мультиагентный набросок в CAD (Honda) — <https://alphaxiv.org/overview/2503.04417v1>;
  обзор Geometric Deep Learning for CAD — <https://arxiv.org/pdf/2402.17695>.
