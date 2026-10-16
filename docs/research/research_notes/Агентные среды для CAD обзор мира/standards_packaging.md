# Упаковка инженерных стандартов (ГОСТ/ЕСКД, ISO, DIN, ASME, JIS, GB) в CAD и design-check ПО: библиотеки, чертёжные стандарты, движки правил, строительные нормы, i18n (состояние на 2026)

Дата исследования: 2026-10-12. Все формулировки о правовом статусе данных стандартов помечены «needs lawyer» — это не юридическое заключение.

---

## КВ1. Библиотеки стандартных изделий и материалов: форматы данных, выбор стандартов по регионам, лицензии данных

### Takeaway
Коммерческие CAD поставляют стандартные изделия как отдельные устанавливаемые/лицензируемые «библиотеки по стандарту» (Inventor: отдельные библиотеки ANSI/DIN/GOST/ISO/JIS&GB, причём GOST единственная не ставится по умолчанию; SolidWorks Toolbox: ANSI/AS/GB/BSI/CISC/DIN/ISO/IS/JIS/KS без GOST; KOMPAS: платное приложение «Стандартные изделия» по ГОСТ/ОСТ 92/ISO/DIN). Open-source проекты (BOLTS, FreeCAD Fasteners) хранят таблицы размеров как YAML/CSV под LGPL/GPL без явной политики по авторскому праву на таблицы стандартов; GOST-покрытие в них минимально (2 стандарта в Fasteners WB).

### Cited Findings

