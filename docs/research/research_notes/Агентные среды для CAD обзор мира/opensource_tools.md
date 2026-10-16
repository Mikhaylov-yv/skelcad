# Open-source tools and frameworks connecting LLM agents with CAD (state as of 2026-10-12)

Research date: 2026-10-12. Star counts and "last release" values are as shown on GitHub/PyPI pages fetched on this date unless another date is given. Anything dated before 2025 is marked "(pre-2025)".

## KQ0. Project-by-project survey: what it does, architecture, kernel, license, activity, limitations

### Takeaway
The field has consolidated around three architectures: (a) "bridge" MCP servers that drive a running GUI CAD (FreeCAD, Fusion, SolidWorks, AutoCAD, KOMPAS, Onshape via REST) over RPC/COM; (b) "code-CAD toolbox" MCP servers/CLIs that execute build123d/CadQuery/OpenSCAD in a headless session and return measurements + renders (build123d-mcp, agentcad, text-to-cad/cadgen, OpenSCAD MCPs); and (c) multi-agent pipelines (Multi-Agent-CAD, CADSmith, CAD/CAE Copilot) that add planner/coder/judge roles and geometric validation. Almost everything open-source sits on OpenCASCADE (OCCT) via OCP; Rust alternatives (Fornjot, CADmium) were archived in 2025–2026, truck is alive, and Zoo's engine is hosted/proprietary.

### Cited Findings

**A. FreeCAD MCP family (bridge to running GUI)**

