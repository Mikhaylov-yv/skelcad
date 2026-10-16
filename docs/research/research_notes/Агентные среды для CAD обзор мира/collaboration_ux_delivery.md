# Collaboration, review UX and desktop delivery for human–AI CAD (as of 2026-10)

Scope: (1) PR-style review & 3D diff for CAD, (2) top-down / skeleton methodology and interface formalization, (3) evidence on human–AI co-design and Copilot-style adoption lessons, (4) agent-side proposal/approval/undo UX and turn-taking in live tools, (5) local-first delivery of Python/OCCT tools to Windows non-programmers. Vendor marketing and practitioner opinion are flagged as such.

---

## Area 1 — "Agent proposes, engineer approves": PR-style review and 3D diff tooling for CAD

### Takeaway
No mainstream CAD system has a true pull-request workflow; the closest are Onshape branch→merge (coarse, per-tab strategies, no cherry-picking inside a tab) and Git-LFS+locking wrappers (Anchorpoint) that cannot merge at all. Visual compare exists in Onshape (blue/red overlay with slider + side-by-side feature list) and SolidWorks (volume/face compare), but a CHI'26 study of 170 forum threads finds engineers still lack the "why", drown in auto-save noise, and lose comparability once geometry is exported to STEP. GrabCAD Workbench is dead (June 2023).

### Cited Findings