**SolidWorks Toolbox / Design Library / Hole Wizard**
- Официальная справка SOLIDWORKS (2013–2022) перечисляет поддерживаемые стандарты Toolbox: ANSI, AS, GB, BSI, CISC, DIN, ISO, IS, JIS, KS; GOST и MIL в списке отсутствуют — [SOLIDWORKS Toolbox Overview 2022](https://help.solidworks.com/2022/English/SolidWorks/toolbox/c_toolbox_overview.htm)
- Стандарты включаются/отключаются в утилите Toolbox Settings; одна и та же БД обслуживает Toolbox и Hole Wizard — [Javelin: Create a New Standard in Hole Wizard/Toolbox](https://www.javelin-tech.com/blog/?p=2515)
- Чтобы изменить значения в стандарте, нужно создать пользовательский (custom) стандарт копированием существующего; переименовать/удалить можно только custom-стандарты — [SOLIDWORKS Help: Custom standards](https://help.solidworks.com/2019/english/solidworks/toolbox/t_tbx_standards_custom.htm); [DraftSight Mechanical: Manage Toolbox standards](https://help.solidworks.com/2025/english/DraftSight/DraftSightMech/mech_tb/c_manage_toolbox_standards.htm)
- Добавление своих деталей: Toolbox Settings → Customize Your Hardware → ПКМ по папке; администратор управляет правами на добавление в общую библиотеку — [SOLIDWORKS Help: Adding parts](https://help.solidworks.com/2021/English/SolidWorks/toolbox/t_toolbox_adding_parts.htm)

**Autodesk Inventor Content Center**
- Inventor 2026: отдельные библиотеки ANSI, DIN, GOST, ISO, «JIS & GB» (объединённая), плюс Feature Generators, Inventor Custom, Parker, Routed Systems, Sheet Metal, IDF; «Other Standard Content» объединяет AFNOR, AS, BSI, CNS, CSN, GOST, IS, KS, PN, SFS, SS, STN, UNI. «Все библиотеки, кроме GOST, устанавливаются по умолчанию» — [Autodesk Help: About Content Center Libraries (2026)](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Install/files/GUID-61015D87-8EF5-4EE3-A612-ECAFE1408850.htm)
- Добавить GOST к установленному Inventor: запустить DCLibrary64.msi с дистрибутива → Change → отметить GOST — [IMAGINiT: How to change which Content Center libraries are installed](https://resources.imaginit.com/manufacturing/how-to-change-which-inventor-content-center-libraries-are-installed)
- Desktop Content нельзя ставить на Vault-сервер и шарить по сети; для общего доступа — вариант Vault Server — [Autodesk Help (2026)](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Install/files/GUID-61015D87-8EF5-4EE3-A612-ECAFE1408850.htm)

**KOMPAS-3D «Стандартные изделия» (АСКОН)**
- В прайс-листе приложений АСКОН позиция «Стандартные Изделия: Детали, узлы и конструктивные элементы» описана как «изделия 2D и 3D по ГОСТ, ОСТ 92, ISO, DIN» (подшипники, детали машин, трубопроводная арматура, пневмо/гидро, сосуды и аппараты, станочные приспособления); отдельно «Стандартные Изделия: Электрические аппараты и арматура 3D», каталоги металлопроката/сортаментов — [АСКОН, прайс приложений MCAD&AEC (2024-10-16)](https://edu.ascon.ru/source/files/prices/MCAD&AEC_app_20241016.pdf); [прайс 2019](https://edu.ascon.ru/source/files/prices/MCAD&AEC_app_20190311.pdf)
- В составе дистрибутива КОМПАС-3D v24 модуль «Стандартные изделия» идёт отдельно — [cad.ru: KOMPAS-3D v24 docs](https://cad.ru/support/bz/download/docs/kompas3Dv24.pdf)
- Библиотека требует отдельной лицензии (в учебном пособии без неё предлагают рисовать отверстия штатными операциями) — [СФУ/СВГУ методичка](https://swsu.ru/sveden/files/Kompyyuternaya_grafika_v_mashinostroenii_MU_07_15.03.05.pdf)
- Исторически библиотеки крепежа КОМПАС-3D V8 Plus базировались на ISO 13584 (PartLib/PLIB); АСКОН также предлагает корпоративный Справочник «Стандартные изделия» для интеграции CAD/CAM/PDM/ERP — [БНТУ, лекция 7](https://nachertalka.bstu.by/files/books/lection_7.pdf)
- В презентации АСКОН о возможностях упоминаются изделия по ASME, DIN, ISO — [Основные возможности КОМПАС-3D (PDF)](https://bimacad.ru/content/uploads/2022/05/Osnovnye-vozmozhnosti-KOMPAS-3D.pdf)

**FreeCAD Fasteners Workbench**
- Данные хранятся в папке `FsData` как CSV-таблицы, имя файла = стандарт: `din933def.csv`, `iso10642def.csv`, `asmeb18.2.1.1def.csv`, `en1661def.csv`, `gost1144def.csv`, `gost11860def.csv`, `GN505def.csv`, `NFE27-619def.csv`, `PEMFasteners`, `PcbSpacer` и т.д. (~110 файлов видно; GOST — только 2) — [GitHub shaise/FreeCAD_FastenersWB/FsData](https://github.com/shaise/FreeCAD_FastenersWB/tree/master/FsData)
- Лицензия GPL-2.0; API `ScrewMaker.Instance().createFastener(type, diam, len, threadType, shapeOnly)`; в README нет заявления об источниках размеров и авторских правах на таблицы стандартов — [GitHub shaise/FreeCAD_FastenersWB](https://github.com/shaise/FreeCAD_FastenersWB)
- Иконки раскрашены по системе единиц: метрические — оранжевые, дюймовые — зелёные, BSP — синие — [FreeCAD Wiki: Fasteners Workbench](https://wiki.freecad.org/Fasteners_Workbench)

**BOLTS (Open Library of Technical Specifications)**
- Репозиторий переехал в github.com/boltsparts/boltsparts; лицензия репозитория GPL-3.0; бэкенды: FreeCAD, OpenSCAD, SolidWorks (через xlwt); папки `data`, `backends`, `bolttools`, `pythonpackage` — [GitHub boltsparts/boltsparts](https://github.com/boltsparts/boltsparts); OpenSCAD lists BOLTS as LGPL-2.1-or-later | GPL-3.0-only — [openscad.org/libraries](https://openscad.org/libraries.html)
- Данные: 18 коллекций `.blt` (batteries, bearings, connecting_bars, extrusions, flanges, hex, hex_socket, nut, pipes, profile_*, vacuum, washer) — [GitHub boltsparts data/](https://github.com/boltsparts/boltsparts/tree/main/data)
- Формат `.blt` (YAML, `blt-version: 0.4`): заголовок коллекции `id, name, description, author, license: "LGPL 2.1+"`, список `classes`; у класса `names`, `standards` (поля `body: ISO`, `standard: ISO 4032`, `labeling`, `replaces: DIN934`, `description`, у снятых — `status: withdrawn`), `parameters` (`free`, `defaults`, `types`, `description`, `tables` с `index/columns/data`, например `M3: [3, 5.5, 2.4, 6.01]`), `source: http://almetal.nl/...` (ссылка на источник таблицы — вторичный сайт поставщика, не сам стандарт) — [raw nut.blt](https://raw.githubusercontent.com/boltsparts/boltsparts/main/data/nut.blt)
- FreeCAD-интеграция — внешний верстак BOLTSFC (Addon Manager; зависимости python3 + pyyaml) — [FreeCAD Wiki: BOLTSFC Workbench](https://wiki.freecad.org/BOLTSFC_Workbench)

**CADENAS PARTsolutions / 3Dfindit / TraceParts**
- CADENAS: «более 700 сертифицированных каталогов производителей» (на другой странице — «более 600»); выгрузка в 100+ нативных и нейтральных форматов (CAD/CAE/BIM/ECAD) — [cadenas.de: available catalogs](https://cadenas.de/en/products/partsolutions/intelligent-standards-supplier-part-catalog/available-manufacturer-catalogs); [partsolutions.com AI info](https://partsolutions.com/about/ai-info/)
- Два уровня 3Dfindit в HiCAD: бесплатный даёт доступ к каталогам производителей с контрактом на скачивание, **платный добавляет доступ к стандартам DIN/ISO/EN** — т.е. нормативные таблицы монетизируются отдельно от вендорских каталогов — [ISD HiCAD Help: 3dfindit / CADENAS](https://help.isdgroup.com/helponline/1033/2024/hicad/Subsystems/hicadsst/Content/WeitereSchnittstellen/Partsolutions.htm)
- TraceParts: «Licensed»-каталоги (ANSI, ASME, DIN, ISO, NF, MS…) требуют покупки онлайн-кредитов; каталоги производителей бесплатны. В июле 2017 TraceParts по требованию TraceParts France убрала европейские/национальные стандартные каталоги из своего Onshape-приложения — [techno-science.net: TraceParts](https://www.techno-science.net/fr/definitions/traceparts); [Onshape forum: certified product catalog](https://forum.onshape.com/discussion/6974/how-can-i-get-certified-product-catalog-in-the-3dx-app-back)

**Onshape Standard Content**
- Три семейства: ANSI, DIN, ISO (болты/винты, гайки, шайбы; DIN — ещё шпонки) + PEM; выбор фильтрами Standard → Category → Class → Component; «auto-size» по выбранному ребру/цилиндру; полный список деталей в приложении — [Onshape Help: Standard Content](https://cad.onshape.com/help/Content/standard_content.htm); [Onshape Standard Content Library (appendix)](https://cad.onshape.com/help/Content/standard_content_appx.htm)
- Standard Content существует только в сборках и недоступен из FeatureScript (ответ ментора на форуме, не официальная документация) — [Onshape forum: classify standard content in FS](https://forum.onshape.com/discussion/30327/classify-onshape-standard-content-in-fs)

**AutoCAD Mechanical content library (для сравнения)**
- «700 000+ стандартных деталей и элементов» для ISO, ANSI, DIN, JIS, BSI, CSN, GB; Content Manager позволяет добавлять свои детали; в 2027 «более 800 деталей обновлены до последней редакции» — [Autodesk: AutoCAD Mechanical overview](https://www.autodesk.com/products/autocad-mechanical/overview)

**Материалы (FreeCAD)**
- Карточки материалов FreeCAD `.FCMat`: в 0.18 — INI-формат (`[FCMat]`, `Name=, Father=, Density=, YieldStrength=`), с TEMPLATE.FCMat и локализованными именами по кодам ISO 639-1; в 1.0+ — YAML-подобный формат с секциями `General` (UUID, Name, License) и `AppearanceModels` (по описанию пакета freecad-material на PyPI) — [FreeCAD Release notes 0.18](https://wiki.freecad.org/Translations:Release_notes_0.18/48/en); [PyPI freecad-material](https://pypi.org/project/freecad-material/); [commit TEMPLATE.FCMat](https://gitea.suzanne.soy/suzanne.soy/FreeCAD/commit/84a88c4d2f359a2407a9e4c0319c781f1c830113)
- nanoCAD Механика 20: обновлённая база материалов «более 60 стандартов ГОСТ» — [cadmaster.ru cm_87_07](https://www.cadmaster.ru/assets/files/articles/cm_87_07.pdf)

**ISO 13584 (PLIB) как формальная модель библиотек деталей**
- ISO 13584 «Parts library» (TC 184/SC4): часть 42 — методология структурирования семейств деталей; часть 32 (OntoML) — обмен онтологиями/справочными словарями по общей модели ISO 13584/IEC 61360; часть 511 — справочный словарь крепёжных изделий; каждому элементу словаря — машиночитаемый идентификатор — [Wikipedia: ISO 13584](https://en.wikipedia.org/wiki/ISO_13584); [BSI: ISO 13584-32 OntoML](https://knowledge.bsigroup.com/products/industrial-automation-systems-and-integration-parts-library-implementation-resources-ontoml-product-ontology-markup-language-1)

### Inferences
- Во всех коммерческих системах «стандарт» = единица установки/лицензии (библиотека, профиль), а GOST — наиболее «опциональная» (Inventor не ставит по умолчанию; SolidWorks Toolbox не содержит вовсе). Это создаёт рынок для российских приложений (АСКОН, nanoCAD, CSoft).
- Open-source де-факто практика: таблицы размеров перепечатываются из вторичных источников (каталоги поставщиков, как `source:` в BOLTS) и распространяются под LGPL/GPL без явного разрешения органов стандартизации. Прецедент судебных претензий к BOLTS/Fasteners не найден (см. Gaps), но и правовой анализ в проектах отсутствует.
- Модель BOLTS (`standards[]` с `body`, `replaces`, `status: withdrawn`, `source`) — хороший минимальный прототип схемы «одна геометрия ↔ несколько стандартов разных органов и редакций».
- CADENAS и TraceParts монетизируют именно нормативные (DIN/ISO/ANSI) таблицы, а не вендорские — косвенное свидетельство того, что эти данные лицензируются у органов стандартизации (needs lawyer).

### Gaps
- Не найден официальный актуальный перечень стандартов (ГОСТ/ISO/DIN) и цены приложения «Стандартные изделия» КОМПАС-3D (PDF прайса не удалось извлечь текстом; страница kompas.ru не найдена поиском).
- Внутренний формат данных SolidWorks Toolbox (SWBrowser.sldedb — Access/SQL) и Inventor Content Center (SQL Server Express .mdf / desktop .idcl) не подтверждён первичными источниками в этом исследовании.
- Не найдена явная политика BOLTS/Fasteners по авторскому праву на таблицы стандартов (README BOLTS недоступен — 404 на raw).
- Не удалось получить документацию формата `.blt` с сайта BOLTS (страницы отдают пусто/404); описание формата основано на самом файле nut.blt.

---

## КВ2. Переключение чертёжных стандартов в CAD и упаковка шаблонов/основных надписей

### Takeaway
В SolidWorks и AutoCAD Mechanical чертёжный стандарт — переключаемый именованный профиль (ANSI/ISO/DIN/JIS/BSI/GOST/GB), который задаёт параметры аннотаций и может экспортироваться как пользовательский файл; шаблоны листа (рамки, основные надписи) живут отдельно от профиля. В FreeCAD TechDraw шаблон — обычный SVG (подмножество SVG Tiny) с полями `freecad:editable` и автозаполнением через `freecad:autofill` (1.0); готовых ГОСТ 2.104 шаблонов в официальной документации нет.

### Cited Findings
- SOLIDWORKS: Document Properties → Drafting Standard; «Overall drafting standard» — ANSI, ISO, DIN, JIS, BSI, GOST, GB + пользовательские; выбор общего стандарта меняет базовый стандарт каждого раздела; сохранить/загрузить/переименовать/копировать/удалить custom-стандарт (файл). В сохранённый стандарт входят Annotations, Dimensions, Centerlines, DimXpert, Tables, Views, Virtual Sharps; остальные свойства документа хранятся в шаблоне чертежа, не в стандарте — [SOLIDWORKS Help 2024: Drafting Standard](https://help.solidworks.com/2024/English/SolidWorks/Sldworks/HIDD_OPTIONS_DRAFTING_STD.htm)
- AutoCAD Mechanical toolset: 8 профилей стандартов (ANSI, BSI, CSN, DIN, GB, ISO, JIS, GOST) — стандарт управляет тем, как встроенные инструменты генерируют геометрию; при создании чертежа стандарт назначается автоматически; смена стандарта влияет только на новые объекты; часть переопределений блокируется валидацией (пример: ANSI ограничивает высоту текста 0.1/0.12/0.24) — обходится созданием custom-стандарта — [Autodesk Help: About Selecting a Drafting Standard (2024)](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-Mechanical/files/GUID-91A27BD0-3D48-49F1-B8D7-F6E10CA6D163.htm)
- AutoCAD Mechanical, сварные обозначения: поддержка ANSI/ASME Y14.3, нескольких редакций ISO 2553, DIN EN ISO 2553:2014 — символы создаются по активному стандарту — [Autodesk Help 2027: welding symbols](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Mechanical/files/GUID-F932CFCF-BFAC-4C13-B399-2B22E1A8718C.htm)
- FreeCAD TechDraw: шаблон — SVG-файл, редактируемый вне FreeCAD (Inkscape/текстовый редактор); задаёт формат листа, рамку, зоны, метки фальцовки, основную надпись; поля с атрибутом `freecad:editable`; с 1.0 — autofill по атрибуту `freecad:autofill`; рендерер поддерживает только SVG Tiny (градиенты/клиппинг ломаются; удалять `transform`) — [FreeCAD Wiki: TechDraw Templates](https://wiki.freecad.org/TechDraw_Templates); [TechDraw TemplateHowTo (ru)](https://wiki.freecad.org/TechDraw_TemplateHowTo/ru); [TechDraw TemplateGenerator (Python-макрос генерации SVG)](https://wiki.freecad.org/TechDraw_TemplateGenerator)
- nanoCAD: модуль «СПДС» — оформление по СПДС (ГОСТ 21.101), координационные оси, отметки уровней, автоотчёты, «Мастер объектов» для параметрических объектов, библиотека профилей/ЖБИ/крепежа «соответствует стандартам и сериям»; поддержка BCF — [Habr: Платформа nanoCAD](https://habr.com/ru/articles/805689); модуль «Механика» — оформление КД по ЕСКД и ЕСТД — [CSoft Omsk: Платформа nanoCAD](https://nanocad.csoftomsk.ru/platforma-nanocad)
- nanoCAD Механика: панель ЕСКД с MechWizard (Мастер объектов), база чертежей/3D стандартных изделий по ГОСТ (а также ISO, DIN, CSN по одному источнику), элементы параметрические и связаны зависимостями, определяемыми стандартами — [Habr (Нанософт)](https://habr.com/company/nanosoft/blog/346704); [cadmaster cm_89_06](https://www.cadmaster.ru/assets/files/articles/cm_89_06.pdf); nanoCAD Механика PRO — отдельное решение на отечественном 3D-ядре, годовая лицензия от 12 000 руб. (2024) — [normacs.info news 74598](https://www.normacs.info/news/74598)
- СПДС GraphiCS (CSoft): надстройка для AutoCAD / AutoCAD Architecture / ZWCAD (также nanoCAD) с 2000 г.; базовый документ ГОСТ 21.101-2020; все объекты используют векторный шрифт по ГОСТ 2.304-81; отдельные объекты для осей, выносок, отметок — [CSoft: SPDS GraphiCS брошюра](https://csdev.csd.ru/local/templates/csdev/upload/pdf/SPDS_GraphiCS.pdf); [cadmaster cm_90_19](https://www.cadmaster.ru/assets/files/articles/cm_90_19.pdf)
- Открытый шрифт по ГОСТ 2.304-81 — OpenGostFont (OFL-1.1, OTF/TTF, упакован в openSUSE и ALT Linux; исходники на Bitbucket) — [openSUSE OBS: opengost-fonts](https://build.opensuse.org/package/show/openSUSE/opengost-fonts); [ALT Linux: opengostfont](https://packages.altlinux.org/en/sisyphus/srpms/opengostfont/)

### Inferences
- Разделение «профиль стандарта (параметры аннотаций) ↔ шаблон листа (рамка/основная надпись)» — общая практика SolidWorks и AutoCAD Mechanical; в FreeCAD эта пара реализована как «preferences TechDraw» + «SVG template», без формального понятия «профиль стандарта».
- Для ГОСТ ЕСКД в open-source есть открытый шрифт (OpenGostFont), но нет канонического набора SVG-шаблонов ГОСТ 2.104 с autofill-полями — нишa для «пакета стандарта».

### Gaps
- Не найдено GitHub-репозитория с готовыми TechDraw-шаблонами ЕСКД (ГОСТ 2.104/2.301) — только общие инструкции wiki.
- Внутренний файловый формат custom drafting standard SolidWorks (.sldstd) и правила обмена между версиями не подтверждены первичным источником.
- Не выяснено, как KOMPAS внутренне хранит «стили оформления» (библиотеки стилей *.lyt/*.lcs) — источники не найдены в этом исследовании.

---

## КВ3. Движки правил / design checkers (SolidWorks Design Checker, DFMPro, aPriori, Check-Mate, Onshape, DriveWorks/Tacton, open-source)

### Takeaway
Промышленные чекеры объединяет одна модель: набор правил в файле (SolidWorks `.swstd`), каждое правило с параметрами, ссылкой на стандарт и уровнем критичности (Critical/High/Medium/Low или Info/Warning/Error), запуск интерактивно или пакетно, отчёт только по провалам, частичное автоисправление. Open-source аналоги для инженерных данных — buildingSMART IDS + IfcTester (BIM) и общие JSON-движки (json-rules-engine, GoRules ZEN/JDM).

### Cited Findings

**SOLIDWORKS Design Checker**
- Файл требований `.swstd`; категории: Document, Annotation, Dimension, Drawing Document, Part Document checks; способы создания: Build Checks (вручную), Learn Checks Wizard (из настроек открытого документа), Create Checks from Existing File (part/assembly/drawing/DWG как эталон) — [SOLIDWORKS Help 2021: Build Checks](https://help.solidworks.com/2021/english/SolidWorks/solidworks_design_checker/c_build_checks.htm); [Javelin: Learn Checks Wizard](https://www.javelin-tech.com/blog/2022/11/using-the-learn-checks-wizard-in-solidworks-design-checker/)
- Check Active Document: можно выбрать встроенные стандарты ANSI, ISO, DIN, JIS, BSI, GOST, GB или свои `.swstd`; результат — сообщение «соответствует» или список провалов по критичности — [SOLIDWORKS Help 2019: Check Active Document](https://help.solidworks.com/2019/english/SolidWorks/solidworks_design_checker/c_check_active_document.htm)
- Критичность задаётся в `.swstd` для каждого правила: Critical, High, Medium, Low; по умолчанию High; в Task Pane показываются только провалы, сгруппированные по критичности — [SOLIDWORKS Help 2018: Criticality Levels](https://help.solidworks.com/2018/English/SolidWorks/solidworks_design_checker/r_criticality_levels.htm); [SOLIDWORKS Tutorial 2025: Checking a Document](https://help.solidworks.com/2025/English/swtutorialonline/t_checking_document.htm)
- Пакетный запуск Tasks → Run Design Checker с «Auto correct all failures»; API `ISWDesignCheck.RunDesignCheck5` формирует отчёт с группировкой Critical/High/Medium/Low до и после коррекции — [SOLIDWORKS API: RunDesignCheck5](https://help.solidworks.com/2015/English/api/dsgnchkapi/SOLIDWORKS.Interop.dsgnchk~SOLIDWORKS.Interop.dsgnchk.ISWDesignCheck~RunDesignCheck5.html)

**Siemens NX Check-Mate**
- Расположение: Developer → HD3D tools; область: текущая деталь / все загруженные / все в папке; библиотека готовых проверок (информация, моделирование, сборки, PMI, требования); пользователь настраивает значения и выбирает уровень результата — information / warning / error — [Siemens blog: Out of the box testing with NX Check-Mate](https://blogs.sw.siemens.com/nx-design/learn-more-about-checks-with-out-of-the-box-testing-with-nx-check-mate)
- Fact sheet: проверка модели, сборки, файла, чертежа; авторинг собственных проверок; HTML-отчёты; интерактивный и batch-режимы — [Siemens: Check-Mate QuickCheck fact sheet](https://www.plm.automation.siemens.com/cz_cz/Images/fs_checkmate_quickcheck_tcm841-11882.pdf)
- Июнь 2021 — проверки на NX/Open; июнь 2023 — Checker Editor на базе logic-editor (без программирования); новый Quality Dashboard заменил Java Qdashboard — [Siemens: What's new in NX June 2023 Validation](https://blogs.sw.siemens.com/nx-design/whats-new-in-nx-june-2023-validation/)

**HCL DFMPro и aPriori**
- DFMPro — add-in внутри SOLIDWORKS, Creo, 3DEXPERIENCE, NX (по одному источнику — также CATIA V5); библиотеки правил по процессам (CNC, листовой металл, литьё под давлением, литьё); пороги правил настраиваются под возможности поставщика; отчёт с привязкой к геометрии — [HCL Software: DFMPro](https://hclsoftwareu.hcltechsw.com/dfmpro); [DFMPro brochure](https://www.hcltech.com/sites/default/files/documents/resources/brochure/files/dfmpro-brochure_0.pdf)
- aPriori — не правила pass/fail, а симуляция процесса производства по CAD-модели (DFM, стоимость, цикл, углеродный след); «более 15 типов процессов», buyer's guide — 440+ процессов — [aPriori DFM+](https://www.apriori.com/dfm-plus); [aPriori DFM Buyers Guide 2026](https://www.apriori.com/wp-content/uploads/2026/04/DFM-Buyers-Guide.pdf)

**Onshape**
- Собственного «design checker» не найдено; валидация — через Release Management: обязательные свойства (workspace/version), правила утверждающих (Professional/Enterprise), кастомные workflow в JSON (`requireApprover`, блокировка перехода In Review → Released без комментария) — [Onshape tech tip: enforce required properties](https://www.onshape.com/en/resource-center/tech-tips/enforce-required-properties-release-management-workflows); [Onshape Help: Designing Release Management Processes](https://cad.onshape.com/help/Content/Release/designing_release_management_processes.htm)

**KBE/конфигураторы**
- DriveWorks — правила «как в электронных таблицах», логика и вычисления без кода, ориентирован на SOLIDWORKS — [DriveWorks Pro (SOLIDWORKS partner)](https://www.solidworks.com/partner-product/driveworks-pro); [fitgap: DriveWorks](https://us.fitgap.com/products/000580/driveworks)
- Tacton — constraint-based solver (вывод допустимых конфигураций из ограничений, а не if-then скрипты); Tacton Design Automation внутри SolidWorks, Creo, Inventor — [TrustRadius: Tacton Design Automation](https://www.trustradius.com/products/tacton-design-automation); [dezignstuff: TactonWorks](https://dezignstuff.com/?p=6329)

**KOMPAS-Expert (АСКОН)**
- Отдельный инструмент проверки документов: примеры проверок — размер не ассоциирован с геометрией, длина ребра меньше допустимой, недопустимое значение шероховатости; результат — список ошибок — [АСКОН: KOMPAS-Expert (презентация)](https://sd.ascon.ru/ftp/Public/%d0%9f%d1%80%d0%b5%d0%b7%d0%b5%d0%bd%d1%82%d0%b0%d1%86%d0%b8%d0%b8_%d0%9d%d0%9f%d0%9e%20%d0%9c%d0%b0%d1%88%d0%b8%d0%bd%d0%be%d1%81%d1%82%d1%80%d0%be%d0%b5%d0%bd%d0%b8%d1%8f/KOMPAS-Expert.pdf)

**Open-source движки правил**
- buildingSMART IDS — машиночитаемый XML-стандарт для спецификаций информационных требований к IFC; схема `Schema/ids.xsd`, User Manual и Implementers Documentation в репозитории — [GitHub buildingSMART/IDS](https://github.com/buildingSMART/IDS)
- IfcTester (IfcOpenShell) — Python-библиотека/CLI/веб-приложение для записи/чтения IDS и проверки IFC-моделей с отчётами в нескольких форматах; пример: спецификация «стены должны иметь свойство LoadBearing» → XML → валидация IFC — [PyPI ifctester](https://pypi.org/project/ifctester/0.0.240318/)
- json-rules-engine (npm, v7.3.x): правило = `conditions` (`all`/`any`/`not`, рекурсивно) + `event` (`type`, `params`); условие = `{fact, operator, value}`; `priority` (выше — раньше); факты статические или асинхронно вычисляемые; результат `run()` — сработавшие события + almanac — [GitHub cachecontrol/json-rules-engine walkthrough](https://github.com/cachecontrol/json-rules-engine/blob/HEAD/docs/walkthrough.md); [npm json-rules-engine](https://npmjs.com/package/json-rules-engine)
- GoRules ZEN Engine — Rust-ядро, биндинги Node/Python/Go/Java, MIT; формат JDM — решение как JSON-граф узлов (Input → decision tables/expressions → Output); есть open-source React-редактор графов — [PyPI zen-engine](https://www.pypi.org/project/zen-engine); [docs.rs zen-engine](https://docs.rs/crate/zen-engine/latest)

### Inferences
- Общий «контракт» правила у зрелых систем: `id → категория → параметры/пороги → ссылка на стандарт/профиль → критичность → автоисправление (опц.) → отчёт только по провалам с привязкой к элементу`. Это и есть искомая UX-модель «rule → reference → element → severity».
- IDS — наиболее близкий open-source прецедент именно инженерного (не бизнес-) формата правил: XML-схема, стандартизированная отраслевым органом, с независимыми реализациями (IfcTester и коммерческие). Для MCAD аналога нет.
- Тренд 2021–2023 у Siemens (NX/Open → no-code Checker Editor) и у SolidWorks (Learn Checks из эталонного документа) — снижение порога авторинга правил инженерами без программирования.

### Gaps
- Не найден полный перечень проверок Check-Mate и формат хранения пользовательских чекеров.
- Внутренняя структура `.swstd` (бинарный/XML) не подтверждена первичным источником.
- Актуальная версия IDS (1.0?), лицензия схемы и официальный список реализаций не получены (GitHub-страница без релизов; technical.buildingsmart.org — 403).
- Нет подтверждения существования встроенного автоматического нормоконтроля ЕСКД в самом КОМПАС-3D (помимо KOMPAS-Expert).

---

## КВ4. Строительные нормы как программные пакеты (Eurocode / AISC / СП 16.13330) и версионирование редакций норм

### Takeaway
Open-source Python-экосистема (steelsnakes, structuralcodes, pyaisc, eurocodepy, sectionproperties, PyNite, forallpeople) версионирует нормы через **структуру модулей по региону и редакции** (`steelsnakes/UK/checks`, `codes/ec2_2004` vs `codes/ec2_2023`, `pyaisc/src/v13`), привязывая тесты к официальным примерам (AISC Design Examples v16.0). Для СП 16.13330 open-source пакетов не найдено — только коммерческие надстройки (Dlubal) и закрытые программы АРСС. Нормы сами по себе версионируются «поколениями» с периодом сосуществования (Eurocode 2-го поколения: публикация до 30.09.2027, отзыв конфликтующих национальных стандартов 30.03.2028).

### Cited Findings
- **steelsnakes** (GPL-2.0, WIP): модули по регионам — EU (EN 1993-1-1), UK (EC3 + UK NA; отдельный модуль `BS` для BS 5950-1:2000 на тех же сечениях), US (`US` imperial / `US_Metric` SI; члены по AISC 360-22, тесты воспроизводят AISC Design Examples v16.0; главы разбиты на модули tension/compression/flexure/shear/combined/stability), IN (IS 800/808, PoC), AU/NZ (хуки). `SectionDatabase` автообнаруживает региональные JSON с нечётким поиском обозначений; **единицы не реализованы** — пользователь отвечает за согласованность — [steelsnakes docs](https://steelsnakes.readthedocs.io/)
- **structuralcodes** (fib International): структура `codes/ec2_2004`, `codes/ec2_2023`, `codes/mc2010` (материалы, сдвиг, трещины, ползучесть/усадка) + `materials/`, `geometry/`, `sections/`; есть страница Versioning; фокус — Eurocode 2 и fib Model Code — [structuralcodes docs](https://fib-international.github.io/structuralcodes/); [PyPI structuralcodes](https://pypi.org/project/structuralcodes)
- **pyaisc** (MIT, 6 коммитов): главы B, D, E, F, G, H, I AISC Manual, редакции 13–15; директория `src/v13` — редакция как подпакет; соединения главы J — в отдельном пакете — [GitHub mwhit74/pyaisc](https://github.com/mwhit74/pyaisc)
- **eurocodepy**: пакет расчётов по Eurocode с встроенной базой стальных профилей (`ec.SteelBeam('HEA200')`) — [PyPI eurocodepy](https://pypi.org/project/eurocodepy/0.1.46/)
- **blue-prints** (LGPL-2.1): AEC-библиотека с проверками по Eurocode 3 и дисклеймером об ответственности пользователя — [PyPI blue-prints](https://pypi.org/project/blue-prints)
- **StruPy / Struthon** — старые пакеты с модулем болтов (StruPy 0.5.1) и приложением болтового соединения (Struthon 0.5.1); **steelas** — AS 4100:2020; **steeltoolbox** — MIT, последний релиз 2017 — [PyPI strupy](https://pypi.org/project/strupy); [PyPI struthon](https://pypi.org/project/struthon); [steelas docs](https://steel-as.readthedocs.io/); [PyPI steeltoolbox](https://pypi.org/project/steeltoolbox)
- **sectionproperties** (MIT): МКЭ-анализ произвольных сечений; публикация в JOSS 2024; последний push ~8 мес. назад — [GitHub StructuralPython/section-properties](https://github.com/StructuralPython/section-properties)
- **PyNite**: 3D/2D статический анализ, P-Δ; обзор экосистемы (вместе с OpenSeesPy) — [Viktor.ai: 5 Python libraries for structural engineers](https://viktor.ai/blog/177/5-powerful-python-libraries-every-structural-engineer-should-know)
- **forallpeople** — библиотека единиц СИ для инженеров: автосокращение размерностей, «structural» environment (`si.environment('structural')`), пользовательские окружения в JSON, обработка «скрытых размерностей» формул норм (√MPa) через множитель-единицу; используется с handcalcs — [PyPI forallpeople 2.4.2](https://pypi.org/project/forallpeople/2.4.2/); [PyPI forallpeople 1.2.0](https://pypi.org/project/forallpeople/1.2.0/)
- **СП 16.13330**: open-source Python не найден. Коммерческие: Dlubal RFEM 6/RSTAB 9 — надстройка проверки стержней по СП 16.13330 (1-я и 2-я группы предельных состояний) — [Dlubal: СП 16.13330](https://www.dlubal.com/ru/img/059313); программа АРСС «Подбор сечений стального проката» по СП 16.13330.2017 и СТО АРСС 11251254.001-018-3 — [normacs.info projects 7393](https://www.normacs.info/projects/7393); действует СП 16.13330.2017 с Изменением № 6 Минстроя — [normacs.info news 76202](https://www.normacs.info/news/76202)
- **Версионирование норм (Eurocode 2-е поколение)**: BS EN 1993-1-1:2022 заменяет BS EN 1993-1-1:2005+A1:2014, отзыв 30.03.2028; CEN/TC 250: латест-дата публикации 30.09.2027, отзыв конфликтующих нац. стандартов 30.03.2028; период сосуществования 2023–2028; смешение поколений допустимо «с осторожностью» без снижения надёжности; стандарт применяется только вместе с National Annex — [BSI Knowledge: Eurocode 3 joints](https://knowledge.bsigroup.com/products/eurocode-3-design-of-steel-structures-design-of-joints/standard); [CEN/TC 250 document (certifico)](https://certifico.com/component/attachments/download/37265)

### Inferences
- Де-факто стандарт версионирования в open-source: **редакция нормы = подпакет/модуль** (`ec2_2004` / `ec2_2023`, `v13`), а **национальное приложение = регион-модуль** (UK vs EU). Нигде не найден формальный механизм «edition selector + дата применимости» на уровне данных; это делается структурой кода.
- Единицы — слабое место: steelsnakes отказывается от unit-awareness; forallpeople/pint — отдельный слой, который пакеты норм не интегрируют.
- Для российских норм (СП 16, СП 20 и т.д.) open-source ниша пуста; при этом тексты СП публикуются Минстроем и доступны в PDF (см. КВ6 о правовом статусе).

### Gaps
- Не найдено open-source Python-пакетов для расчёта сварных швов и групп болтов по EN 1993-1-8 / AISC J с подтверждённой функциональностью (steelsnakes заявляет соединения «в планах»).
- Не удалось получить страницу Versioning structuralcodes и подтвердить строковые идентификаторы кодов (`set_design_code`).
- Не найдено open-source реализаций СП 16.13330 / СП 20.13330 на GitHub (поиск на русском дал только коммерческие продукты).

---

## КВ5. i18n и мульти-стандартность в open-source инженерных инструментах (единицы, локаль, редакции)

### Takeaway
В FreeCAD мульти-стандартность реализована слоями: глобальные «unit schemas» (Standard, MKS, US customary, Imperial decimal, Building Euro (cm), Building US (ft-in-fraction) и др.) в Preferences без per-document единиц; локализация имён материалов через ISO 639-1 коды в FCMat; переводы через Crowdin; стандарт крепежа — через выбор таблицы (имя файла CSV = стандарт). Структурные Python-пакеты решают регион через модули, а единицы — внешними библиотеками (forallpeople/pint).

### Cited Findings
- FreeCAD: пользователь задаёт предпочитаемую unit-schema в Preferences, она отвечает за преобразование отображения; `getValueAs()` — принудительное получение в заданной единице — [FreeCAD Wiki: Quantity](https://wiki.freecad.org/Quantity/de)
- Схемы «US building (feet + inches + fraction)» и «Building Euro (всё в см, площади/объёмы в м)» добавлены отдельными коммитами; Draft при схеме 5 использует специальное представление размеров — [commit US building](https://gitea.suzanne.soy/suzanne.soy/FreeCAD/commit/ad92a2df25c03805b3f782cc79a743e972f81f94); [commit Building Euro](https://gitea.suzanne.soy/suzanne.soy/FreeCAD/commit/ee9452a8eec89b76e55a52573eee2e0b06ddc754); [commit fix Building-US](https://gitea.suzanne.soy/suzanne.soy/FreeCAD/commit/d6f31d5c4b673ae87df0e113724de9fa34cf4d63)
- Настройка «Minimum fractional inch» от 1/2" до 1/128", по умолчанию 1/8" — [hobby-machinist форум](https://hobby-machinist.com/threads/freecad-gorgeous-i-am-a-little-intimidated.86448/page-5)
- Per-document единицы в FreeCAD невозможны; обход — отдельные конфиги и запуск с `--user-cfg` — [Codidact: FreeCAD units per document](https://powerusers.codidact.com/posts/289060)
- Известный баг: привязки/сетка Draft остаются в мм после переключения на imperial (0.16, подтверждён на 0.20) — [FreeCAD tracker #1951](https://tracker.freecad.org/view.php?id=1951)
- FCMat TEMPLATE использует двухбуквенные коды ISO 639-1 для локализованных имён — [commit TEMPLATE.FCMat](https://gitea.suzanne.soy/suzanne.soy/FreeCAD/commit/84a88c4d2f359a2407a9e4c0319c781f1c830113)
- Fasteners WB: раскраска иконок по системе единиц (metric/inch/BSP) — [FreeCAD Wiki: Fasteners Workbench](https://wiki.freecad.org/Fasteners_Workbench)
- steelsnakes: регионы как модули (EU/UK/US/US_Metric/IN/AU/NZ), US и US_Metric — раздельные модули под imperial/SI; единицы не реализованы — [steelsnakes docs](https://steelsnakes.readthedocs.io/)
- forallpeople: окружения единиц задаются JSON, есть предустановленное `structural` — [PyPI forallpeople](https://pypi.org/project/forallpeople/2.4.2/)
- Fasteners WB имеет TRANSLATIONS.md (перевод UI) — [GitHub shaise/FreeCAD_FastenersWB](https://github.com/shaise/FreeCAD_FastenersWB)

### Inferences
- Ни один из рассмотренных open-source инструментов не связывает «локаль/регион» с автоматическим выбором набора стандартов (например, ru-RU → ГОСТ + ЕСКД + СП): выбор стандарта и выбор единиц — независимые ручные настройки.
- Удачный паттерн из FreeCAD: именованные «схемы» (unit schema) как переключаемые пресеты — его можно обобщить до «схемы стандарта» (единицы + оформление + библиотеки + нормы).

### Gaps
- Не найдено описания механизма локализации стандартов в KiCad/BOLTS (кроме UI-переводов).
- Не исследованы i18n-подходы в OpenSCAD/Blender-CAD-аддонах и LibreCAD.

---

## КВ6 (ключевой вопрос «Legal»). Какие данные стандартов можно поставлять открыто; как проекты обходят ограничения

### Takeaway
ISO и DIN однозначно трактуют свои стандарты как охраняемые и лицензируют даже внутрикорпоративное копирование и встраивание в ИИ/ПО; руководство Стандартинформа заявляло, что все ГОСТ Р ИСО / ГОСТ ISO защищены авторским правом, а исключительное право официального опубликования национальных стандартов принадлежит национальному органу. Национальные ГОСТ в ст. 1259 п. 6 ГК РФ явно не названы (упомянуты «законы, другие нормативные акты»), закон 162-ФЗ/приказ Минпромторга № 1730 обязывают публиковать в свободном доступе лишь часть документов (стандарты из перечней к НПА, основополагающие, классификаторы), остальные — платно. Open-source проекты (BOLTS, Fasteners, KiCad) обходят вопрос, публикуя **производные таблицы** из вторичных источников под LGPL/GPL/CC-BY-SA без явного правового анализа. Всё ниже — **needs lawyer**.

### Cited Findings

**ISO**
- Весь контент ISO охраняется авторским правом и принадлежит ISO; копирование, даже частичное, требует письменного разрешения ISO Central Secretariat или национального члена ISO — [ISO: Copyright](https://www.iso.org/copyright.html?lang=2)
- End Customer Licence Agreement (обновлён 2026-05-29): воспроизведение бумажной публикации в любой форме требует предварительного письменного разрешения; публикации защищены авторским, базо-данных, товарно-знаковым правом; вопросы — copyright@iso.org — [ISO: Terms and conditions / licence agreement](https://www.iso.org/terms-conditions-licence-agreement.html)
- OBP Terms of Use (2026-09-18): «ISO Content» = публикации и Digitally Enhanced Content; принадлежат ISO; лицензирование — licensing@iso.org — [ISO OBP Terms](https://www.iso.org/home/store/iso-obp-terms.html)
- POCOSA 2017 (резолюция Council 08/2017 от 15.03.2017) — политика распространения публикаций ISO и защиты авторского права, включая национальные адаптации; члены обязаны защищать ИС ISO в своих странах — [law.resource.org: Statement of Intervention Annex (2020)](https://law.resource.org/pub/eu/docket/2020-01-20.Statement%20of%20Intervention%20Annex.pdf); [GSO course on POCOSA 2017](https://www.gso.org.sa/tr/course/2019114?lang=en)
- Исторический прецедент 2003 г.: предложение ISO брать плату за встраивание кодов ISO 3166/4217/639 в ПО вызвало протест и не было реализовано — [xml.coverpages.org](https://xml.coverpages.org/ni2003-09-20-a.html); [consortiuminfo.org](https://consortiuminfo.org/?p=1078)

**DIN**
- DIN Media Netzwerklizenz: разрешает воспроизведение норм только внутри предприятия для собственных нужд за ежегодную плату; передача внешним третьим лицам не покрывается — [Beuth/DIN Media: Netzwerklizenzen (PDF)](https://www.beuth.de/resource/blob/1058270/64c04bef43bde07e42a4490a25c6565e/beuth-netzwerklizenzen-wp-data.pdf)
- Отдельная KI-Lizenz для использования норм в ИИ-системах: требует членства DIN, сетевой лицензии и изолированной ИИ-среды; цена по запросу; сами тексты норм покупаются отдельно («платят трижды») — [IWW: DIN-Normen und KI](https://www.iww.de/pbp/planungsleistungen/din-normen-wer-normen-mit-kuenstlicher-intelligenz-nutzen-will-zahlt-dreimal-f174541)
- DIN Media предлагает структурированные данные норм как Datenservice — [dinmedia.de: Datenservice](https://www.dinmedia.de/de/normen-management/datenservice)

**ГОСТ / Россия**
- ГК РФ ст. 1259 п. 6: не являются объектами авторских прав официальные документы государственных органов и органов местного самоуправления, «в том числе законы, другие нормативные акты, судебные решения», их официальные переводы, а также официальные документы международных организаций; государственные символы; фольклор; сообщения о событиях и фактах. Стандарты/технические нормы явно не названы — [Викитека: ст. 1259 ГК РФ](https://ru.wikisource.org/wiki/Ст._1259_ГК_РФ)
- Руководитель Стандартинформа (В.А. Витушкин): «Абсолютно все ГОСТ Р ИСО и ГОСТ ISO защищены авторским правом. Распространение этих документов без согласия ИСО и/или национального органа по стандартизации является нарушением»; перевод стандартов — только с разрешения международных/региональных организаций — [normacs.info news 57722](https://www.normacs.info/news/57722)
- Тот же источник: «исключительное право официального опубликования и распространения национальных стандартов и общероссийских классификаторов принадлежит национальному органу по стандартизации»; Федеральный информационный фонд стандартов — единственный официальный источник; должна быть предусмотрена ответственность за неправомерное распространение — [normacs.info news 57722](https://www.normacs.info/news/57722); [gostinfo.ru](https://www.gostinfo.ru/InformationOfStandardization/Details/1810)
- 162-ФЗ «О стандартизации в РФ» (от 29.06.2015, в силе с 29.09.2015); ст. 8 → приказ Минпромторга от 27.05.2016 № 1730 о порядке свободного доступа к документам НСС (в силе с 01.07.2016); из перечня открытого доступа убраны общероссийские классификаторы (по данным NormaCS); на этапе обсуждения Росстандарт считал, что за предоставление стандартов нужно брать плату — [normacs.info news 44249](https://www.normacs.info/news/44249); [pravo.ppt.ru: приказ 1730](https://pravo.ppt.ru/prikaz/minpromtorg/n-1730-85917); Федеральный информационный фонд стандартов — ст. 29 162-ФЗ, оператор ФГУП «СТАНДАРТИНФОРМ» — [normacs.info discussions 2574](https://www.normacs.info/discussions/2574)
- Порядок доступа (КонсультантПлюс, разъяснение по закупкам): в свободном доступе на сайте Росстандарта публикуются национальные стандарты из перечней, на которые ссылаются НПА, основополагающие стандарты и правила стандартизации, классификаторы и ИТС; органам власти/Росатому/судам копии бесплатно в 15 рабочих дней, остальным — за плату; иные документы — через оператора ФГУП «СТАНДАРТИНФОРМ» или его партнёров — [consultant.ru: доступ к документам по стандартизации](https://www.consultant.ru/document/cons_doc_LAW_211913/ab45a9083d740a166b9258e803b0d450d0e6e61a/)
- Судебное дело 2005–2006 (СПб городской суд) по обязанности агентства публиковать стандарты: апелляция сочла обязанность ограниченной публикацией новых документов «на время, необходимое для ознакомления»; практика protect.gost.ru — просмотр с защитой от сохранения (жалобы пользователей) — [linux.org.ru обсуждение](https://www.linux.org.ru/forum/talks/2418701); [securitylab: доступ к ГОСТам затруднили](https://www.securitylab.ru/news/301586.php); [cnews](https://cnews.ru/link/a1692)

**Как обходят open-source проекты**
- BOLTS: таблицы под LGPL 2.1+, поле `source:` указывает на сайт поставщика (almetal.nl), а не на текст стандарта; стандарты упоминаются как метаданные (`body`, `standard`, `replaces`, `status`) — [raw nut.blt](https://raw.githubusercontent.com/boltsparts/boltsparts/main/data/nut.blt)
- FreeCAD Fasteners: CSV-таблицы с именами стандартов под GPL-2.0 без заявления об источниках — [GitHub shaise/FreeCAD_FastenersWB](https://github.com/shaise/FreeCAD_FastenersWB)
- KiCad libraries: CC-BY-SA 4.0 с исключением — share-alike не применяется к проектам, использующим библиотеку, и к сгенерированным из них файлам; при редистрибуции коллекций (в т.ч. модифицированных) — та же лицензия и атрибуция; применение исключения к отдельно вынесенным библиотекам «не подтверждено юристами и не проверено судом» (форум) — [KiCad LICENSE.md (зеркало)](https://portrait.gitee.com/KiCAD-CN/kicad-symbols/blob/master/LICENSE.md); [Debian copyright kicad-symbols](https://tracker.debian.org/media/packages/k/kicad-symbols/copyright-10.0.4-1); [KiCad forum: library license](https://forum.kicad.info/t/kicad-library-license-and-design-local-libraries/32114)
- OpenGostFont: открытый шрифт по ГОСТ 2.304-81 под OFL-1.1 — пример «реализации стандарта» (а не копии текста), распространяемой свободно — [openSUSE OBS opengost-fonts](https://build.opensuse.org/package/show/openSUSE/opengost-fonts)
- CADENAS/TraceParts продают именно доступ к DIN/ISO/EN/ANSI таблицам (платный тир), что указывает на лицензирование у органов — [ISD HiCAD help](https://help.isdgroup.com/helponline/1033/2024/hicad/Subsystems/hicadsst/Content/WeitereSchnittstellen/Partsolutions.htm); [techno-science TraceParts](https://www.techno-science.net/fr/definitions/traceparts)

### Inferences (needs lawyer)
- Разумная граница для открытого пакета: (а) **метаданные** стандарта (обозначение, название, статус, даты, связи replaces/replacedby) — фактические сведения, низкий риск; (б) **размерные таблицы/формулы** — спорная зона: в РФ фактические данные не охраняются как таковые, но подбор/расположение (составное произведение, ст. 1259/1260) и права на базу данных могут быть заявлены; для ISO/DIN органы прямо считают это охраняемым; (в) **тексты** стандартов — закрыто для ISO/DIN, для ГОСТ — спорно (п. 6 ст. 1259 vs позиция Стандартинформа о ГОСТ Р ИСО).
- Рабочая стратегия, которую используют проекты: «данные не входят в пакет — пользователь подключает свою копию» (как HiCAD/3Dfindit платный тир) либо «производные таблицы из каталогов поставщиков с указанием source» (BOLTS). Для ГОСТ дополнительный аргумент — обязательная бесплатная публикация стандартов, на которые ссылаются НПА (приказ 1730), но это право просмотра, не редистрибуции.
- Тексты СП (Минстрой) и ГОСТ, включённые в перечни к техрегламентам, доступны публично; это снижает практические риски, но не даёт формального права на перепечатку.

### Gaps
- Не найдено ни одного судебного решения РФ по вопросу «является ли национальный ГОСТ объектом авторского права»; найденные дела касаются обязанности публикации (2005–2006). Нужен поиск в kad.arbitr.ru/sudrf (не выполнялся).
- Текущая редакция приказа № 1730 и фактический перечень стандартов в свободном доступе на сайте Росстандарта не проверены по первоисточнику.
- Не найдена официальная политика ISO/DIN конкретно о **встраивании размерных таблиц стандартов в CAD-библиотеки** (только общие условия и KI-лицензия DIN).
- Нет публичных сведений о лицензионных соглашениях CADENAS/TraceParts/Dassault/Autodesk с DIN/ISO/Росстандартом.

---

## КВ7 (ключевой вопрос «Архитектура»). «Стандарты как устанавливаемые пакеты» (данные + правила + шаблоны + i18n, версионированные редакции): прецеденты BOLTS, FreeCAD, KiCad, IDS

### Takeaway
Прямого прецедента «пакет стандарта» (данные + правила + шаблоны + переводы в одном артефакте с редакциями) не найдено, но все компоненты существуют по отдельности: BOLTS (`.blt` с `blt-version`, `standards[]`, `status`, `replaces`, `license`, `source`), FreeCAD Addon Manager (`package.xml` с SemVer/CalVer, зависимостями и ограничениями версий FreeCAD/Python), KiCad PCM (ZIP + `metadata.json`, репозиторий из `repository.json` + `packages.json` с JSON-схемой), IDS (XSD-схема правил + независимые валидаторы), Inventor (библиотека = устанавливаемый компонент MSI), SolidWorks (`.swstd` правила + custom drafting standard + Toolbox custom standard).

### Cited Findings
- FreeCAD `package.xml` (с 0.20): обязательный XML-манифест в корне пакета, формат версии 1; `<version>` по SemVer 2.0 **или** CalVer (не смешивать); FreeCAD использует метаданные, чтобы понять, какие ресурсы загружать и какие зависимости устанавливать; есть поля минимальной/максимальной версии FreeCAD и минимальной версии Python; Addon Manager применяет constraints-файл для разрешения Python-зависимостей; учитывается только `package.xml` основной ветки — [FreeCAD Wiki: Package Metadata](https://wiki.freecad.org/Package_Metadata); [GitHub FreeCAD/AddonManager](https://github.com/FreeCAD/AddonManager)
- KiCad PCM: пакет — ZIP (ISO 21320-1) с обязательным `metadata.json`; репозиторий — два JSON (метаданные репозитория и список пакетов), валидируемых по `pcm.v1.schema.json`; список пакетов — массив под ключом `packages`; `metadata.json` репозитория — надмножество архивного — [KiCad dev docs: Addons](https://dev-docs.kicad.org/en/addons/); [KiCad forum: GitHub repository compatible with KiCad](https://forum.kicad.info/t/how-to-create-a-github-repository-compatible-with-kicad/49550); [PyPI hatch-kicad](https://pypi.org/project/hatch-kicad/)
- BOLTS `.blt`: `blt-version: 0.4`, `license` на уровне коллекции, `standards[]` с `body/standard/replaces/status`, `source` — [raw nut.blt](https://raw.githubusercontent.com/boltsparts/boltsparts/main/data/nut.blt); дистрибутивы строятся из единых данных под разные CAD (FreeCAD/OpenSCAD/SolidWorks) — [GitHub boltsparts](https://github.com/boltsparts/boltsparts)
- IDS: XSD-схема + User Manual + Implementers Documentation; реализации (IfcTester) читают/пишут IDS и валидируют IFC — [GitHub buildingSMART/IDS](https://github.com/buildingSMART/IDS); [PyPI ifctester](https://pypi.org/project/ifctester/0.0.240318/)
- Inventor: библиотека стандарта = компонент установки (DCLibrary64.msi → Change → GOST) — [IMAGINiT](https://resources.imaginit.com/manufacturing/how-to-change-which-inventor-content-center-libraries-are-installed)
- SolidWorks: правила (`.swstd`), профили оформления (custom drafting standard: save/load), custom Toolbox standards — три независимых артефакта — [Drafting Standard 2024](https://help.solidworks.com/2024/English/SolidWorks/Sldworks/HIDD_OPTIONS_DRAFTING_STD.htm); [Build Checks 2021](https://help.solidworks.com/2021/english/SolidWorks/solidworks_design_checker/c_build_checks.htm); [Custom standards 2019](https://help.solidworks.com/2019/english/solidworks/toolbox/t_tbx_standards_custom.htm)
- ISO 13584 PLIB / OntoML — стандартизированная модель словарей и библиотек деталей с машиночитаемыми идентификаторами; ранние библиотеки крепежа КОМПАС строились на ISO 13584 — [Wikipedia ISO 13584](https://en.wikipedia.org/wiki/ISO_13584); [БНТУ лекция 7](https://nachertalka.bstu.by/files/books/lection_7.pdf)
- Версионирование норм в Python: редакция = подпакет (`codes/ec2_2004`, `codes/ec2_2023`; `pyaisc/src/v13`), регион = модуль (`steelsnakes/UK`, `/US`, `/US_Metric`) — [structuralcodes docs](https://fib-international.github.io/structuralcodes/); [pyaisc](https://github.com/mwhit74/pyaisc); [steelsnakes](https://steelsnakes.readthedocs.io/)
- Жизненный цикл редакций норм: дата публикации / дата отзыва / период сосуществования / National Annex как обязательная пара (Eurocode 2G: 30.09.2027 / 30.03.2028) — [BSI Knowledge](https://knowledge.bsigroup.com/products/eurocode-3-design-of-steel-structures-design-of-joints/standard)

### Inferences
- Обоснованная архитектура (синтез прецедентов): **манифест** (как `package.xml`/`metadata.json`: id, SemVer пакета, зависимости, совместимость с ядром) + **реестр стандартов** (как BOLTS `standards[]`: body, designation, edition/date, status active/withdrawn, replaces/replacedBy, national annex) + **данные** (таблицы в CSV/YAML/JSON с `source` и лицензией на уровне коллекции, как `.blt`) + **правила** (декларативный JSON/XML с `id → reference (standard, clause) → applicability → requirement → severity`, как IDS + критичность Design Checker) + **шаблоны** (SVG с editable/autofill-полями, как TechDraw) + **i18n** (имена по ISO 639-1, как FCMat) + **схемы единиц** (пресеты, как FreeCAD unit schemas). Версионирование редакций — по модели Eurocode: `published / withdrawn / coexistence` + явный выбор редакции в проекте.
- Юридическая развязка через два слоя пакета: открытый «каркас» (метаданные, правила-ссылки, шаблоны, i18n) и подключаемый «data-слой» (таблицы), который либо производный с указанием источника, либо поставляется пользователем/лицензиатом (needs lawyer).

### Gaps
- Не найдено ни одного проекта, объединяющего все четыре компонента (данные+правила+шаблоны+i18n) в одном версионированном пакете стандарта.
- Схема `pcm.v1.schema.json` и список полей версий `packages.json` KiCad не прочитаны напрямую.

---

## КВ8 (ключевой вопрос). На что опираются инженеры в России для автоматизации ЕСКД/СПДС сегодня

### Takeaway
Основные инструменты: КОМПАС-3D/КОМПАС-График (АСКОН) с платным приложением «Стандартные изделия» (ГОСТ, ОСТ 92, ISO, DIN) и отдельным чекером KOMPAS-Expert; Платформа nanoCAD с модулями «СПДС» (ГОСТ 21.101) и «Механика» (ЕСКД/ЕСТД, база стандартных изделий по ГОСТ, MechWizard) и nanoCAD Механика PRO; СПДС GraphiCS/MechaniCS (CSoft) для AutoCAD/ZWCAD/nanoCAD; из зарубежных — профили GOST в AutoCAD Mechanical и SolidWorks (оформление и Design Checker), библиотека GOST в Inventor Content Center (ставится вручную).

### Cited Findings
- КОМПАС-3D v24 — модуль «Стандартные изделия» в дистрибутиве; состав по ГОСТ/ОСТ 92/ISO/DIN — [cad.ru KOMPAS v24](https://cad.ru/support/bz/download/docs/kompas3Dv24.pdf); [АСКОН прайс приложений 2024](https://edu.ascon.ru/source/files/prices/MCAD&AEC_app_20241016.pdf)
- KOMPAS-Expert — проверка документов со списком ошибок — [АСКОН KOMPAS-Expert](https://sd.ascon.ru/ftp/Public/%d0%9f%d1%80%d0%b5%d0%b7%d0%b5%d0%bd%d1%82%d0%b0%d1%86%d0%b8%d0%b8_%d0%9d%d0%9f%d0%9e%20%d0%9c%d0%b0%d1%88%d0%b8%d0%bd%d0%be%d1%81%d1%82%d1%80%d0%be%d0%b5%d0%bd%d0%b8%d1%8f/KOMPAS-Expert.pdf)
- Платформа nanoCAD: модули «СПДС» и «Механика» входят в лицензию (по данным партнёра), «Растр»/«Топоплан» — отдельно; реестр отечественного ПО № 8814 — [CSoft Omsk](https://nanocad.csoftomsk.ru/platforma-nanocad); [Habr: Платформа nanoCAD](https://habr.com/ru/articles/805689)
- nanoCAD Механика: база стандартных изделий по ГОСТ (ISO/DIN/CSN), MechWizard на панели ЕСКД; Механика 20 входит в nanoCAD Plus 20; Механика PRO — отдельный продукт на отечественном ядре, от 12 000 руб./год (2024) — [Habr Нанософт](https://habr.com/company/nanosoft/blog/346704); [cadmaster cm_87_07](https://www.cadmaster.ru/assets/files/articles/cm_87_07.pdf); [normacs news 74598](https://www.normacs.info/news/74598)
- СПДС GraphiCS (CSoft, с 2000 г.) — AutoCAD/AutoCAD Architecture/ZWCAD/nanoCAD, ГОСТ 21.101-2020, шрифт ГОСТ 2.304-81 — [CSoft брошюра](https://csdev.csd.ru/local/templates/csdev/upload/pdf/SPDS_GraphiCS.pdf); [cadmaster cm_90_19](https://www.cadmaster.ru/assets/files/articles/cm_90_19.pdf)
- AutoCAD Mechanical — профиль GOST — [Autodesk Help 2024](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-Mechanical/files/GUID-91A27BD0-3D48-49F1-B8D7-F6E10CA6D163.htm); SolidWorks — GOST в drafting standards и Design Checker — [SOLIDWORKS 2024](https://help.solidworks.com/2024/English/SolidWorks/Sldworks/HIDD_OPTIONS_DRAFTING_STD.htm); Inventor — GOST-библиотека не по умолчанию — [Autodesk 2026](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Install/files/GUID-61015D87-8EF5-4EE3-A612-ECAFE1408850.htm)
- Нормоконтроль как внешняя услуга (компании гарантируют «комплект проходит нормоконтроль») — [vnesenie-v-reestr.ru](https://vnesenie-v-reestr.ru/kd/about)

### Inferences
- В РФ автоматизация ЕСКД/СПДС сосредоточена в проприетарных отечественных продуктах; open-source слой ограничен шрифтом OpenGostFont и 2 ГОСТ-таблицами в FreeCAD Fasteners — крупный незанятый сегмент для открытого «пакета ГОСТ/ЕСКД».

### Gaps
- MechaniCS (CSoft) — почти нет данных в результатах поиска.
- Нет актуальных (2025–2026) официальных перечней ГОСТ в базах nanoCAD Механика и КОМПАС «Стандартные изделия».

---

## КВ9 (ключевой вопрос). Примеры движков правил с хорошим UX для инженеров (rule → reference → element → severity)

### Takeaway
Лучшие образцы: SolidWorks Design Checker (правило в `.swstd` → встроенный стандарт ANSI/ISO/GOST… → провалы по элементам документа, сгруппированные Critical/High/Medium/Low, автокоррекция, batch); NX Check-Mate (чекер → настраиваемые значения → Information/Warning/Error → HTML-отчёт/дашборд; no-code Checker Editor с 2023); DFMPro (правило по процессу → порог поставщика → подсветка на геометрии → отчёт); IDS/IfcTester (specification: applicability → requirements с facets и cardinality → отчёты); Tacton (ограничения + предложения альтернатив при конфликте).

### Cited Findings
- Design Checker: уровни критичности per-check, только провалы в отчёте, встроенные стандарты + свои файлы, автокоррекция — [Criticality Levels](https://help.solidworks.com/2018/English/SolidWorks/solidworks_design_checker/r_criticality_levels.htm); [Check Active Document](https://help.solidworks.com/2019/english/SolidWorks/solidworks_design_checker/c_check_active_document.htm); [Learn Checks Wizard](https://www.javelin-tech.com/blog/2022/11/using-the-learn-checks-wizard-in-solidworks-design-checker/)
- Check-Mate: information/warning/error, настраиваемые значения, Checker Editor (2023), Quality Dashboard — [Siemens blog](https://blogs.sw.siemens.com/nx-design/learn-more-about-checks-with-out-of-the-box-testing-with-nx-check-mate); [What's new June 2023](https://blogs.sw.siemens.com/nx-design/whats-new-in-nx-june-2023-validation/)
- DFMPro: правила по процессу, пороги под поставщика, отчёт с локализацией дефектов на модели — [HCL DFMPro](https://hclsoftwareu.hcltechsw.com/dfmpro)
- IfcTester/IDS: спецификация как «применимость → требования», отчёты в нескольких форматах, CLI/web/библиотека — [PyPI ifctester](https://pypi.org/project/ifctester/0.0.240318/)
- Tacton: solver проверяет ограничения друг против друга и предлагает альтернативы при конфликте выбора — [TrustRadius Tacton](https://www.trustradius.com/products/tacton-design-automation)
- json-rules-engine: `conditions{all/any/not}` + `event{type, params}` + `priority` — компактная JSON-модель, пригодная для «rule → event(severity, reference)» — [json-rules-engine walkthrough](https://github.com/cachecontrol/json-rules-engine/blob/HEAD/docs/walkthrough.md)
- GoRules JDM: решения как JSON-графы с decision tables; open-source редактор — [PyPI zen-engine](https://www.pypi.org/project/zen-engine)
- KOMPAS-Expert: список ошибок как результат проверки — [АСКОН KOMPAS-Expert](https://sd.ascon.ru/ftp/Public/%d0%9f%d1%80%d0%b5%d0%b7%d0%b5%d0%bd%d1%82%d0%b0%d1%86%d0%b8%d0%b8_%d0%9d%d0%9f%d0%9e%20%d0%9c%d0%b0%d1%88%d0%b8%d0%bd%d0%be%d1%81%d1%82%d1%80%d0%be%d0%b5%d0%bd%d0%b8%d1%8f/KOMPAS-Expert.pdf)

### Inferences
- Повторяющиеся UX-элементы, которые стоит заимствовать: (1) правило всегда привязано к именованному «стандарту/профилю», переключаемому целиком; (2) критичность задаётся автором правила, а не вычисляется; (3) отчёт показывает только провалы и группирует по критичности; (4) «learn from reference document» снижает стоимость авторинга; (5) автокоррекция — для оформительских правил, не для геометрии/прочности; (6) пакетный режим + API для CI-подобных проверок.

### Gaps
- Не найдены скриншоты/спецификация UI Checker Editor NX и формата хранения его чекеров.
- Не найдены open-source MCAD-чекеры с моделью критичности (кроме IDS для BIM).