- neka-nat/freecad-mcp: "Control FreeCAD from Claude Desktop and other MCP clients"; "two components: an addon running inside FreeCAD and an MCP server launched by your client"; addon exposes an RPC server started from the "MCP Addon workbench"; MIT; 2.8k stars, 341 forks, 222 commits, 22 open issues, 31 open PRs; Releases section empty; install = copy `addon/FreeCADMCP` into FreeCAD Mod dir + launch server with `uvx freecad-mcp`; "keep FreeCAD open with its RPC server running"; guides cover "GUI execution, background jobs, headless scripts, timeout troubleshooting" and "FEM analysis" — [GitHub](https://github.com/neka-nat/freecad-mcp)
- Tool list for neka-nat (aggregator view): 11 tools incl. arbitrary Python execution and `run_fem_analysis` ("Run the CalculiX solver on an existing Fem::FemAnalysis and return summary results"); RPC on localhost:9875 — [mcp.so listing](https://mcp.so/zh/servers/freecad-mcp); [policylayer](https://policylayer.com/tools/neka-nat-freecad-mcp/run-fem-analysis)
- Third-party 2026 guide on neka-nat (updated June 2026): "GUI required… screenshots need an active 3D view. Headless use is an open issue"; covers FreeCAD 1.0 and 1.1; "Every mutating call returns a screenshot by default" → issue "Excessive Token Usage Due to Image Returns" led to `--only-text-feedback` flag; `execute_code` runs arbitrary Python; Remote Connections bind `0.0.0.0` with IP whitelist; "No export tool: STEP/STL export requires execute_code"; "Complex sketches and fillet chains are weaker. The maintainer's April 2026 comparison says CadQuery tends to win on precision"; "FEM: Results are a first-pass sanity check, not a reviewed simulation"; macOS Mod path is version-specific (`v1-1/Mod`, `v1-0/Mod`); snap FreeCAD had PySide2/shiboken2 conflicts — [mcp.directory guide](https://mcp.directory/blog/freecad-mcp-complete-guide-2026)
- Variants: tessalabs-space/freecad-mcp (addon serves XML-RPC on localhost:9875 + stdio server on fastmcp, credits neka-nat); spkane/freecad-mcp (pip `freecad-robust-mcp`, "xmlrpc, socket, and embedded modes"); theosib/FreeCAD-MCP-Server (TCP bridge + addon) — [search summary with repo URLs](https://lobehub.com/mcp/tessalabs-space-freecad-mcp), [spkane](https://lobehub.com/mcp/spkane-freecad-mcp), [theosib](https://glama.ai/mcp/servers/theosib/FreeCAD-MCP-Server)
- theosib/FreeCAD-MCP-Server details: stdio bridge → JSON-RPC over TCP port 9876 → addon with "threaded TCP server… runs requests on FreeCAD's main thread through a QTimer-polled work queue"; tools `get_document_graph` (feature tree with validity state), `get_sketch_diagnostics` ("sketch constraint health (DOF, conflicts, redundancies)"), `tracked_recompute` ("recompute with a before/after diff of errors"), `analyze_shape`, `execute_script`, `get_screenshot`; "no dedicated undo tool"; LGPL-2.1-or-later; 34 stars, 2 commits — [GitHub](https://github.com/theosib/FreeCAD-MCP-Server)
- sandraschi/freecad-mcp: 85 tools; CalculiX FEM "stress, strain, displacement, and safety factor", "10 material presets, automatic meshing via Gmsh, and an end-to-end run_fem_analysis tool"; Ollama local-LLM integration; OpenFOAM via Docker; prerequisites FreeCAD 1.1.1+, PrusaSlicer 2.8+; endpoint `http://localhost:10944/sse`; MIT; Windows-oriented scripts (`start.ps1`, winget); Glama: "This server cannot be deployed", responsiveness "Slow" — [Glama](https://glama.ai/mcp/servers/sandraschi/freecad-mcp)
- blwfish/freecad-mcp claims "30+ tools covering parametric modeling, PartDesign operations, CAM toolpath generation, and mesh manipulation"; bonninr/freecad_mcp last push 2025-03-20 — [claudemarketplaces](https://claudemarketplaces.com/mcp/blwfish/freecad-mcp), [gittrend](https://gittrend.io/repo/bonninr/freecad_mcp)
- AnkusDrive (gchen19): CLI + MCP driving FreeCAD Python API with FEM tools `fem_new_analysis`, `fem_run`, `fem_results`; targets FreeCAD 1.1.x; ~3 stars — [README](https://raw.githubusercontent.com/gchen19/AnkusDrive/main/README.md)
- JupyterCAD MCP exists ("lets LLMs control JupyterCAD using natural language") — [mdskills listing](https://www.mdskills.ai/mcp-servers/jupytercad-mcp?tab=source)
- Independent FreeCAD MCP bridge (blog, 2026-08-06): author built own MCP server "inside FreeCAD's embedded Python runtime", stdio + remote HTTP transports (for ChatGPT web via reverse proxy); behaviour shaped by `LLM_USAGE.md` + a Codex skill; "the model needs a working discipline: inspect before editing, prefer parametric and mutable features" — [tspi.at](https://www.tspi.at/2026/08/06/llmfreecad.html)

**B. build123d / CadQuery toolbox servers and CLIs**

- pzfreo/build123d-mcp: "MCP server for build123d to improve AI cognition when creating 3D CAD models"; "Execute build123d code in a persistent CAD session"; stdio = "each app process its own isolated session", HTTP = one shared session; measures volume/area/bbox/topology/COM; finds holes, bosses, countersinks, hole patterns; "checks printability, fit/alignment, and export validity"; renders PNG/SVG/DXF and "2D engineering drawing previews"; tools incl. `validate()`, `compare(kind="shape")`, `edit_feature`, `find_candidates`, `interface_features()`, `last_error`, `install_skill`, "Save and restore session snapshots"; Apache-2.0; 112 stars, 560 commits; limitations: "HTTP mode has no built-in authentication and uses one shared CAD session", `edit_feature` refuses counterbored/countersunk holes; claims "On the public CADGenBench leaderboard in June 2026, using build123d-mcp raised the same model's score from 0.360 to 0.457 and CAD validity from 88% to 100%" — [GitHub](https://github.com/pzfreo/build123d-mcp)
- build123d-mcp PyPI: latest 0.3.90 released 2026-09-25; first release 0.1.0 on 2026-05-01; ~90 releases since; Python >=3.11,<3.15; author Paul Fremantle — [PyPI](https://pypi.org/project/build123d-mcp/)
- jdilla1277/agentcad: "CAD CLI and MCP server for AI agents"; build123d default runtime, CadQuery via `agentcad[cadquery]` extra; kernel OpenCascade via OCP; CLI `run --label` (versioned STEP + metrics), `measure`, `check-spec` ("compares cylindrical features against a spec checklist"), `inspect`, `diff` (shared/reference-only/candidate-only volume), `view` (A/B), `parts`; MCP via `python -m agentcad.mcp`; Apache-2.0 (LICENSE file); 158 stars, 16 forks, 201 commits, 34 open issues; v0.6.0 on PyPI 2026-09-11; classifier "3 - Alpha"; Python 3.10–3.12 only ("OpenCascade bindings do not support 3.13+"); launched Product Hunt 2026-06-09 — [GitHub](https://github.com/jdilla1277/agentcad), [PyPI](https://pypi.org/project/agentcad/), [Product Hunt](https://www.producthunt.com/products/agentcad/makers)
  - Note: depscope lists agentcad PyPI license as "BSL-1.17", conflicting with Apache-2.0 on GitHub/PyPI; treat GitHub LICENSE as authoritative — [depscope](https://depscope.dev/pkg/pypi/agentcad)
- earthtojake/text-to-cad ("Give your agent CAD superpowers"): plugin/skills for Claude Code, Codex, Cursor, Gemini, Grok; skills for CAD, STEP, engineering drawings, DXF, URDF/SRDF/SDF, SendCutSend, DfAM, DFM, G-code, Bambu; kernel OCP (OpenCascade Python binding), build123d 0.11; `cadgen` PyPI package provides `cadgen mcp`, `cadgen viewer`, build daemon; MIT; 19.5k stars, 1.9k forks, 1,456 commits; requires Python 3.11+ and Node 20+; "Windows 11 Smart App Control blocks the unsigned OCP native module"; first start downloads CAD runtime; telemetry on by default — [GitHub](https://github.com/earthtojake/text-to-cad)
- rishigundakaram/cadquery-mcp-server: main tool `verify_cad_query` (PASS/FAIL against description); `generate_cad_query` "only a stub"; `uv sync --extra cad` — [Glama](https://glama.ai/mcp/servers/@rishigundakaram/cadquery-mcp-server)
- Library status: build123d latest v0.11.1 (dev 0.11.2.dev2 dated 2026-07-07); CadQuery 2.6.0 (2025-10-06), 2.6.1 (2025-10-28), later 2.7.0/2.8.0 on Anaconda — [newreleases](https://newreleases.io/project/github/gumyr/build123d/release/v0.11.1), [piwheels](https://www.piwheels.org/project/cadquery), [anaconda](https://anaconda.org/channels/CadQuery/packages/cadquery/overview)

**C. OpenSCAD MCP servers** (all MIT per Glama): gemini-cad-mcp (ssfdre38; SCAD → watertight STL, photo-to-model), RobertCoop (PNG multi-angle + animation, PyPI), jhacksman (SCAD/STL/CSG/3MF export, "headless Docker support"), AaronGoldsmith/mcp-printable (printability checks, Blender link, PyPI), rahulgarg123 (npm, headless PNG), fboldo (npm, PNG + STL), dkpoulsen (npm, STL/OFF/AMF/3MF/CSG, syntax validation), MeshCue Forge, BambuStudio MCP — [Glama OpenSCAD list](https://glama.ai/mcp/servers/integrations/openscad); quellant/openscad-mcp on FastMCP with multi-view render — [Glama](https://glama.ai/mcp/servers/@quellant/openscad-mcp/blob/8e1e81fb43846e02a2956b61355ffd6e27181600/README.md)
- JSCAD: no MCP server found; OpenJSCAD.org last push 2026-05-07, 142 open issues — [gittrend](https://gittrend.io/repo/jscad/OpenJSCAD.org)

**D. Zoo (KCL)**

- KittyCAD/mcp (zoo-mcp): "An MCP server housing various Zoo built utilities"; MIT; 10 stars; tools `execute_kcl`, `exec_kcl_project`, `mock_execute_kcl`, `import_cad_file`, `start/get/stop_modeling_session`, `snapshot`; install `uvx zoo-mcp` or "Prebuilt PyInstaller binaries… for Linux, macOS, and Windows, so no Python toolchain is needed" (not code-signed); requires `ZOO_API_TOKEN`; "Only one modeling session is allowed per server process"; inline `kcl_code` only self-contained — [GitHub](https://github.com/KittyCAD/zoo-mcp)
- Zoo docs: hosted use counts as API usage/billing; needs API token — [zoo.dev/docs](https://zoo.dev/docs/developer-tools/mcp)
- KittyCAD/modeling-app (Design Studio): MIT app, but the 3D view "is just a video stream from our hosted geometry engine" (engine not open); 1.3k stars; KCL is text, version-controllable — [GitHub](https://github.com/KittyCAD/modeling-app)

**E. Proprietary-CAD bridges (open-source servers)**

- faust-machines/fusion360-mcp-server: "Beta"; stdio MCP → TCP :9876 → Fusion add-in running on main thread via CustomEvent; 93 tools incl. sketch constraints/dimensions, features, sheet metal, "assembly (components, joints, rigid groups)", parameters, CAM, "perception (viewport render)", mock mode; no drawings category; MIT; 117 stars; README "Last updated: 2026-09-16"; limits: TCP unauthenticated, "All units are centimeters", "batching reportedly crashes the add-in", 30 s add-in timeout, "mutation commands are never auto-retried", tested only Fusion 2705.1.15 macOS arm64; install `uvx fusion360-mcp-server --mode socket` — [GitHub](https://github.com/faust-machines/fusion360-mcp-server)
- SolidWorks: all Windows/COM. haunchen/solidworks-mcp (Streamable HTTP on LAN, tested SW2021); SolidworksMCP-python (109 tools, "under active construction", mock adapter); yimu0824 (SW2020+, STEP/IGES/STL export); keecherr (22 tools, SW2023–2025); SolidPilot = AGPL-3.0 fork of eyfel/mcp-server-solidworks ("CAD-neutral intermediate representation, then a deterministic compiler lowers it into concrete SolidWorks operations"; ~3 dozen tools incl. drawing; needs Windows, SW2026, .NET 4.8, C# layer on localhost:5000); arhamgarg/solidworks-mcp (AGPL, LLM generates pywin32 scripts) — [Glama search](https://glama.ai/mcp/servers/y36q5h4ov7), [SolidPilot](https://glama.ai/mcp/servers/ihefudnp5d), [haunchen](https://mcpservers.org/pt-BR/servers/haunchen/solidworks-mcp)
- daobataotie/CAD-MCP (AutoCAD/GstarCAD/ZWCAD): Windows-only pywin32 COM; FastMCP; 35 tools incl. drawing primitives, dimensions, hatch, layers, blocks, DWG/DXF, "undo/redo", `send_command`; stdio or streamable-http (multi-client, one CAD instance); MIT; 595 stars, 12 commits — [GitHub](https://github.com/daobataotie/CAD-MCP)
- KOMPAS-3D: MCP-KOMPAS-3D (Habr, author lya_ocean): Python stdio server → COM calls on `ComWorker` thread; 2D-only (drawings/fragments); tools for geometry, editing, measurement, screenshot, `execute_python_script`, `batch_execute`, `reconnect()`; API7 unreliable for views/layers so API5 used; slow on thousands of objects; 19 comments, +28 score; no GitHub URL/license in article — [Habr](https://habr.com/en/articles/987312), [vc.ru](https://vc.ru/dev/2696636-avtomatizatsiya-kompas-3d-s-pomoshchyu-python-i-mcp-dlya-ai-agentov). kompas-3d-ai-bridge: "deterministic execution layer" via MCP + COM/API7 for "parts, assemblies, and 3D documents"; Windows, pywin32; version "1.1.14_CAP2"; "not an official ASCON product" — [Glama](https://glama.ai/mcp/servers/jyv0wct90l)
- Onshape: altendky/onshape-mcp (Rust; sketches, extrude/revolve/sweep/fillet, planes, Part Studio screenshots, STL/STEP export, FeatureScript writing/debugging, full REST API; no assemblies/mates/drawings mentioned; Apache-2.0 OR MIT; 19 stars; `npx --yes onshape-mcp` or prebuilt binaries; own OAuth app required; "Early development"; ChatGPT connectivity fails (issue #546)) — [GitHub](https://github.com/altendky/onshape-mcp). Another listing claims an "enhanced" Onshape server with 45 tools — [Glama](https://glama.ai/mcp/servers/duxkig1kpw). PTC has no official MCP server — [innfactory](https://innfactory.ai/en/services/companygpt/integrations/onshape/)

**F. Multi-agent pipelines**

- Pan-Chera/Multi-Agent-CAD (MAC): planning/geometry/coding/repair stages, each with configurable OpenAI-compatible model; LangGraph orchestration; Aider for repair; v2 adds independent Judge + visual verification; build123d/OpenCascade; vendored `packages/cadpy` from earthtojake/text-to-cad; outputs STEP/STL/GLB/URDF; multi-part assemblies "experimental"/"technology preview"; MIT; ~1.0k stars, 95 forks, 60 commits; benchmark (10 prompts/141 features): MAC v1 Qwen 3.7 140/141 at 0.90M tokens ($1.43) vs CAD Skill reproduction 138/141 at 103.95M tokens ($18.59) — "about 116× fewer tokens"; "Web UI executes generated Python with the user's permissions"; "does not sandbox the subprocess"; conda install, Windows not in CI — [GitHub](https://github.com/Pan-Chera/Multi-Agent-CAD)
- CADSmith (arXiv 2603.26512, submitted 2026-03-27; Barkley, Loghmani, Barati Farimani, CMU): Planner/Coder/Executor/Validator/Refiner agents generating CadQuery; inner loop fixes execution errors; outer loop = OpenCASCADE measurements (bbox, volume, solid validity) + VLM Judge (Claude Opus judge vs Sonnet generators); RAG over API docs; 100-prompt benchmark: execution 95%→100%, median IoU 0.8085→0.9629, Chamfer 28.37→0.74; no code link on abstract page — [arXiv](https://arxiv.org/abs/2603.26512)
- armpro24-blip/cad-cae-copilot ("AI-native CAD/CAE/CAX workbench"): FastAPI backend + React workbench + MCP server; `.aieng` package format; build123d on OCP; CalculiX solver, Gmsh meshing; tools `cad.execute_build123d` (replace/append), `cad.get_source`, `aieng.insert_standard_part`, `aieng.generate_bom`, 51 materials; "CAE setup and solver runs are separate approval-gated steps"; "Every edit returns a regression diff and a critique diff"; design rules `require(...)` fail build with structured violation; "credibility tier… production_ready is never assumed"; MIT; 71 stars, 899 commits; analyses: linear static, modal, linear buckling, steady-state thermal, one-way thermal-stress; "Assembly contact and bolt preload are proxy-only"; 3D SIMP experimental; install Docker `ghcr.io/armpro24-blip/aieng-workbench:latest`, Codespaces, or `uvx` from tag v0.1.0-alpha.4 ("PyPI publication is not planned") — [GitHub](https://github.com/armpro24-blip/cad-cae-copilot)
- Research-only (no code found): TOOLCAD (arXiv 2604.07960, 2026-04-09, ACL 2026 submission; tool-using LLM + "CAD modeling gym" + curriculum RL) — [arXiv](https://arxiv.org/abs/2604.07960); "Self-Improving CAD Generation Agents with FEA as Feedback" (arXiv 2605.17448, 2026-05-17/27, WIP): brief → "fully assembled, multi-part STEP file" validated by FEA; "Codex (GPT-5.5) and Claude Code (Opus-4.7) agents did not produce a single strict-passing artifact in the main first-attempt sweep"; best config ~20% of typed requirements — [arXiv](https://arxiv.org/abs/2605.17448); FeaGPT (arXiv 2510.21993, Oct 2025) Gmsh Python API + CalculiX input generation — [arXiv](https://arxiv.org/pdf/2510.21993); CADEngBench (arXiv 2608.09296) evaluates "Parametric Design, Assembly Reasoning, and Physics Simulation" — [arXiv](https://arxiv.org/pdf/2608.09296)

**G. FEA / CAE integration**

- Cai-aa/CAE-Agent-Hub: MCP servers for Abaqus, Fluent, Workbench/Mechanical, AEDT, HyperWorks, LAMMPS, OVITO, CalculiX (wraps `ccx`, parses `.inp`, exports results), "FEP Agent Hub" (FreeCAD + Elmer FEM + ParaView); ~25 Abaqus skills; browser viewer on `result_mesh.json`; MIT; ~1.0k stars, 132 forks, 107 commits; Windows/PowerShell install; "Installing an MCP server does not install the commercial CAE software" — [GitHub](https://github.com/Cai-aa/cae-agent-hub)
- @casys/mcp-calculix (JSR, MIT, v0.8.6): "STEP file → SHA-256 snapshot → Gmsh tetrahedral mesh → generated CalculiX deck → parsed results → optional recorded evidence → MCP App"; linear static, modal, buckling, Norton creep, coupled temp-displacement; "does not approve designs or make safety or compliance judgments"; read-only MCP App results viewer; Docker (loopback HTTP :3015) or `deno run jsr:@casys/mcp-calculix/server --stdio`; ~23 downloads/week; source github.com/superWorldSavior/mcp-calculix — [JSR](https://jsr.io/@casys/mcp-calculix)
- benchwire/mcp-fea: STEP + plain-English question → mesh + CalculiX solve on Modal as async MCP task; reports von Mises, factor of safety — [Glama](https://glama.ai/mcp/servers/benchwire/mcp-fea)
- CalculiX forum: "CAD-CAE-Copilot with calculix" thread (July 2026, no replies); another post: AI MCP server for bridge/building analysis tested with CalculiX 2.22 + FreeCAD 1.1 on Windows 11 — [calculix.discourse.group](https://calculix.discourse.group/t/ai-mcp-server-for-analysis-of-bridges-and-buildings-with-b32r/4037)
- PyCCX: no agent/MCP integration found.

**H. Benchmarks**

- huggingface/cadgenbench: tasks Generation (drawing → model) and Editing (change to STEP); metrics validity gate, F1 + volume IoU, interface match (keep-in/keep-out), Betti numbers; Apache-2.0; 141 stars; reference baseline "iterative agent that writes build123d code, with CadQuery also supported"; leaderboard Space HuggingAI4Engineering — [GitHub](https://github.com/huggingface/cadgenbench)
- Leaderboard snapshots (third-party): 2026-08-12: 19 validated submissions, top 59.6% Claude Opus-based build123d agent; 2026-09-23: "Godela at 84.5%"; "each submission can include a different agent, CAD library, prompt, and tool configuration" — [BenchLM](https://benchlm.ai/benchmarks/cadgenbenchgeneration). Godela source/licence not found.

### Inferences
- Nearly all open-source agent-CAD stacks resolve to OCCT via OCP/build123d/CadQuery or FreeCAD; the choice is really between "live GUI bridge" (editable feature tree, GUI-bound) and "headless code-CAD" (reproducible, scriptable, no parametric GUI tree).
- Star counts show attention is on the skill/plugin approach (text-to-cad 19.5k) and FreeCAD bridge (2.8k) rather than on dedicated MCP toolboxes (build123d-mcp 112, agentcad 158).
- Multi-agent pipelines are converging on the same validation recipe: kernel measurements (volume/bbox/validity) + VLM judge on renders + retry loop.

### Gaps
- Exact last-commit dates were not visible on fetched GitHub pages for most repos (only PyPI dates and README "last updated" lines).
- CADSmith code: no repository found.
- Godela (CADGenBench #1): no public code or license found.
- KOMPAS MCP-KOMPAS-3D GitHub URL and license not found.
- OpenSCAD mailing-list thread on MCP experience (Jan 2026) timed out twice; not read.

## KQ1. Which projects go beyond single-part generation (assemblies, constraints/mates, drawings, design rules, FEA)?

### Takeaway
Only a handful do: Fusion360 MCP (joints, rigid groups, sketch constraints, CAM), Multi-Agent-CAD (experimental multi-part assemblies + URDF), CAD/CAE Copilot (FEA, BOM, standard parts, design rules), theosib FreeCAD server (sketch constraint diagnostics), text-to-cad (drawings, DFM/DfAM, URDF/SDF), build123d-mcp (drawing previews), FreeCAD MCPs with CalculiX, and SolidPilot/CAD-MCP (2D drawings). True constraint-solver-driven assemblies are rare; most "assemblies" are positioned compounds.

### Cited Findings
- Fusion360 MCP: 93 tools incl. "Sketching (rectangles, circles, splines, constraints, dimensions)", "assembly (components, joints, rigid groups)", "sheet metal", "CAM/manufacturing", "parameters"; no drawings category — [GitHub](https://github.com/faust-machines/fusion360-mcp-server)
- Multi-Agent-CAD: "multi-part mechanical assemblies… exports STEP, STL, GLB, and URDF"; assembly outputs "Separate-part geometry, assembled files, URDF, manifests, and QA artifacts"; "experimental"/"technology preview"; "Generated geometry and joints should be validated before manufacturing or simulation" — [GitHub](https://github.com/Pan-Chera/Multi-Agent-CAD)
- CAD/CAE Copilot: text-to-CAE with "Material, loads, constraints, mesh, and solver artifacts… stored beside the CAD model"; `aieng.insert_standard_part`, `aieng.generate_bom`; design rules via `require(...)`; "Assembly contact and bolt preload are proxy-only" — [GitHub](https://github.com/armpro24-blip/cad-cae-copilot)
- theosib FreeCAD server: `get_sketch_diagnostics` reports "DOF, conflicts, redundancies"; `get_document_graph` gives feature tree with "dependencies, and validity state" — [GitHub](https://github.com/theosib/FreeCAD-MCP-Server)
- text-to-cad skills: "engineering drawings, DXF, URDF, SRDF, SDF, SendCutSend, DfAM check, DFM, G-code" — [GitHub](https://github.com/earthtojake/text-to-cad)
- build123d-mcp: "2D engineering drawing previews" + `drawing` skill; checks "printability, fit/alignment"; assemblies/joints not mentioned — [GitHub](https://github.com/pzfreo/build123d-mcp)
- FreeCAD neka-nat `run_fem_analysis` on existing `Fem::FemAnalysis` with Gmsh mesh; issue #158 (2026-09-30): "run_fem_analysis prerequisites are stale for FreeCAD 1.x, and ConstraintForce.Force is silently off by 1000x" — [Issues](https://github.com/neka-nat/freecad-mcp/issues)
- sandraschi/freecad-mcp: CalculiX FEM with Gmsh auto-meshing, BIM, OpenFOAM — [Glama](https://glama.ai/mcp/servers/sandraschi/freecad-mcp)
- SolidPilot: tools "for modeling, sketching, drawing, and export" — [Glama](https://glama.ai/mcp/servers/ihefudnp5d); CAD-MCP: 2D dimensions, hatch, layers, blocks — [GitHub](https://github.com/daobataotie/CAD-MCP); KOMPAS MCP: 2D only — [Habr](https://habr.com/en/articles/987312); kompas-3d-ai-bridge claims "parts, assemblies, and 3D documents" — [Glama](https://glama.ai/mcp/servers/jyv0wct90l)
- Library-level assembly support available to agents: CadQuery Assembly constraints Point, Axis, Plane, PointInPlane, PointOnLine, FixedPoint, FixedRotation, FixedAxis; `solve()` minimizes cost functions; "Multiple solutions can exist, and the initial locations determine which one is reached"; export STEP and OCCT XML — [CadQuery docs](https://cadquery.readthedocs.io/en/latest/assy.html). build123d joints: RigidJoint, RevoluteJoint, LinearJoint, CylindricalJoint, BallJoint; `connect_to()` "is a one-time repositioning", no constraint solver mentioned — [build123d docs](https://build123d.readthedocs.io/en/latest/joints.html)
- Research: FEA-as-feedback paper targets "fully assembled, multi-part STEP file" but agents produced zero strict-passing artifacts first attempt — [arXiv](https://arxiv.org/abs/2605.17448); CADEngBench evaluates assembly reasoning and physics — [arXiv](https://arxiv.org/pdf/2608.09296)

### Inferences
- Assembly support in open source is either (a) borrowed from the host CAD (Fusion joints, FreeCAD/Assembly via execute_code) or (b) code-level positioning (build123d joints, CadQuery cost-function solver), not a constraint-managed assembly model exposed as agent tools.
- FEA integration is the most mature "beyond-part" capability (three independent CalculiX/Gmsh routes), but all authors warn results are not reviewed simulations.

### Gaps
- No data on whether any open-source agent tool exposes FreeCAD Assembly workbench (1.0+) joints as first-class tools.
- Drawing generation quality (dimensioning, GD&T) is not evaluated anywhere found.

## KQ2. How do they let a human review and control the agent's output (viewer, diff, approval, undo)?

### Takeaway
Review is mostly visual (screenshots/renders/local viewers) plus kernel metrics; versioning/diff exists in agentcad (labelled STEP versions, volume diff, A/B viewer) and CAD/CAE Copilot (regression/critique diffs, approval-gated steps, elicitation); undo is largely absent except CAD-MCP's undo/redo tool and FreeCAD's native document transactions reached via scripts.

### Cited Findings
- agentcad: "Each run is versioned with --label"; `diff` compares "shared, reference-only, and candidate-only volume"; `view` "synchronized A/B comparison"; viewer preloads A (previous)/B (current) for "A/B, side-by-side, overlay, and Parts-tab change review"; "failed builds keep the last good model visible"; turntable GIF; binds 127.0.0.1 — [GitHub](https://github.com/jdilla1277/agentcad)
- CAD/CAE Copilot: "Approval for gated actions works through the client's own prompt, the workbench viewer or VS Code card, or headless MCP elicitation, with a fail-safe deny"; "Every edit returns a regression diff and a critique diff"; "Low agreement on LLM-judged steps routes to asking the user" — [GitHub](https://github.com/armpro24-blip/cad-cae-copilot)
- build123d-mcp: "Save and restore session snapshots"; `compare(kind="shape")`; PNG/SVG/DXF renders; `last_error` — [GitHub](https://github.com/pzfreo/build123d-mcp)
- text-to-cad: "CAD Viewer shows models as viewer cards in Claude Code and Claude Desktop, as a CAD tab in Codex, and as a link in Gemini, Grok, and terminal-based setups" — [GitHub](https://github.com/earthtojake/text-to-cad)
- neka-nat freecad-mcp: human watches live FreeCAD GUI; every mutating call returns a screenshot (opt-out `--only-text-feedback`) — [mcp.directory](https://mcp.directory/blog/freecad-mcp-complete-guide-2026); no undo/review in README — [GitHub](https://github.com/neka-nat/freecad-mcp)
- theosib: `tracked_recompute` "reports changes but does not revert them"; no undo tool — [GitHub](https://github.com/theosib/FreeCAD-MCP-Server)
- CAD-MCP (AutoCAD): tools include "undo/redo" and screenshot — [GitHub](https://github.com/daobataotie/CAD-MCP)
- Fusion360 MCP: "perception (viewport render)"; "mutation commands are never auto-retried" — [GitHub](https://github.com/faust-machines/fusion360-mcp-server)
- Zoo MCP: `snapshot` tool; KCL is text so diffs are git diffs — [GitHub](https://github.com/KittyCAD/zoo-mcp), [modeling-app](https://github.com/KittyCAD/modeling-app)
- casys mcp-calculix: read-only MCP App results viewer, "never runs a solve"; recorded runs with "idempotent request identity and replay validation" — [JSR](https://jsr.io/@casys/mcp-calculix)
- Multi-Agent-CAD: optional browser UI with 3D preview for single parts; QA artifacts/manifests — [GitHub](https://github.com/Pan-Chera/Multi-Agent-CAD)
- Practitioner guidance (Vagon, 2026-10): "Save versioned .FCStd checkpoints before substantial changes"; document transactions "are not a universal rollback for exported files, external scripts, or every addon operation"; "After a failed operation, check what changed first, since repeating a request can add duplicate features"; "Do not estimate dimensions from screenshot pixels" — [vagon.io](https://www.vagon.io/blog/how-to-use-freecad-with-claude-mcp-computer-use)
- Practitioner (tspi.at): "Screenshots served as an independent check, and the author notes that the agent could often correct its own calculations after seeing a rendered error" — [tspi.at](https://www.tspi.at/2026/08/06/llmfreecad.html)
- HN commenters' verification tips: "Add unit-style checks to OpenSCAD: maximum overhang slope, null intersections between parts, and expected volume"; "Use cutaway or slice views, since plain renders hide internal detail"; "Have multiple models review each other's specs and code" — [HN 48234090](https://hn.svelte.dev/item/48234090)
- Multi-model/ocp-vscode: build123d joints have `symbol` with "built-in support in the ocp-vscode viewer" — [build123d docs](https://build123d.readthedocs.io/en/latest/joints.html)

### Inferences
- The code-CAD approach gives free versioning via text diffs (git), while GUI bridges rely on the CAD's own undo/transactions, which no MCP server exposes cleanly.
- Only CAD/CAE Copilot implements explicit approval gating; everywhere else "approval" is the MCP client's generic tool-permission prompt.

### Gaps
- No open-source project found that renders a geometric diff (added/removed faces) visually; agentcad's diff is volumetric only.

## KQ3. What failure modes and limitations do users report (hangs, bad geometry, non-determinism, GUI dependence)?

### Takeaway
Reported issues cluster into: GUI-thread hangs/timeouts and modal dialogs in bridge servers; platform/version path fragility (Windows/macOS Mod dirs, FreeCAD 1.x); screenshot capture failures and token blow-up; sign/coordinate-frame geometry errors that pass kernel checks; weak spatial perception from downscaled renders; loss of parametric history when scripting; and high token/budget cost.

### Cited Findings
- neka-nat issues: #115 (2026-08-09) "GUI-dispatched calls can hang indefinitely, with no timeout or recovery, after a FreeCAD-side exception leaves a broken FeaturePython object"; #148 (2026-09-21) CAM post-processor "creates unclose-able dialog"; #135 (2026-09-10) "Screenshots are black or artifact-laden on NVIDIA + Hyprland/Wayland"; #157 (2026-09-30) `execute_code_headless` fails on Windows due to POSIX shlex; #140 (2026-09-14) Windows + FreeCAD 1.1.x RPC "gives no startup feedback"; #116 Windows path missing `v1-1`; #158 FEM force "silently off by 1000x"; #146 "No supported install/update path"; #14 (2025-05-12) "Support headless FreeCAD" still open — [Issues](https://github.com/neka-nat/freecad-mcp/issues)
- neka-nat troubleshooting: RPC "only connects when a tool fires, so a healthy-looking config can still fail"; "macOS GUI apps may not inherit the shell PATH"; "Blank white screenshots on Windows" (fixed); snap PySide2 conflicts — [mcp.directory](https://mcp.directory/blog/freecad-mcp-complete-guide-2026)
- Fusion360 MCP: "batching reportedly crashes the add-in"; 30 s timeout; unauthenticated TCP — [GitHub](https://github.com/faust-machines/fusion360-mcp-server)
- Vagon: "After a timeout, the operation may still be running on the GUI thread, so check job or RPC status before retrying"; "Python can create a solid without creating the Sketch, Pad, and Pocket history you expect"; "Labels can be edited and may not uniquely identify an object"; "script success does not certify geometry validity" — [vagon.io](https://www.vagon.io/blog/how-to-use-freecad-with-claude-mcp-computer-use)
- tspi.at (2026-08-06): failures were "wrong-direction extrusions, missing cutouts, hidden collisions, misplaced bodies, and operations that succeeded mathematically but made no mechanical sense", attributed to "subtle sign and coordinate-frame errors"; ChatGPT web "did not reliably consume screenshots"; "One engineering task used roughly half of a monthly Codex allowance"; "Local models are not yet capable enough" — [tspi.at](https://www.tspi.at/2026/08/06/llmfreecad.html)
- HN (Show HN: AI CAD Harness, ~May 2026): ex-SolidWorks AE "tried a FreeCAD MCP driven by Claude Code and 'got mixed results'" (matching PCB LED positions to enclosure), moved back to Onshape; commenters: LLM tools "give correct outputs only some of the time"; "LLMs remain weak at spatial reasoning"; demo "sketches lacked constraints"; "subtle errors are hard to spot" — [HN 47977694](https://news.ycombinator.com/item?id=47977694)
- HN (OpenSCAD benchmark thread, ~June 2026): "Claude Code struggled with a snap-fit, vase-mode box: tolerances were wrong and it kept adding features that wouldn't print in vase mode"; "Models can't really 'see' their results. Downscaled images lose detail, and wireframe views are hard to read"; "In FreeCAD, models created distance constraints from arbitrary points instead of the references a human drafter would use"; Autodesk Fusion assistant "comically bad"; success: TPU grommet "nearly perfect on the first try" — [HN 48234090](https://hn.svelte.dev/item/48234090)
- build123d-mcp: "the AI otherwise writes blind — it cannot see the geometry it produces" (motivation) — [PyPI](https://pypi.org/project/build123d-mcp/0.3.56/); `edit_feature` refuses complex holes; HTTP unauthenticated shared session — [GitHub](https://github.com/pzfreo/build123d-mcp)
- agentcad: "Repeated shape captures fail with duplicate_capture"; "Mixing CAD APIs in one script is rejected"; Python 3.13+ unsupported — [GitHub](https://github.com/jdilla1277/agentcad)
- text-to-cad: Windows 11 Smart App Control "DLL load failed" for unsigned OCP module — [GitHub](https://github.com/earthtojake/text-to-cad)
- Multi-Agent-CAD: "does not sandbox the subprocess"; NumPy conflict on pure pip; Windows not in CI — [GitHub](https://github.com/Pan-Chera/Multi-Agent-CAD)
- KOMPAS: API7 unreliable for views/layers; slow with thousands of objects — [Habr](https://habr.com/en/articles/987312)
- Onshape MCP: "some operations are more reliable than others"; ChatGPT fails — [GitHub](https://github.com/altendky/onshape-mcp)
- Research: FEA-feedback agents "did not produce a single strict-passing artifact" first attempt — [arXiv](https://arxiv.org/abs/2605.17448)
- Security class of limitation: `execute_code` arbitrary Python in FreeCAD (neka-nat), unauthenticated TCP (Fusion), Web UI runs generated Python with user permissions (MAC) — sources above.

### Inferences
- GUI-bridge servers inherit the host's single-threaded GUI: any exception/dialog on the main thread deadlocks the agent; headless modes are partial (neka-nat `execute_code_headless`, spkane "embedded", OpenSCAD CLI) and are where the ecosystem is heading.
- "Kernel-valid but mechanically wrong" is the dominant geometry failure; it motivates VLM judges (CADSmith, MAC v2) and multi-view renders (21-view renderer in the FEA paper).

### Gaps
- No quantitative non-determinism study found; claims are anecdotal.
- No Reddit r/FreeCAD threads surfaced via search; the FreeCAD forum was not reachable through search results.

## KQ4. Which are usable without manually installing Python (installers, uvx, Docker, .mcpb)?

### Takeaway
`uvx`/`uv tool run` is the de-facto standard (freecad-mcp, build123d-mcp, zoo-mcp, fusion360-mcp-server, cad-cae-copilot); zero-Python options are Zoo's PyInstaller binaries, Onshape-mcp binaries/npx, npm OpenSCAD servers, Deno/Docker for mcp-calculix, Docker for CAD/CAE Copilot and jhacksman OpenSCAD; no `.mcpb` Desktop Extension found for any CAD server. GUI bridges still need the host CAD installed and an addon copied by hand.

### Cited Findings
- freecad-mcp: `uvx freecad-mcp` for server, but addon must be copied manually into version-specific Mod dir (#146 "No supported install/update path"); #161 (2026-10-02) community Windows installer script — [GitHub](https://github.com/neka-nat/freecad-mcp), [Issues](https://github.com/neka-nat/freecad-mcp/issues)
- build123d-mcp: `uv tool run --python 3.12 build123d-mcp@latest`; configs for Claude Code/Desktop, Cursor, VS Code, Continue, Cline, Codex CLI; GitHub Codespaces; HTTP mode; no Docker/.mcpb — [GitHub](https://github.com/pzfreo/build123d-mcp)
- agentcad: `pip install agentcad` only; no uvx/npx documented — [GitHub](https://github.com/jdilla1277/agentcad)
- text-to-cad: plugin/skills via Claude Code plugin or skills.sh; `cadgen` run through uv; needs Python 3.11+ and Node 20+; "first start downloads the CAD runtime" — [GitHub](https://github.com/earthtojake/text-to-cad)
- zoo-mcp: `uvx zoo-mcp`; "Prebuilt PyInstaller binaries… Linux, macOS, and Windows, so no Python toolchain is needed"; not code-signed — [GitHub](https://github.com/KittyCAD/zoo-mcp)
- fusion360-mcp-server: `uvx fusion360-mcp-server --mode socket`; `claude mcp add fusion360 -- uvx fusion360-mcp-server --mode socket`; add-in via script/symlink — [GitHub](https://github.com/faust-machines/fusion360-mcp-server)
- onshape-mcp: `npx --yes onshape-mcp` or prebuilt binary — [GitHub](https://github.com/altendky/onshape-mcp)
- OpenSCAD servers on npm (rahulgarg123, fboldo, dkpoulsen) and PyPI (RobertCoop, mcp-printable); jhacksman "headless Docker support" — [Glama](https://glama.ai/mcp/servers/integrations/openscad)
- cad-cae-copilot: Docker `ghcr.io/armpro24-blip/aieng-workbench:latest`, Codespaces, `uvx` from git tag — [GitHub](https://github.com/armpro24-blip/cad-cae-copilot)
- mcp-calculix: Docker image by digest or `deno run jsr:@casys/mcp-calculix/server --stdio` — [JSR](https://jsr.io/@casys/mcp-calculix)
- Multi-Agent-CAD: conda env + `pip install --no-deps aider-chat==0.82.3` — [GitHub](https://github.com/Pan-Chera/Multi-Agent-CAD)
- CAE-Agent-Hub: clone + venv + `pip install -e .` per server (Windows/PowerShell) — [GitHub](https://github.com/Cai-aa/cae-agent-hub)
- CAD-MCP: `python src/server.py` or `pip install -e .`; Windows + pywin32 — [GitHub](https://github.com/daobataotie/CAD-MCP)
- sandraschi/freecad-mcp: `just bootstrap` + `start.ps1`; Glama "cannot be deployed" — [Glama](https://glama.ai/mcp/servers/sandraschi/freecad-mcp)
- Search for `.mcpb`/Desktop Extension CAD servers returned only build123d-mcp's uv config: "This is a config-file setup, not a bundled Desktop Extension" — [search](https://pypi.org/project/build123d-mcp/0.3.80/)

### Inferences
- "No Python" is achievable today only for Zoo (hosted engine, paid API), Onshape (REST), OpenSCAD (npm wrappers around the OpenSCAD binary), and Dockerised CAE; every OCCT-based toolbox still needs a CPython 3.10–3.12 with OCP wheels, and uvx hides but does not remove that.

### Gaps
- No evidence of any CAD server in the Claude Desktop extensions directory or shipping `.mcpb`.

## KQ5. Which geometry kernels are viable in open source in 2026?

### Takeaway
OCCT (LGPL-2.1 with exception) is the only production-grade open B-rep kernel and shipped 8.0 in May 2026; truck (Rust, Apache-2.0) is alive but niche; Fornjot (archived 2026-06-19) and CADmium (archived 2025-09-05) are dead; Zoo's engine is hosted/proprietary behind an MIT client; OpenSCAD/CGAL/Manifold is mesh-only.

### Cited Findings
- OCCT: "LGPL 2.1 only with exception"; 8.0 dated 2026-05-07, 8.0.1 2026-07-30 (Wikipedia); "introduced BRepGraph, a graph-based B-Rep topology representation"; STEP export ~20% smaller; FOSDEM 2026 talk "OCCT3D 8.0: Evolving the Open Source Geometry Kernel" — [Wikipedia](https://en.wikipedia.org/wiki/Open_Cascade_Technology), [FOSDEM](https://fosdem.org/schedule/event/QQRAAF-occt3d-8-kernel-evolution), [OCC FAQ](https://dev.opencascade.org/resources/faq)
- OCP binding constraint: agentcad "Python 3.10–3.12, since the OpenCascade bindings do not support 3.13+" — [PyPI](https://pypi.org/project/agentcad/)
- Fornjot: "This project has been shut down. Its goals were never reached."; archived 2026-06-19; 0BSD; 2.6k stars; mainline "not been developed in over a year, in favor of a series of experiments"; downstream CommandCAD, fj-text, bevy_mod_fornjot — [GitHub](https://github.com/hannobraun/fornjot)
- truck: "Truck is a Rust CAD Kernel"; Apache-2.0; 1.6k stars, 2,872 commits; crates truck-geometry (NURBS), truck-topology, truck-shapeops ("boolean operations to Solid"), truck-stepio, truck-js; tutorials only for v0.6.x; no GitHub releases listed — [GitHub](https://github.com/ricosjp/truck)
- CADmium (on truck): "archived by the owner on Sep 5, 2025"; "Early prototype"; Elastic License 2.0; 1.6k stars — [GitHub](https://github.com/CADmium-Co/CADmium)
- Zoo: modeling-app MIT, "3D view is just a video stream from our hosted geometry engine" — [GitHub](https://github.com/KittyCAD/modeling-app); MCP use billed as API usage — [zoo.dev](https://zoo.dev/docs/developer-tools/mcp)
- OpenSCAD vs B-rep: HN commenters: CadQuery-type kernels "produce boundary representations needed for toolpaths and subtractive manufacturing. OpenSCAD outputs meshes" — [HN 48234090](https://hn.svelte.dev/item/48234090); mcp.directory: "OpenSCAD runs headless and is code-first. Blender has no feature history" — [mcp.directory](https://mcp.directory/blog/freecad-mcp-complete-guide-2026)
- Other Rust kernels seen only as listings: opencascade-rs (Rust bindings to OCCT), ecto/vcad "BRep CAD kernel in Rust (and WASM)" — [gittrend opencascade-rs](https://gittrend.io/repo/bschwind/opencascade-rs), [gittrend vcad](https://gittrend.io/repo/ecto/vcad)
- Russian C3D Toolkit (ASCON) is proprietary (Wikipedia listing surfaced) — [Wikipedia](https://en.wikipedia.org/wiki/C3D_Toolkit)

### Inferences
- Any 2026 open-source agent-CAD design should assume OCCT + Python 3.10–3.12 (OCP) as the kernel layer; Rust-only stacks have no maintained B-rep kernel with STEP round-trip except truck, whose maturity (no releases, v0.6 tutorials) is unproven for agent workloads.

### Gaps
- truck last release/commit date and STEP import/export completeness not verified.
- No benchmark comparing OCCT 8.0 BRepGraph vs 7.x for agent-generated models.
