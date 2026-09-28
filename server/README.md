# FlowMuse Backend

FastAPI, asynchronous SQLAlchemy 2, and SQLite provide workflow persistence and a bounded model execution queue. Python 3.10 or later is required. The backend currently targets local, single-user operation in one service process.

See the [project README](../README.md) for the frontend and a complete application quick start.

## Installation and startup

Run these commands in PowerShell from the repository root:

```powershell
python -m venv server/.venv
server/.venv/Scripts/python -m pip install -e "./server[dev]"
if (-not (Test-Path server/.env)) {
    Copy-Item server/.env.example server/.env
}
```

Configure `server/.env` if you want server-side provider defaults:

```dotenv
FLOWMUSE_PROVIDER_BASE_URL=https://api.example.com/v1
FLOWMUSE_PROVIDER_API_KEY=your-provider-key
```

Start the backend from `server/` so the relative `.env` and database paths resolve consistently:

```powershell
cd server
.venv/Scripts/python -m uvicorn flowmuse.app:app --host 127.0.0.1 --port 8000 --workers 1
```

- [API documentation](http://127.0.0.1:8000/docs)
- [Health check](http://127.0.0.1:8000/api/health)
- [Application](http://127.0.0.1:8000), available when `web/dist` exists at backend startup

To serve the compiled frontend, run `npm --prefix web install` and `npm --prefix web run build` from the repository root before starting the backend. For frontend development, run `npm --prefix web run dev` in a separate terminal and use [port 5173](http://127.0.0.1:5173); Vite proxies `/api` to port 8000.

Press `Ctrl+C` in the server terminal to stop the service.

## Credentials and stored data

Node-level provider settings take precedence over backend defaults. The default API key is used only when the selected Base URL matches the configured default address after trailing-slash normalization. A different endpoint requires an explicit node API key.

API keys are excluded from saved graphs, run snapshots, API responses, browser persistence, and application logs. Loading a saved workflow requires entering node keys again or using the backend default key. Keep real credentials out of Git; `.env` files are ignored.

Saved workflows contain prompts, node positions, connections, and input images. Run events store text and image results. The default database is `server/data/flowmuse.db` when started as documented. Deleting a workflow preserves its run history; use the run deletion endpoint to remove finished runs and their events.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Check the service and database. |
| GET / POST | `/api/workflows` | List workflows or create a workflow. |
| GET / PUT / DELETE | `/api/workflows/{id}` | Read, fully replace, or delete a workflow. |
| POST | `/api/runs` | Validate and enqueue a graph; return HTTP 202 with a run ID. |
| GET | `/api/runs` | List run history, optionally filtered by `workflowId`. |
| GET | `/api/runs/{id}?after=0` | Read run status and incremental events. |
| POST | `/api/runs/{id}/cancel` | Cancel an active or queued run; finished runs retain their status. |
| DELETE | `/api/runs/{id}` | Delete a finished run and its events; active runs return HTTP 409. |

List endpoints accept `limit` (default 50, maximum 100) and `offset` (default 0).

Workflow writes use `{name, nodes, edges}`. Run creation uses `{nodes, edges, workflowId?}`. Execution always uses the submitted graph snapshot; `workflowId` links the run to an existing workflow but does not load that workflow's graph automatically.

Node and edge fields follow the frontend [graph types](../web/src/types/flow.ts) and [node registry](../web/src/registry/nodeRegistry.ts). A minimal text run using the backend provider credentials looks like this:

```json
{
  "nodes": [{
    "id": "llm-1",
    "type": "llm",
    "position": {"x": 0, "y": 0},
    "data": {
      "label": "Prompt generation",
      "params": {
        "model": "gpt-4o-mini",
        "prompt": "Describe a cat.",
        "temperature": 0.7
      }
    }
  }],
  "edges": []
}
```

Use a model supported by your provider. Invalid graphs, parameters, or missing required inputs are rejected before execution. Validation covers duplicate IDs, missing nodes, incompatible ports, multiple connections to one input, and cycles.

## Run lifecycle and events

Runs begin as `queued`, move to `running`, and finish as `success`, `error`, `cancelled`, or `interrupted`. Queued runs can also be cancelled or interrupted. Execution follows topological order and stops on the first failed node.

On shutdown or restart, unfinished runs become `interrupted`. Live credentials and in-memory tasks are not recovered, and model requests are not automatically retried.

Event types are `run_started`, `node_started`, `node_success`, `node_error`, `run_success`, `run_error`, `run_cancelled`, and `run_interrupted`. Each event includes a monotonically increasing per-run `sequence` and a timestamp in `time`. Node events include `nodeId`; successful node events include `result: {text?, images?}`.

A polling response contains run metadata, `events`, `nextCursor`, and `hasMore`. Request the next page with `after=nextCursor`. Each page contains at most 100 events. Drain all `hasMore` pages before treating a terminal run status as fully consumed.

The frontend locks the canvas during execution and maps these events to node status and results. Cancellation stops local waiting and subsequent nodes; a request already accepted by the provider may still execute or incur charges.

## Provider protocols

Use a versioned Base URL such as `https://api.example.com/v1`. The backend appends endpoint paths; do not put `/chat/completions` or `/images/generations` in the Base URL.

### Text and vision

LLM nodes call `POST /chat/completions` with Bearer authentication. The JSON body contains `model`, `messages`, `temperature`, `max_tokens`, and `stream: false`.

An optional system message precedes a user message containing text and, when connected, an `image_url` content block. Reference images are sent as data URLs. The LLM prompt supports `{{text}}` substitution from its upstream text input.

The response parser reads `choices[0].message`. String content is returned as text; text blocks in content arrays are joined with newlines. Empty text output fails the node.

### Images API

Image-generation nodes using the Images protocol call:

- `POST /images/generations` with JSON when no reference image is connected.
- `POST /images/edits` with a multipart image file when a reference image is connected.

Both send the model, prompt, requested image count, and size. Responses are parsed from `data` entries containing `b64_json` or `url`. The returned image count must match the requested count.

### Chat image generation

Nodes configured for Chat image generation call `POST /chat/completions` using the same message format as text nodes. This requires a provider-specific image-output capability; it is not supported by every Chat model.

The parser accepts these image representations in `choices[0].message`:

- Markdown image links in string `content`.
- A standalone `data:image/...;base64,...` string in `content`.
- `image_url` or `image` blocks in a content array, using an `image_url` object with a `url` field, an `image_url` string, or a `url` field.
- Objects in `message.images` using the same URL fields.

For a requested count of N, the backend makes N sequential requests and takes the first parsed image from each response. A response without an image fails the node. The node result contains the request prompt and collected images; accompanying model text is not used as the result text.

Chat image requests do not send the node's size setting. The provider determines dimensions. Bare HTTP URL text and `b64_json` fields are not parsed as Chat image output. Streaming SSE responses are not supported: HTTP bytes are read incrementally to enforce a size limit, then parsed as one complete JSON response.

### Prompt and image handling

For image-generation nodes, connected upstream text takes precedence over the local prompt. Without usable upstream text, the local prompt is used.

Input images are read by the frontend as data URLs; there is no separate upload service. PNG, JPEG, WebP, and GIF inputs are supported up to 10 MiB per image. SVG input is not supported. Returned inline images are subject to the same validation.

Remote image URLs are passed to the browser without downloading them on the backend. Temporary provider URLs may expire. Base64 output is retained in run events.

Protocol references: [image generation](https://developers.openai.com/api/docs/guides/image-generation) and [vision inputs](https://developers.openai.com/api/docs/guides/images-vision). The implementation uses HTTPX rather than a provider-specific SDK.

## Configuration and limits

Settings use the `FLOWMUSE_` prefix and can be supplied through environment variables or `.env` in the backend working directory. See [.env.example](.env.example) and [config.py](flowmuse/config.py).

| Setting | Default | Purpose |
| --- | --- | --- |
| `FLOWMUSE_DATABASE_URL` | `sqlite+aiosqlite:///./data/flowmuse.db` | Database connection. |
| `FLOWMUSE_PROVIDER_BASE_URL` | `https://api.openai.com/v1` | Default provider address. |
| `FLOWMUSE_PROVIDER_API_KEY` | Empty | Default provider secret. |
| `FLOWMUSE_REQUEST_TIMEOUT` | `120` | Total time budget per provider request, in seconds. |
| `FLOWMUSE_RUN_TIMEOUT` | `900` | Execution budget after acquiring a worker slot, in seconds. |
| `FLOWMUSE_MAX_OUTPUT_TOKENS` | `2048` | Chat output token budget. |
| `FLOWMUSE_MAX_CONCURRENT_RUNS` | `2` | Simultaneously executing workflows. |
| `FLOWMUSE_MAX_PENDING_RUNS` | `16` | Combined active and queued run limit; excess submissions return HTTP 429. |
| `FLOWMUSE_MAX_REQUEST_BYTES` | `33554432` | Maximum inbound request body: 32 MiB. |
| `FLOWMUSE_MAX_RESPONSE_BYTES` | `67108864` | Maximum provider response: 64 MiB. |

Each graph permits up to 100 nodes and 300 edges. Image generation counts range from 1 to 9. HTTP and database operations use asynchronous clients.

Host and Origin restrictions allow the local frontend and backend by default. `FLOWMUSE_ALLOWED_HOSTS` and `FLOWMUSE_ALLOWED_ORIGINS` accept JSON arrays to configure these lists. This is an unauthenticated local service with user-configurable outbound model addresses; public or multi-user deployment requires authentication, data isolation, and outbound access controls.

Use exactly one backend process (`--workers 1`) and do not share the database between live instances. Multiple instances require an external queue and worker coordination. Tables are created on first startup; future schema changes require a migration strategy. The current queue is not a durable distributed queue.

## Connection troubleshooting

Failures retain a safe error category without exposing raw exception messages, headers, credentials, or provider response bodies:

| Category | Meaning |
| --- | --- |
| `ConnectError` | A connection to the provider or proxy could not be established. |
| `ProxyError` | Proxy connection setup failed. |
| `RemoteProtocolError` | Invalid upstream HTTP behavior or an early disconnect. |
| `ReadError` / `WriteError` | The connection failed while receiving or sending data. |
| `DecodingError` | The response compression encoding was invalid. |
| `TLS_CERTIFICATE` / `TLS_HANDSHAKE` | Certificate verification or TLS negotiation failed. |
| `DNS_ERROR` | Provider or proxy hostname resolution failed. |
| `ConnectTimeout` / `ReadTimeout` / `WriteTimeout` / `PoolTimeout` | The corresponding connection operation timed out. |
| `RequestDeadline` | The total provider request budget was exceeded. |

TLS and DNS categories are reported when the underlying cause can be identified. HTTP errors retain their status: 401 indicates authentication failure, 403 denied access, 404 a missing endpoint or resource, 429 rate or quota limits, and 5xx a provider or gateway failure. A 5xx response alone does not establish a credential or quota problem.

The backend inherits `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` from its startup environment. A working provider website in the browser does not establish that the backend uses a working proxy route or that image generation is available. An unauthenticated request returning 401 only confirms that the tested endpoint responded at that time.

Model requests are not automatically retried after connection failures, to avoid duplicate charges. Keep TLS verification enabled while investigating certificate or proxy problems.

References: [HTTPX exceptions](https://www.python-httpx.org/exceptions/) and [HTTPX environment variables](https://www.python-httpx.org/environment_variables/).

## Verification

From the repository root, using the project's local Python environment:

```powershell
server/.venv/Scripts/python -m pytest server/tests -q -c server/pyproject.toml
server/.venv/Scripts/python -m ruff check server
npm --prefix web run build
```

Tests use temporary SQLite databases and HTTPX MockTransport. Coverage includes workflow CRUD and persistence, reference-image execution, graph validation, provider response formats, incremental events, credential isolation, transport error classification, cancellation, queue limits, timeouts, and interruption recovery.

These tests do not require real API keys or incur model charges. Provider-specific model permissions, quotas, and protocol differences require separate validation with your own credentials.