**Onshape branching/merging (the only widely used CAD "PR-like" flow)**
- Onshape merges From→To: target is the active workspace, source is a workspace or version from another branch; options are (1) replace all target changes with source, (2) merge source changes into target, (3) keep all target changes. Strategies are chosen *per tab*; "you cannot select individual changes within a tab". Merge is computed against the common ancestor (delta base→source applied to target). — [Onshape Help: Merging](https://cad.onshape.com/help/Content/Document/merging.htm)
- Conflicts are most likely when the Target was also modified after the Source branch was created; an unwanted merge can be undone by restoring the workspace to the action before the merge. — [Onshape Tech Tip: Successful Merging](https://www.onshape.com/en/resource-center/tech-tips/tech-tip-a-guide-to-successful-merging-in-onshape)
- Practitioner complaints (forum, anecdotal): "very easy to accidentally work on the node of the main branch", branches "including your DEV branch can be accidentally deleted", "merge across to main sometimes fails for me"; that user uses branching only "to compare a few different design scenarios off a version". — [Onshape forum](https://forum.onshape.com/discussion/comment/42657)
- Onshape Compare (since June 2015): default is a graphical overlay with a slider; **blue = Base, red = Target**; a list view shows features side by side so one can "see the changes in the graphics and the specific differences in features". Any combination of workspaces/versions/history entries can be compared. — [Onshape Help: Compare](https://cad.onshape.com/help/Content/Document/compare.htm); [Tech Tip: Comparing Design Changes](https://www.onshape.com/en/resource-center/tech-tips/tech-tip-comparing-design-changes); [What's New June 8 2015](https://onshape.com/en/resource-center/what-is-new/whats-new-in-onshape-june-8-2015)
- A 2016 forum post said Compare was then limited to Part Studios (no assemblies); may be outdated. — [Onshape forum](https://forum.onshape.com/discussion/comment/19404)

**SolidWorks Compare / DrawCompare / eDrawings**
- SOLIDWORKS Compare finds differences in Document Properties, Features, Geometry or BOM; geometry results are shown as **Volume comparison** (material added/removed) or **Face comparison** (unchanged / unique / modified faces). Geometry compare runs on every component, so "large assemblies could take a long time". — [Javelin: Compare & DrawCompare](https://www.javelin-tech.com/blog/2019/04/solidworks-compare-drawcompare/); [SeaCAD: Compare tool](https://vn.seacadtech.com/blog/catching-every-detail-with-solidworks-compare-tool/)
- For drawings, Compare checks only document properties and BOM; graphical sheet differences need DrawCompare (additions/removals between two documents). — [Javelin 2019](https://www.javelin-tech.com/blog/2019/04/solidworks-compare-drawcompare/); [CATI: Compare Drawings](https://www.cati.com/blog/solidworks-utilities-compare-drawings/)
- PDM/Manage: comparison tools available through the PDM history tab; drawings can be opened in eDrawings from history to review differences (2025 reseller post). — [Javelin 2025: Comparison tools for PDM/Manage](https://www.javelin-tech.com/blog/2025/08/comparison-tools-for-solidworks-pdm-and-solidworks-manage/)
- User report (unresolved): dimensions measured with eDrawings Markup "significantly different from the value in the SOLIDWORKS model". — [3DEXPERIENCE forum](https://3dswym.3dexperience.3ds.com/question/solidworks-user-forum/edrawing-dimension-do-not-match-sldrw_-3Tor9kmQSK7VgksUBRJ_Q)

**GitHub for CAD / git-lfs / diff viewers**
- GitHub added in-browser diffing of **.STL** models in 2013 (reported via forum link to the GitHub blog). — [Leadwerks forum thread on GitHub 3D diff](https://www.leadwerks.com/community/topic/7620-github-adds-support-for-diffing-3d-files)
- Zoo (ex-KittyCAD) **Diff Viewer**: open-source Chrome/Edge extension that overrides parts of the GitHub UI to show a 3D view of CAD files in PRs; two modes: **2-up** (before/after) and **combined** (experimental: additions, deletions and unchanged in one viewer); uses the Zoo API to convert files; status "PUBLIC ALPHA". — [zoo.dev/diff-viewer](https://zoo.dev/diff-viewer); [docs.zoo.dev/diff-viewer](https://docs.zoo.dev/diff-viewer)
- Anchorpoint (Git + Git LFS for SolidWorks etc.) uses **file locking when someone starts editing** because "Git cannot merge binary CAD files", so locking is the main conflict prevention. — [Anchorpoint docs: Git for CAD](https://docs.anchorpoint.app/git/cad); [Anchorpoint: Git with SolidWorks](https://www.anchorpoint.app/blog/git-with-solidworks); [Anchorpoint: Best version control for CAD](https://www.anchorpoint.app/blog/best-version-control-for-cad)
- Academic prototype: command-line diff/patch/merge for openNURBS (.3dm) models (UNC Charlotte thesis). — [Rawlings thesis](https://ninercommons.charlotte.edu/record/2257/files/Rawlings_uncc_0694N_13315.pdf)
- **GrabCAD Workbench** was discontinued: announced Aug 2022 (reason reported as lack of dev staff), service ended **June 1, 2023 12:00 GMT**, all stored files deleted. — [All3DP](https://all3dp.com/4/grabcad-workbench-to-go-offline/); [GrabCAD blog](https://blog.grabcad.com/?p=30535)
- Practitioner/vendor opinion (NOVEDGE blog, 2026): CAD files are "binary, huge, and occasionally non-deterministic, making line-based diffs meaningless"; argues for diffs that report "which nodes were added or removed, which edges—mates, constraints, references—were rewired, and which attributes changed", a CAD-aware layer over a VCS with assemblies as graphs, machine-readable snapshots of parameters and mass properties, visual diffs and policy gates; file-level locking called "too coarse". No shipped product found implementing this. — [NOVEDGE: Geometry-aware VC](https://novedge.com/blogs/design-news/geometry-aware-version-control-for-cad-graph-based-workflows-semantic-diffs-lfs-locks-and-deterministic-ci); [NOVEDGE: Git-inspired CAD](https://novedge.com/blogs/design-news/git-inspired-cad-deterministic-content-addressed-geometry-with-semantic-diffs-and-merges)

**Evidence on what engineers actually need (CHI 2026)**
- Deng, Zhang, Cheng, Olechowski, Zhou, "Untangling the Timeline: Challenges and Opportunities in Supporting Version Control in Modern CAD", CHI '26: qualitative analysis of 424 collected / **170 relevant threads** from 7 forums (Autodesk, Onshape, SolidWorks, Reddit, Thingiverse, CAD Forum, Eng-Tips; 2005–2024), 83% inter-coder agreement. Thread counts: navigating history 47, editing history 45, propagating changes to linked files 26, exporting with history 19, **identifying changes between versions 17, branching & merging 10**. — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)
- Same paper: "users still have no way to know 'why' the changes were made" (the why/what = engineering change orders); Onshape and SolidWorks show parametric *and* geometric differences, Thangs and Fusion show geometric only; for Fusion "Modelling command parameters are not compared, even if they are accessible"; neutral exports are "all binary stuff, so it's impossible to diff"; auto-saves and trivial edits (toggling a section view) create versions that look like real changes (raised in 45 threads); after STEP export "its associated version history is effectively lost". — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)
- Same paper, design opportunities: use LLMs/VLMs on CAD code and visualized geometric differences to "generate candidate textual descriptions of modifications for users to review"; **"the AI should only function as an assistive layer"**, users stay accountable for history entries; think-aloud capture turned into documentation; git-style curated history ("not merely a raw log of edits"), lightweight markers/tags for milestones; "additional visual dimensions, markers, and colour encoding to represent design evolutions"; expose versioning/branching/sharing "as composable primitives rather than fixed workflows"; bundled multi-version exports akin to `git bundle`. — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)
- Earlier work by the same group: CSCW 2023 semi-structured interviews with **20 CAD professionals** on distributed CAD collaboration challenges. — [Cheng et al., CSCW](https://www.eecg.utoronto.ca/~shuruiz/forcolab/paper/CSCW_CollaborationinCAD.pdf); Onshape Research Symposium 2022 talks "Time to branch out: An analysis of online user forum posts to inform CAD branching" (Cheng) and "An Empirical Study of Branching Use in CAD" (Cuvin). — [Onshape Research Symposium 2022](https://www.onshape.com/en/education/research-symposium/2022-event)

### Inferences
- The "PR" metaphor for engineers maps onto Onshape's branch/version/compare vocabulary better than onto git's; engineers already accept "compare two history points with an overlay slider" (Onshape) and "volume added/removed" (SolidWorks). A proposal UX built on those two idioms needs no new mental model.
- Everything that works today compares *feature trees + geometry* inside one proprietary system; neutral formats break it. An agent that operates on a code/parametric model (CadQuery/build123d) is actually well placed: it can show a parameter/feature-level textual diff *and* a geometric diff, which the CHI'26 study says is what Fusion/Thangs lack.
- Review noise is the dominant complaint; proposals should be coalesced into one reviewable change-set per intent, not per operation.

### Gaps
- "Kaizen" CAD diff tool: no search result found anything under that name (may be a misremembered or very new product). Not covered.
- No source found measuring review time or acceptance for any CAD compare UI; no A/B evidence of overlay vs 2-up vs heat-map.
- Bitbucket/Jenkins pipelines for CAD: not researched beyond NOVEDGE's "deterministic CI" opinion piece.
- Onshape Compare current assembly support unverified (only a 2016 forum note).

---

## Area 2 — Top-down methodology in practice: skeletons, master models, layout sketches, and whether the skeleton is explicit data

### Takeaway
Every major CAD has a "skeleton" construct (Creo Skeleton Model + Publish/Copy Geometry, NX WAVE control part + Product Interface, SolidWorks layout sketch / master model, Inventor skeletal part, Onshape layout Part Studio + Derive, KOMPAS "компоновочная геометрия"), always realized as *ordinary geometry* (surfaces, curves, datums, expressions) with associative links. The only tools that treat the *interface* as a first-class, declared object are Creo's reference control and NX's Product Interface (explicitly published geometry + expressions). Nowhere is the skeleton a data schema outside the CAD kernel.

### Cited Findings
- Creo: a skeleton is "a special model that holds shared design information for a project"; design criteria are "surface geometry, curves, and datum features"; skeletons can only be created inside an assembly and regenerate before other components; components pull interface geometry with Copy Geometry / Publish Geometry features; standard vs motion skeletons. — [PTC CS56587](https://www.ptc.com/en/support/article/CS56587); [Creo Toolkit: Skeleton Model Functions](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r13/usascii/creo_toolkit/user_guide/Skeleton_Model_Functions.html); [PTC blog: Guide to top-down assembly](https://ptc.com/en/blogs/cad/guide-to-top-down-assembly); [Skill-Lync](https://resources.skill-lync.com/branches/mechanical-engineering/questions/design-cad/creo-top-down-design)
- Creo "reference control": reference restrictions, scope of creation, scope of selection, references backup (PTC user conference deck, 2015). — [PTC308 Baum deck](https://www.ptcusercommunity.com/sejnu66972/attachments/sejnu66972/CommunityNetworkingDiscussions/794/1/PTC308_Baum_20150616_1424.pdf)
- NX WAVE Geometry Linker creates associative copies of geometry between parts; in top-down work a **control part holds the interface geometry** that component designers reference; links can be broken; position-dependent links break when the source leaves the assembly. — [Skill-Lync NX WAVE](https://resources.skill-lync.com/branches/mechanical-engineering/questions/design-cad/nx-wave-geometry-linker); [Eng-Tips WAVE link behaviour](https://www.eng-tips.com/threads/nx-wave-links-behaviour.414239/post-8183909)
- NX **Product Interface** "allows users to define geometry and expressions from a part and set this information as a reference to utilize in a new part"; WAVE Interface Linker lets others consume published interfaces "without altering the parent part". NX 2212 Feature Templates can take WAVE geometry links as inputs. — [Siemens NX blog: interpart modeling](https://blogs.sw.siemens.com/nx-design/nx-tips-tricks-interpart-modeling-2/); [Siemens NX blog: feature templates](https://blogs.sw.siemens.com/nx-design/feature-templates-tips-and-tricks/)
- NX Interpart Expressions drive dimensions from assembly level, another part, or a spreadsheet. — [GrabCAD Q&A](https://grabcad.com/questions/what-is-the-difference-between-wave-geometry-linker-and-interpart-link-in-nx-7-5); ATA Engineering lists geometry linker, interface linker, associativity manager as the WAVE tools for dividing work among teams. — [ATA Engineering](https://www.ata-e.com/software/training-support/free-resources/increase-assembly-speed-and-efficiency-with-nx-wave-tools/)
- SolidWorks (ASEE study): two top-down methods — **layout sketch** ("a sketch to show both the assembly layout and the main dimensions"; only one per assembly; every part should attach to it) and **master model** (split/multibody, bodies copied into part files); authors conclude master model "is the most robust, flexible, and adaptable approach", while the layout sketch was faster on a basic assembly. — [ASEE: Two CAD methodologies for top-down assemblies](https://peer.asee.org/investigating-and-comparing-two-different-cad-methodologies-to-create-top-down-assemblies)
- Practitioner opinion (French CAD forum): a skeleton "can carry too much information"; recommends "Lock references"; downsides: external reference management, configuration management, "very slow rebuilds". — [myCAD forum](https://forum.mycad.visiativ.com/t/quelle-est-la-bonne-methode-pour-concevoir-des-pieces-et-assemblages-dependants-dun-squelette/112738)
- Inventor: skeleton = "a single part model with base sketches that reflect the layout of the assembly components"; with position-independent components, moving layout geometry "do[es] not require component revisions". — [Autodesk Inventor Help: Skeletal modeling](https://help.autodesk.com/cloudhelp/2023/ENU/Inventor-Help/files/GUID-0435FE9D-6283-4CE0-813B-BD9B0BE5778C.htm)
- Onshape: multi-part Part Studios (shared sketches/features drive several parts), in-context editing (snapshot of assembly, other parts ghosted), "Create Part Studio in Context" from a mate connector. — [Onshape blog: top-down](https://www.onshape.com/en/blog/onshape-takes-the-lead-on-top-down-design); [Onshape Help: Create Part Studio in Context](https://cad.onshape.com/help/Content/Assembly/create_part_studio_in_context.htm). Forum workflow (practitioner): a **layout Part Studio with only sketches and basic solids**, Derive into development Part Studios; "derive between the development part studios is to be avoided as this will bring the document to its knees". — [Onshape forum: in-context best practices](https://forum.onshape.com/discussion/8458/best-practices-for-in-context-editing)
- KOMPAS-3D: vendor material lists bottom-up, top-down and "modelling based on layout schemes, such as kinematic schemes" as supported methods; ASCON 2012 "White Nights" talk by I. Volokitin covers top-down methodology and large assemblies (locomotive, drilling rigs). — [KOMPAS-3D description](https://pcbgt.com.sg/kompas-3d); [ASCON 2012 deck](https://sd.ascon.ru/ftp/Public/WhiteNights2012/1_%d0%92%d0%be%d0%bb%d0%be%d0%ba%d0%b8%d1%82%d0%b8%d0%bd_%d0%90%d0%a1%d0%9a%d0%9e%d0%9d_%d0%91%d0%be%d0%bb%d1%8c%d1%88%d0%b8%d0%b5_%d1%81%d0%b1%d0%be%d1%80%d0%ba%d0%b8.pdf)
- Multi-user research: BYU NX Connect prevents simultaneous edits of the same feature via **lock–warn–rollback**, orders operations by an operation sequence number (first-come wins, invalid ops kept for later fix); demo: 3 users built a turbine front frame in ~1/3 the single-user time. — [BYU TechTransfer: conflict management](https://techtransfer.byu.edu/technologies-section-new/real-time-conflict-management-in-multi-user-cad-environments); [BYU TechTransfer: NXConnect](https://techtransfer.byu.edu/technologies-section-new/enhancing-multi-user-cad-systems-with-nxconnect); [BYU CADLab demo](https://cadlab.byu.edu/content/front-frame-demo); [Hepworth dissertation (feature reservation)](https://scholarsarchive.byu.edu/etd/5586); [US patent 9648059](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9648059)

### Inferences
- Formalized interfaces exist in industry only as *published geometry sets + expressions* (NX Product Interface, Creo Publish Geometry) plus reference-restriction policies; the "contract" is enforced by the CAD, not by a document. A code-first CAD (CadQuery/build123d) could make the skeleton an explicit Python/JSON object (datum planes, axes, envelopes, named parameters), which no commercial tool does today — a differentiator, but engineers will expect the same semantics (regenerate-first, associative, breakable links).
- Practitioners consistently warn of two failure modes: skeleton bloat and rebuild cascades. An agent that edits a skeleton must show the downstream blast radius before applying.

### Gaps
- No primary Siemens documentation retrieved for Product Interface/WAVE (only Siemens blogs and training sites); no PTC primary doc on reference control beyond a 2015 deck.
- KOMPAS "компоновочная геометрия" specifics (official help) not retrieved; only vendor summaries.
- No published study on how companies write mechanical interface control documents (ICDs) alongside CAD skeletons.

---

## Area 3 — Human–AI co-design evidence and Copilot adoption lessons

### Takeaway
Direct HCI evidence on AI copilots *inside* CAD is thin (systems papers, one 20-designer Fusion 360 study, a NASA ethnography); the transferable, quantified lessons come from programming: verification dominates interaction time (22.4% of session time verifying, 51.5% in suggestion-related states, 34% acceptance), experienced developers were 19% *slower* with early-2025 tools while believing they were 20% faster (METR RCT), and org-level AI adoption correlated with lower delivery stability (DORA 2024). The CHI'26 CAD VC paper concludes AI "should only function as an assistive layer".

### Cited Findings

**Programming evidence transferable to CAD**
- Mozannar et al., "Reading Between the Lines", CHI 2024 (Honorable Mention), 21 programmers, 1,024 suggestions: CUPS taxonomy of 12 states; **"verifying suggestion" takes 22.4% of session time**, waiting 4.2%; total time in suggestion-related states **51.5%**; conclusion: programmers spend "a large fraction of total session time (34.3%)" double-checking and editing suggestions; **34.0% of suggestions accepted** (mean per participant 36.5%); when "Deferring Thought For Later", acceptance probability 0.98 and 53.2% verify immediately after accepting; accounting for post-acceptance checking raised mean verification time from 3.25 s to 15.21 s. — [arXiv 2210.14306](https://arxiv.org/html/2210.14306v5); [MSR listing](https://www.microsoft.com/en-us/research/people/adamfo/publications)
- METR RCT (July 2025): 16 experienced OSS developers, 246 tasks in their own repos, randomized AI-allowed vs not; **AI increased completion time by 19%**; developers predicted a 24% speedup and afterwards *believed* AI reduced time by 20%. — [arXiv 2507.09089](https://arxiv.org/pdf/2507.09089); [METR summary](https://tagteam.harvard.edu/hub_feeds/3997/feed_items/14760086/about)
- DORA 2024: per 25% increase in AI adoption, +3.4% code quality and +3.1% review speed, but decreased delivery stability (secondary summaries: −7.2% stability, −1.5% throughput); 75% self-report productivity gains; correlational. — [DORA 2024 infographic](https://dora.dev/research/2024/2024-DORA-Report-Infographic.pdf); [RedMonk on DORA 2024](https://redmonk.com/rstephens/2024/11/26/dora2024/)
- Thoughtworks Radar (Oct 2024) names "complacency with AI-generated code": reviewers become less vigilant after positive experiences; cites a GitHub-reported 15% rise in PR merge rates and asks whether larger PRs are merged faster "because they trust the AI too much". — [Thoughtworks Radar](https://www.thoughtworks.com/en-au/radar/techniques/complacency-with-ai-generated-code)
- FAccT 2024 interview study of 17 developers on how they judge trustworthiness of AI code generation (UW + Microsoft Research). — [FAccT 2024 paper](https://facctconference.org/static/papers24/facct24-99.pdf)
- Student thesis (Edinburgh, 2024, not peer-reviewed): two Copilot interaction patterns, "Collaborators" vs "Operators"; trust linked to met expectations and perceived productivity. — [Edinburgh UG4 thesis](https://project-archive.inf.ed.ac.uk/ug4/20244354/ug4_proj.pdf)

**CAD / engineering design specific**
- 20 designers with mechanical-engineering backgrounds (≥2 years CAD, no prior Generative Design exposure) performed a generative design task in Autodesk Fusion 360 while supported by metacognitive agents (arXiv 2025). — [arXiv 2506.12879](https://arxiv.org/pdf/2506.12879)
- Ethnography of an early-stage NASA design team on when/why they used generative AI, with follow-up interviews (ASME IDETC 2024). — [Ma et al., IDETC 2024](https://codesign.berkeley.edu/papers/ma-genai-idetc)
- TU Dresden / Fraunhofer: barriers to generative AI in CAD — small datasets, mixed data types, proprietary formats, lack of advanced modelling commands. — [TU Dresden publication](https://fis.tu-dresden.de/portal/en/publications/challenges-and-opportunities-in-the-integration-of-generative-ai-with-computeraided-design(08db7881-1718-40cb-bec0-6e6596d640d0).html)
- Systems papers 2025: CADDesigner (LLM agent with interactive requirement dialogue). — [arXiv 2508.01031](https://arxiv.org/html/2508.01031v2); multi-agent "From Idea to CAD". — [arXiv 2503.04417](https://arxiv.org/html/2503.04417v1); Kumar et al.: LLM-generated FreeCAD scripts do well on simple/moderate designs, struggle with highly constrained ones. — [arXiv 2508.00843](https://arxiv.org/pdf/2508.00843v1); survey "LLMs for CAD". — [arXiv 2505.08137](https://arxiv.org/html/2505.08137v1)
- Industry status (ABI Research, Oct 2025): copilots are "table stakes", all major suppliers offer an AI assistant in at least one product. — [ABI Research](https://www.abiresearch.com/market-research/insight/7787074-ai-is-reshaping-cad-but-suppliers-must-be-)
- CHI'26 CAD version-control paper: AI may synthesize version-change summaries but "should only function as an assistive layer"; users remain accountable. — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)

### Inferences
- Verification is the real cost center. If a CAD agent's proposals take the engineer longer to check than to do by hand (likely for geometry, which is slower to inspect than text), METR's negative result will reproduce. The review UI must compress verification: show exactly what changed (parameters + volume delta + affected downstream features) and nothing else.
- The "Deferring Thought" pattern (accept now, check later, 98% acceptance) is the over-reliance mechanism; for CAD, a defer-then-batch-review mode without a forcing checkpoint would reproduce DORA's stability loss (bad geometry reaching manufacturing).

### Gaps
- No CHI/UIST/DIS 2023–2026 paper found that interviews mechanical engineers about trust in AI *inside* CAD; closest are the Fusion 360 generative-design study and the NASA ethnography. Searched twice; nothing stronger.
- No engineer survey with numbers on acceptance/rejection of AI-proposed CAD changes.
- GitHub/Microsoft internal Copilot adoption lessons (beyond CHI 2024 and radar commentary) not retrieved from primary sources.

---

## Area 4 — Agent-side UX: proposals, approvals, sandboxes, undo; MCP guidance; turn-taking/locking in live tools

### Takeaway
Coding agents converged on a tiered permission model (read-only auto / edits auto within workspace / shell asks / full bypass / sandboxed autonomous) plus local checkpoints for undo; MCP's spec says there "SHOULD always be a human in the loop", clients MUST treat tool annotations as untrusted, and should show tool inputs before calling. Live multiplayer tools (Figma, Onshape, Excalidraw) all use server-ordered or version-numbered last-writer-wins at property/element granularity and tell users to avoid editing the same object; research multi-user CAD (BYU) used explicit feature locks (lock–warn–rollback). No study found that compares strict turn-taking vs concurrent editing *with an AI agent*.

### Cited Findings

**Agent permission/approval models**
- MCP spec (2025-06-18): tools are "model-controlled"; "there **SHOULD** always be a human in the loop with the ability to deny tool invocations"; applications SHOULD show which tools are exposed, insert visual indicators when tools are invoked, and "present confirmation prompts to the user for operations". ToolAnnotations are metadata; "clients **MUST** consider tool annotations to be untrusted unless they come from trusted servers". Clients SHOULD "prompt for user confirmation on sensitive operations", "show tool inputs to the user before calling the server", validate results, time out, and log for audit. — [MCP spec: Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- MCP annotation semantics as implemented: `readOnlyHint` (does not modify environment), `destructiveHint` (meaningful only when not read-only), hosts use them to decide auto-approve vs confirmation dialog; LangChain surfaces `destructive_hint` so approval rules can key off it instead of hardcoded names. — [LangChain MCP tools](https://docs.langchain.com/oss/python/langchain/mcp/tools); [Spring AI MCP annotations](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-annotations-server.html); [azukiazusa: MCP tool annotations](https://azukiazusa.dev/en/blog/mcp-tool-annotations)
- Claude Code permission modes: default (ask), **acceptEdits** (create/edit files in working dir without prompting; common filesystem Bash like mkdir/rm/mv/cp/sed auto-approved; outside working dir and other Bash still prompt), **plan** (read-only, all mutating tool calls blocked), **auto** (research preview; runs without prompting with background safety classification; truly destructive actions still prompt), **bypass**; Shift+Tab cycles; availability depends on surface (web sessions offer only acceptEdits and plan). — [Claude Code docs: permission modes](https://code.claude.com/docs/en/permission-modes)
- Cursor Run Modes: "Auto-review" runs known-safe calls, sandboxes shell commands when possible, sends the rest to a classifier that allows / tries another approach / asks for approval; docs warn the classifier "can make mistakes, so Auto-review is not a security boundary". — [Cursor docs: run modes](https://cursor.com/docs/agent/security/run-modes.md)
- Cursor Checkpoints: automatic snapshots of Agent changes, restore from "Restore Checkpoint"; stored locally, separate from Git, track only Agent edits, "not a substitute for version control". — [Cursor docs: checkpoints](https://docs.cursor.com/agent/chat/checkpoints). Forum bug reports: diffs not shown for every change, checkpoint revert leaving files changed; staff advised committing to git before agent sessions. — [Cursor forum](https://forum.cursor.com/t/cursor-keeps-forcing-auto-accept-when-in-agent-mode/157627)
- Devin CLI permissions: Normal (read-only auto, writes/shell wait for approval), Accept Edits (workspace edits auto, shell and out-of-workspace writes prompt), Bypass, Autonomous with `--sandbox` (shell/network unprompted inside OS sandbox; "direct file edits via the edit/write tools still prompt, because those tools operate outside the sandbox"); admin deny/ask rules "remain active regardless of the user's permission mode". — [Devin CLI docs: permissions](https://docs.devin.ai/cli/reference/permissions)
- OpenHands CLI: default confirms each action; `--always-approve` auto-approves; `--llm-approve` uses an LLM-based security analyzer. — [OpenHands on PyPI](https://www.pypi.org/project/openhands/)
- Sandbox snapshot/rollback pattern (E2B): snapshot before a risky operation, spawn a fresh sandbox from the snapshot on failure. — [E2B docs: snapshots](https://e2b.dev/docs/sandbox/snapshots)

**Turn-taking / locking in live tools**
- Figma: "inspired by CRDTs" but not true CRDTs because a central server orders every edit; **last-writer-wins per property** ("last" = last to reach the server); "changes to different properties never conflict"; simultaneous editing of the same text value "doesn't work in Figma… this use case isn't one we're optimizing for". — [Figma: How multiplayer works](https://www.figma.com/blog/how-figmas-multiplayer-technology-works/); [madebyevan mirror](https://madebyevan.com/figma/how-figmas-multiplayer-technology-works/); CRDT merges can "lose user intent" though consistent. — [Hex: pragmatic live collaboration](https://hex.tech/blog/a-pragmatic-approach-to-live-collaboration/)
- Onshape live collaboration: all features/changes shown in real time to all collaborators; Follow Mode lets you watch a colleague; simultaneous edits of the **same sketch/feature** "could cause a conflict, so this should be avoided"; **"whoever commits the sketch (or feature) last would have their changes stay"**; recommendation: use Branches in the same Part Studio; "all changes made in a branch must be merged back – you can't choose"; everything is in history and undoable. — [Onshape Tech Tip: live collaboration](https://www.onshape.com/en/resource-center/tech-tips/tech-tip-why-onshapes-live-collaboration-is-nothing-to-fear); [Onshape Help: Collaboration](https://cad.onshape.com/help/Content/Collaboration/collaboration.htm); [Onshape blog: under the hood](https://www.onshape.com/it/blog/under-the-hood-how-collaboration-works)
- Excalidraw rooms: peers merge by **union of element IDs**, then a per-element monotonically increasing `version` (added to make deletions win) and a random `versionNonce` tie-breaker. — [Excalidraw blog: P2P collaboration](https://plus.excalidraw.com/blog/building-excalidraw-p2p-collaboration-feature); [pyshine source tour](https://pyshine.com/Excalidraw-Virtual-Whiteboard-Source-Tour/). An agent-in-the-room MCP server re-asserts bot-owned elements at a higher version so a human deletion doesn't silently drop them and reports contested IDs. — [excalidraw-mcp-collab](https://www.remoteopenclaw.com/mcp/rus-artur4ik/excalidraw-mcp-collab)
- Research multi-user CAD (BYU NX Connect): **lock–warn–rollback** on features, operation sequence numbers, first-come-first-served conflict resolution. — [BYU TechTransfer](https://techtransfer.byu.edu/technologies-section-new/real-time-conflict-management-in-multi-user-cad-environments)
- Olechowski group (Toronto) synchronous-CAD research: "preliminary analysis identified coupling effects to be a challenge in synchronous collaboration tasks". — [Mitacs project](https://www.mitacs.ca/our-projects/synchronous-collaboration-in-multi-user-cad-environments/)

### Inferences
- For an AI agent editing a parametric model, the Figma/Onshape LWW-per-object rule is risky because CAD features are coupled (a sketch change regenerates downstream); the BYU feature-lock model (lock the features the agent is touching, warn the human, roll back on conflict) plus Onshape's "work on a branch, merge when done" is the pattern most consistent with both industry practice and the MCP human-in-the-loop guidance. Strict turn-taking at *branch* granularity (agent writes to its own branch; human reviews and merges) avoids the live-conflict problem entirely.
- Cursor's experience (local checkpoints that drift from reality, users told to commit to git first) suggests undo for an agent should be backed by the real version store (git/Onshape history), not a side-car snapshot.

### Gaps
- No controlled study found comparing strict turn-taking vs concurrent editing between humans and an AI agent in any design tool; only inferences from human–human multiplayer systems.
- Cheng & Olechowski's specific paper on awareness/conflicts in synchronous cloud CAD (cited in CHI'26 as 2024) was not located directly.

---

## Area 5 — Local-first delivery of Python/OCCT tools to Windows non-programmers

### Takeaway
Concrete precedents exist at both ends: FreeCAD ships conda-forge-built, signed bundles (hundreds of MB: 1.1.4 AppImage 783 MB, macOS DMG 620–687 MB) and uses pixi for dev; CQ-editor ships both PyInstaller builds (reworked in 0.7.0) and conda-constructor "unstable" installers; GeoLibre Desktop ships Tauri + Python FastAPI sidecar as MSIX to the Microsoft Store and winget. Known pain: OCP wheels alone are 60–97 MB, PyInstaller output triggers heuristic AV detections without code signing, NSIS reinstalls may not replace a running sidecar, MSIX requires a CA cert or Store re-signing, and the Store forbids self-updating builds.

### Cited Findings
- cadquery-ocp 7.7.2.1 wheels: Windows cp312 listed at **59.4 MB**; other platform wheels ~88–97 MB (manylinux aarch64 cp310 96.8 MB, macOS arm64 87.7 MB); release yanked because `cadquery_vtk` dependency was broken; Python 3.9–3.12 supported. — [PyPI cadquery-ocp 7.7.2.1](https://pypi.org/project/cadquery-ocp/7.7.2.1); [PyPI ocp-vtk](https://pypi.org/project/ocp-vtk/)
- CadQuery docs recommend conda as "the better tested and more mature option" and offer a single installer for CadQuery + CQ-editor. — [CadQuery installation](https://cadquery.readthedocs.io/en/stable/installation.html)
- CQ-editor releases: 0.7.0 "Reworked the PyInstaller Builds", CI moved AppVeyor→GitHub Actions; "Unstable" pre-release "holds the latest of the conda constructor installers based on master"; 0.6.2 needed PyQt5 made explicit after a packaging change. — [CQ-editor releases](https://github.com/CadQuery/CQ-editor/releases); a hobbyist tested the standalone (nightly) CQ-editor installer in a VM first because it was unofficial. — [newscrewdriver](https://newscrewdriver.com/2024/04/27/cq-editor-standalone-on-vm-via-rdp/)
- FreeCAD: release builds come from conda-forge packages (same system produces Windows .7z, Linux AppImage, macOS DMG); wiki: "the easiest and quickest way to compile FreeCAD is with Pixi" (`pixi run configure/build/freecad`); one maintainer's pixi env has 339 dependency packages. — [prefix.dev: How FreeCAD uses pixi](https://prefix.dev/blog/how-freecad-uses-pixi); [FreeCAD wiki: Packaging](https://wiki.freecad.org/Packaging); [freecad-feedstock](https://github.com/looooo/freecad-feedstock)
- FreeCAD 1.1.4 release assets: Linux x86_64 AppImage **783 MB**, aarch64 721 MB, macOS arm64 DMG 620 MB, x86_64 687 MB; "Windows and macOS builds are signed by The FreeCAD project association AISBL". (Windows .exe/.7z sizes hidden behind "Show all 18 assets" — not captured.) — [FreeCAD releases](https://github.com/FreeCAD/FreeCAD/releases)
- Tauri v2 sidecar: list binaries under `bundle.externalBin`; files must carry the target triple suffix (e.g. `my-sidecar-x86_64-pc-windows-msvc.exe`); requires `tauri-plugin-shell` and a `shell:allow-execute` capability with `"sidecar": true`. — [Tauri v2: Embedding External Binaries](https://v2.tauri.app/develop/sidecar). Issue: with NSIS on Windows a PyInstaller sidecar "may not be replaced on a same-version reinstall", and a running sidecar makes the copy fail silently; workaround was an NSIS pre-install hook killing the process. — [tauri-apps/tauri #15134](https://github.com/tauri-apps/tauri/issues/15134)
- GeoLibre Desktop (real shipping example): Tauri app with optional Python FastAPI sidecar for heavy processing; `build-msix.ps1` wraps the Tauri build + sidecar with MakeAppx; Store build is re-signed by Microsoft, winget/sideload build is self-signed/CA-signed; **in-app updater compiled out of the Store build because the Store rejects apps that update themselves**; installable via `winget install OpenGeos.GeoLibre`; also in Microsoft Store, Mac App Store, Homebrew, AUR, COPR, Flatpak. — [GeoLibre GitHub](https://github.com/saikosis/geolibre); [geolibre.app downloads](https://geolibre.app/downloads/); [winget listing](https://wingetgui.com/apps/OpenGeos-GeoLibre); Microsoft's winapp CLI guide covers packaging a Tauri app as MSIX with package identity. — [Microsoft Learn: Tauri + winapp CLI](https://learn.microsoft.com/en-us/WINDOWS/APPS/dev-tools/winapp-cli/guides/tauri)
- MSIX constraints: sideloading requires the package be signed by a certificate trusted on the target machine ("There is no other way"); unsigned MSIX installs only with Developer Mode; signing cert subject must match manifest Publisher; Store route gives free signing and updates; new signed apps still get SmartScreen warnings until reputation builds. — [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/878524/how-to-destributed-unsigned-or-self-signed-msix-us); [pyappdist: MSIX](https://pyappdist.readthedocs.io/en/latest/platforms/windows-msix.html); [Microsoft Learn: publish first app](https://learn.microsoft.com/en-us/WINDOWS/APPS/package-and-deploy/publish-first-app); [winapp packaging CLI](https://learn.microsoft.com/ar-sa/windows/apps/dev-tools/winapp-cli/guides/packaging-cli)
- pixi-pack: packs a pixi environment and its conda packages into an archive; `pixi-unpack` rebuilds it without pixi/conda/micromamba; cross-build with `--platform win-64`; `--create-executable` yields a self-extracting `environment.ps1` on Windows; unpack only on the same platform. — [pixi-pack docs](https://pixi.prefix.dev/dev/deployment/pixi_pack/); [ArcGIS offline guide using pixi-pack](https://developers.arcgis.com/python/latest/guide/install-and-set-up/offline/)
- conda constructor builds full installers; conda-standalone (PyInstaller-built `conda.exe`) "is not intended for end-users". — [conda-standalone](https://github.com/conda/conda-standalone); [Medium: constructor walkthrough](https://medium.com/@Amet13/building-a-cross-platform-python-installer-using-conda-constructor-f91b70d393)
- PyInstaller antivirus pain: heuristic (`!ml`) detections attributed to self-extraction behaviour, missing version info and **no code signing**; fixes reported: submit false-positive to vendor, Defender exclusions, or **rebuild PyInstaller bootloaders** (Mapillary). — [microsoft/apm #487](https://github.com/microsoft/apm/issues/487); [discuss.python.org](https://discuss.python.org/t/pyinstaller-false-positive/43171); [Mapillary forum](https://forum.mapillary.com/t/a-trojan-in-mapillary-tools-win32-exe-solved/5185); [false-positive-malware-reporting](https://github.com/hankhank10/false-positive-malware-reporting)
- PyInstaller hidden imports (dynamic `importlib.import_module`) produce no warning, only runtime ImportError; use `--debug=imports`, `--collect-submodules`, module excludes to cut size. — [PyInstaller: when things go wrong](https://github.com/pyinstaller/pyinstaller/blob/v5.1/doc/when-things-go-wrong.rst)

### Inferences
- Realistic footprint for an OCCT+Python+Qt/web GUI app is several hundred MB (FreeCAD 600–800 MB on non-Windows platforms; OCP alone ~60–100 MB before VTK/numpy); the "size" pain is unavoidable, so the lever is update delta (MSIX/Store or Tauri updater), not initial size.
- The GeoLibre pattern (Tauri shell + Python sidecar, MSIX to Store + winget, dual builds) is the closest published precedent for "Python/OCCT to non-programmers on Windows without pip"; the trade-offs are documented (two build variants, Store update policy, sidecar replace bug on NSIS).
- Code signing is the common denominator for AV, SmartScreen and MSIX; FreeCAD solved it via an association (AISBL) certificate. Budget for an OV/EV certificate or Store submission from day one.

### Gaps
- No measured PyInstaller bundle size for a CadQuery/OCP app found (only wheel sizes); FreeCAD Windows .exe/.7z sizes not captured.
- No uv-based installer precedent found for OCCT apps (uv/`uv tool install` still presumes a developer-ish user); not researched further.
- GeoLibre details come partly from a mirror of its packaging README (ypbind.de) and third-party winget mirrors with inconsistent version numbers; treat specifics as plausible but unverified against the primary repo.

---

## Key Question A — Which review/approval UX has worked for engineers (not programmers)? What do they reject?

### Takeaway
Engineers accept: history-point compare with a visual overlay/slider plus a side-by-side feature list (Onshape), volume/face compare (SolidWorks), explicit file locks (PDM/Anchorpoint), and branches used mainly as "what-if scenarios". They reject: noisy histories (auto-saves, trivial toggles), geometry-only diffs without the "why", merge tools where you cannot pick individual changes, and workflows where it's easy to edit the wrong branch or lose a branch.

### Cited Findings
- Noise complaint: auto-saves/trivial edits produce look-alike versions (45 threads); "no way to know 'why'"; exported geometry "impossible to diff". — [CHI'26, arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)
- Branch/merge: per-tab strategies only, no cherry-pick within a tab. — [Onshape Help: Merging](https://cad.onshape.com/help/Content/Document/merging.htm); forum: accidental main-branch edits, deleted branches, failed merges; branches used for scenario comparison. — [Onshape forum](https://forum.onshape.com/discussion/comment/42657)
- Accepted compare idioms: blue/red overlay + slider + feature list. — [Onshape Help: Compare](https://cad.onshape.com/help/Content/Document/compare.htm); volume added/removed, face unchanged/unique/modified. — [Javelin](https://www.javelin-tech.com/blog/2019/04/solidworks-compare-drawcompare/)
- Locking over merging for binary CAD. — [Anchorpoint docs](https://docs.anchorpoint.app/git/cad)
- Design recommendation from the CHI'26 authors: AI-drafted change descriptions for the user to review, standardized templates, curated (not raw) history, AI "only… an assistive layer". — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)

### Inferences
- A proposal card for engineers should contain: one-sentence intent (the "why"), parameter/feature diff, a geometric overlay with slider, affected-downstream list, and Accept/Reject/Edit — mirroring what they already use in Onshape/SolidWorks rather than a git diff view.

### Gaps
- No quantitative usability study of any CAD review UI with engineers found.

---

## Key Question B — How to represent and show a "3D diff" so a designer decides in seconds?

### Takeaway
Shipping tools converge on three views: (a) colour-coded overlay of base vs target with a slider (Onshape), (b) volume delta (added/removed material) and face classification (SolidWorks), (c) 2-up before/after and a combined add/delete/unchanged view (Zoo Diff Viewer). Research adds that parameter-level diffs and the textual "why" are what geometry-only views miss, and that LLM/VLM-generated change summaries are a plausible assist.

### Cited Findings
- Onshape: blue Base / red Target overlay, slider, side-by-side feature list. — [Onshape Help: Compare](https://cad.onshape.com/help/Content/Document/compare.htm)
- SolidWorks: volume comparison (added/removed) and face comparison (unchanged/unique/modified); slow on big assemblies. — [Javelin](https://www.javelin-tech.com/blog/2019/04/solidworks-compare-drawcompare/); [SeaCAD](https://vn.seacadtech.com/blog/catching-every-detail-with-solidworks-compare-tool/)
- Zoo Diff Viewer: 2-up and combined (additions/deletions/unchanged) modes in the GitHub PR UI; alpha. — [docs.zoo.dev/diff-viewer](https://docs.zoo.dev/diff-viewer)
- GitHub native STL diff (2013). — [Leadwerks thread](https://www.leadwerks.com/community/topic/7620-github-adds-support-for-diffing-3d-files)
- Thangs and Fusion show geometric differences only; Onshape and SolidWorks show parametric + geometric. — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)
- Proposed: LLM/VLM candidate textual descriptions of modifications; extra visual dimensions/markers/colour for design evolution. — [arXiv 2602.09236](https://arxiv.org/html/2602.09236v1)
- Vendor opinion: semantic diff should list nodes added/removed, rewired mates/constraints/references, and attribute changes. — [NOVEDGE](https://novedge.com/blogs/design-news/geometry-aware-version-control-for-cad-graph-based-workflows-semantic-diffs-lfs-locks-and-deterministic-ci)

### Inferences
- For a seconds-level decision: default to the combined add(green)/remove(red)/unchanged(grey) boolean-difference view with a one-line intent and a number row (volume Δ, mass Δ, bbox Δ, count of affected features); provide 2-up and slider overlay as secondary views; keep the parameter diff textual.

### Gaps
- No empirical comparison of overlay vs 2-up vs boolean-difference views for decision speed found.

---

## Key Question C — Evidence on strict turn-taking vs concurrent editing with AI agents

### Takeaway
No direct evidence found. Human–human systems chose LWW per property/element with explicit guidance to avoid same-object concurrent edits (Figma, Onshape) or feature-level locks with rollback (BYU NX Connect); coding agents sidestep concurrency by working in sandboxes/branches with checkpoints and human merge.

### Cited Findings
- Figma LWW per property, same-text concurrent editing unsupported by design. — [Figma blog](https://www.figma.com/blog/how-figmas-multiplayer-technology-works/)
- Onshape: last committer wins on the same feature; avoid; use branches; "must be merged back – you can't choose". — [Onshape Tech Tip](https://www.onshape.com/en/resource-center/tech-tips/tech-tip-why-onshapes-live-collaboration-is-nothing-to-fear)
- BYU: lock–warn–rollback, OSN ordering, first-come wins. — [BYU TechTransfer](https://techtransfer.byu.edu/technologies-section-new/real-time-conflict-management-in-multi-user-cad-environments)
- Excalidraw: union + version/versionNonce; agent servers re-assert bot elements at higher version and report contested IDs. — [Excalidraw blog](https://plus.excalidraw.com/blog/building-excalidraw-p2p-collaboration-feature); [excalidraw-mcp-collab](https://www.remoteopenclaw.com/mcp/rus-artur4ik/excalidraw-mcp-collab)
- Devin: autonomous mode only inside an OS sandbox; edits outside still prompt. — [Devin CLI docs](https://docs.devin.ai/cli/reference/permissions); Cursor: checkpoints local, git recommended. — [Cursor docs](https://docs.cursor.com/agent/chat/checkpoints)
- MCP: human SHOULD be able to deny every invocation; show inputs before calling. — [MCP spec](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

### Inferences
- The defensible default for a CAD agent is strict turn-taking at the change-set level (agent works on a branch/sandbox copy, human merges), with optional live "follow mode" to watch; true concurrent editing of one feature tree by human and agent has no supporting evidence and contradicts Onshape's own guidance.

### Gaps
- No HCI study of human–agent concurrent vs turn-taking editing in CAD or design tools surfaced in searches.

---

## Key Question D — Precedents of shipping OCCT/Python desktop apps to Windows users without pip

### Takeaway
FreeCAD (conda-forge bundles, signed, hundreds of MB), CQ-editor (PyInstaller builds + conda-constructor installers), and GeoLibre Desktop (Tauri + Python sidecar, MSIX to Store/winget) are the concrete precedents; pixi-pack/constructor are the packaging routes for conda-based OCCT stacks; code signing and update policy are the recurring pains.

### Cited Findings
- FreeCAD: conda-forge-based bundles for Win/Linux/mac; 1.1.4 non-Windows bundles 620–783 MB; builds signed by FreeCAD AISBL. — [prefix.dev](https://prefix.dev/blog/how-freecad-uses-pixi); [FreeCAD releases](https://github.com/FreeCAD/FreeCAD/releases)
- CQ-editor: PyInstaller builds (0.7.0) and conda-constructor "Unstable" installers. — [CQ-editor releases](https://github.com/CadQuery/CQ-editor/releases)
- GeoLibre: Tauri + FastAPI sidecar, MSIX, Store + winget, dual builds, updater removed for Store. — [GeoLibre GitHub](https://github.com/saikosis/geolibre); [downloads](https://geolibre.app/downloads/)
- pixi-pack self-extracting `environment.ps1` for win-64. — [pixi-pack docs](https://pixi.prefix.dev/dev/deployment/pixi_pack/)
- Tauri sidecar NSIS replace bug. — [tauri #15134](https://github.com/tauri-apps/tauri/issues/15134)
- PyInstaller AV false positives and fixes (signing, bootloader rebuild). — [microsoft/apm #487](https://github.com/microsoft/apm/issues/487); [Mapillary](https://forum.mapillary.com/t/a-trojan-in-mapillary-tools-win32-exe-solved/5185)
- MSIX signing requirement; Store re-signing; SmartScreen reputation. — [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/878524/how-to-destributed-unsigned-or-self-signed-msix-us); [pyappdist MSIX](https://pyappdist.readthedocs.io/en/latest/platforms/windows-msix.html)

### Inferences
- A smaller OCCT/Python project can realistically follow CQ-editor (constructor or PyInstaller + NSIS, signed) for a quick path, or GeoLibre (Tauri shell + sidecar + MSIX/winget) for a polished one; neither avoids the ~0.3–0.8 GB footprint or the signing cost.

### Gaps
- No published size figures for a PyInstaller-frozen CadQuery/OCP app; no FreeCAD Windows asset sizes captured; no uv-based end-user installer precedent found.
