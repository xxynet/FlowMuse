# FlowMuse

A visual workflow editor for image generation. Connect image upload, LLM, image generation, and gallery nodes to create reusable workflows for realistic portraits, figurines, and sticker packs.

FlowMuse includes a Vue frontend and a working FastAPI backend. The default runner calls real model services; provider credentials and access to a compatible model are required for model nodes. The application UI is currently in Chinese.

## Features

- Drag-and-drop node editing with typed ports and connection validation.
- Built-in realistic portrait, figurine, and nine-image sticker pack presets.
- Text and vision requests through a Chat Completions-compatible API.
- Image generation and reference-image editing through an Images-compatible API, plus support for compatible Chat image-generation providers.
- Workflow saving, loading, and deletion, with SQLite-backed run history and events.
- A generated-results list that excludes reference uploads and gallery duplicates, with image downloads that keep the editor open.
- Asynchronous execution, incremental status updates, cancellation, time budgets, and concurrency limits.
- Multiple themes using CSS variables, with the selected theme saved locally.
- Provider API keys excluded from saved workflows, run snapshots, and application logs.

## Technology

**Frontend:** Vue 3, Vite, strict TypeScript, Pinia, Vue Flow, Tailwind CSS v4, and Lucide icons.

**Backend:** FastAPI, asynchronous SQLAlchemy 2, SQLite through aiosqlite, and HTTPX.

## Requirements

- Python 3.10 or later.
- Node.js 20.19+ within the 20.x release line, or Node.js 22.12 or later, with npm.
- A compatible model provider and API key for model execution.

The commands below use Windows PowerShell and start from the repository root unless noted otherwise.

## Quick start

Install the backend and build the frontend:

```powershell
python -m venv server/.venv
server/.venv/Scripts/python -m pip install -e "./server[dev]"
npm --prefix web install
npm --prefix web run build
```

Optionally create a backend configuration file without replacing an existing one:

```powershell
if (-not (Test-Path server/.env)) {
    Copy-Item server/.env.example server/.env
}
```

Set `FLOWMUSE_PROVIDER_BASE_URL` and `FLOWMUSE_PROVIDER_API_KEY` in `server/.env`, or enter the Base URL and API key directly in each model node. Use a versioned base address such as `https://api.example.com/v1`, not a full endpoint path.

Start the application:

```powershell
cd server
.venv/Scripts/python -m uvicorn flowmuse.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Open [FlowMuse](http://127.0.0.1:8000). The backend serves the compiled frontend from `web/dist`. [Interactive API documentation](http://127.0.0.1:8000/docs) is available on the same port. Press `Ctrl+C` in the server terminal to stop it.

For configuration, API details, and provider compatibility, see the [backend guide](server/README.md).

## Development

Keep the backend running on port 8000. In another terminal, from the repository root:

```powershell
npm --prefix web run dev
```

Open the [development frontend](http://127.0.0.1:5173). Vite proxies `/api` requests to the backend. Use this address for frontend hot reload; port 8000 continues to serve the last compiled build.

## Using a workflow

1. Load a preset or add nodes to the canvas.
2. Select a reference image and configure the model nodes with a supported model, Base URL, and API key.
3. Run the workflow and inspect node status, logs, and image results. Active or queued runs can be cancelled.
4. Name and save the workflow to load it again later.

The canvas is locked during execution. Loading a preset or clearing the canvas starts a new workflow. API keys remain in page memory and are not saved with the graph; after loading a saved workflow, enter them again or use the backend defaults.

For image-generation nodes, connected upstream text takes precedence over the local prompt. Chat image generation requires a provider that supports image output; a text-only Chat model is not sufficient.

## Project structure

```text
FlowMuse/
├── server/
│   ├── flowmuse/
│   │   ├── app.py              # REST API, lifecycle, and static frontend serving
│   │   ├── config.py           # Environment-based configuration
│   │   ├── database.py         # Async database access and persistent models
│   │   ├── schemas.py          # Graph, parameter, and image validation
│   │   ├── provider.py         # Model requests, response parsing, and safe errors
│   │   └── runner.py           # Topological execution and task management
│   ├── tests/                 # Backend regression tests
│   └── .env.example           # Configuration template without credentials
└── web/
    └── src/
        ├── main.ts            # Application entry and stylesheet ordering
        ├── styles/main.css    # Theme variables and Tailwind mappings
        ├── types/flow.ts      # Graph, node, port, and result types
        ├── registry/          # Node schemas for cards, ports, and forms
        ├── stores/            # Canvas state, run state, and logs
        ├── services/          # API client, backend runner, and demo runner
        ├── presets/           # Built-in workflow templates
        ├── composables/       # Theme selection and run orchestration
        └── components/        # Canvas, node cards, fields, and layout
```

## Extending FlowMuse

### Add a theme

Add a variable block to `web/src/styles/main.css`, copying all `--fm-*` variables from an existing theme and adjusting their values. Register its ID, label, and palette in `web/src/composables/useTheme.ts`.

Components use semantic classes such as `bg-primary`, `bg-surface`, `text-text`, and `border-border`. Theme selection is stored in `localStorage`.

### Add a node type

Update the frontend `NodeKind` type in `web/src/types/flow.ts` and add a `NodeTypeSchema` entry in `web/src/registry/nodeRegistry.ts`. The schema defines ports, fields, icon, and accent color for the shared card and form components.

Add the matching node type, ports, and parameter validation to `server/flowmuse/schemas.py`, and its execution behavior to `server/flowmuse/runner.py`. Register a corresponding node slot in `web/src/components/canvas/CanvasView.vue` and add relevant execution tests.

### Run integration

`web/src/services/apiRunner.ts` submits a graph snapshot to `POST /api/runs` and polls incremental events. `useRunner` maps those events to Pinia state using the existing `RunnerHooks` interface. `mockRunner.ts` remains a demo reference and is not used for default execution.

Development-only browser hooks expose `window.__flowStore` for canvas state and `window.__vueFlow` for the Vue Flow instance. They are not exposed by production builds.

## Verification

Run from the repository root using the local Python environment:

```powershell
server/.venv/Scripts/python -m pytest server/tests -q -c server/pyproject.toml
server/.venv/Scripts/python -m ruff check server
npm --prefix web run test
npm --prefix web run build
```

Backend tests use temporary SQLite databases and mocked HTTP responses. They do not require provider credentials or incur model charges. Real provider permissions, quotas, model support, and image quality must be verified separately with your own configuration.

## Operating scope

FlowMuse currently targets local, single-user use. Run one backend process with `--workers 1`. The queue lives in memory; saved workflows and run events persist in SQLite. Unfinished runs are marked as interrupted after shutdown or restart rather than automatically retried.

The default database is `server/data/flowmuse.db` when the backend starts from `server/`. It contains saved prompts, input images, and run results. Deleting a workflow keeps its run history; history can be removed through the run API.

Public or multi-user deployment requires authentication, data isolation, and outbound access controls. See the [backend configuration and limits](server/README.md#configuration-and-limits) and [connection troubleshooting](server/README.md#connection-troubleshooting) for details.
