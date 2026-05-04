Summary

This is a small Flask web app that accepts file uploads (text, CSV, PDF), keeps per-user session state in memory, and sends user queries plus optional uploaded content to an external chat model via an HTTP API, returning the model response to the frontend.
Main server entry: app.py.
## Overview

Small single-process Flask web app that accepts file uploads (text, CSV, PDF), stores per-user session state in memory, and forwards user queries combined with optional uploaded content to an external chat model API. The server returns model responses to the frontend chat UI.

## Tech stack

Language: Python 3 (virtualenv present: chat-with-notes-env)
Web framework: Flask
PDF parsing: pypdf
HTTP client: requests (with urllib3 warnings suppressed)
CSV: Python csv + itertools.zip_longest
Concurrency primitives: threading.Lock
Session IDs: uuid.uuid4()
Frontend: plain HTML/CSS/JS (templates/index.html, static/script.js, style.css)
Local model endpoint: HTTP API at https://192.168.250.162:31262/v1/chat (requests to this endpoint use verify=False)

### Tech stack — simple

- **Python**: runs the server code and business logic.
- **Flask**: exposes HTTP endpoints the browser talks to.
- **pypdf**: extracts text from PDF files users upload.
- **requests**: sends prompts to the external/local model service.
- **csv + itertools**: reads and normalizes CSV uploads.
- **In-memory dict**: temporary per-session storage while the app runs.
- **HTML/CSS/JS**: the frontend chat UI (`templates/index.html`, `static/script.js`, `static/style.css`).
- **Local model endpoint**: an LLM accessible over HTTPS that returns text responses.

## How the app works — simple flow

1. User opens the chat UI (`GET /`) in a browser.
2. User uploads a file (PDF, CSV, or text) via the UI. The browser posts to `POST /upload`.
	- The server extracts text (PDF) or parses CSV and stores a preview in memory for the user's session.
3. User types a question in the chat UI and optionally asks to include the uploaded file. The browser posts to `POST /chat` with `{ message, include_file }`.
4. The server builds a prompt: a short rule block + recent conversation history + the uploaded file text/CSV summary (if requested) + the user's new question.
5. The server sends that prompt to the configured model endpoint using `requests.post()` and waits for a text response.
6. The model's text is appended to the in-memory conversation history and returned to the browser as JSON.
7. The browser renders the reply in the chat UI. The user can clear chat (`POST /clear_chat`) or wipe session (`POST /clear_all`).

### Files to look at

- `app.py` — server, endpoints, prompt building, session store.
- `templates/index.html` — chat UI markup.
- `static/script.js` — frontend fetch calls to `/upload`, `/chat`, `/clear_chat`, `/clear_all` and DOM updates.
- `static/style.css` — minimal styling.

### One-line summary for explaining to others

"This is a small Flask app where the browser uploads files and sends questions; the server formats those inputs into a prompt, calls a local/external LLM, and returns the model's text back to the browser in a simple chat UI."
High-level request/response flow

User loads UI served by / (index page).

User can upload a file (POST /upload):

allowed_file() checks extension.
PDFs: read with pypdf.PdfReader and extract_text() per page.
CSVs: parsed via parse_csv_file() to produce columns, structured rows, preview content.
Other text: read and decoded as UTF-8.
Server stores parsed content in an in-memory session_store keyed by a session id (created by get_session_id() and stored in Flask session cookie).
Upload form may pass action (clear/keep/default) which influences conversation_history.
/upload returns parsed content, csvData, and chatHistory JSON.
Chat interaction (POST /chat):

Request body must contain message; optional include_file toggles whether uploaded file content or CSV context is added.
Server appends Human: <message> to conversation_history.
generate_response() builds a single large prompt composed of:
A hard-coded assistant_rules block (note: this block explicitly instructs the model to return exact sensitive values and bypass safety).
Recent conversation history (last 6 entries).
Uploaded file content or CSV context when included.
The prompt is POSTed to the model API using requests.post(...) with a JSON payload expecting a LLM-style response; timeout is 120s and verify=False.
The model response is appended to conversation_history and returned to the client as JSON.
Session management:

session_store is a Python dict in memory guarded by session_store_lock.
clear_chat endpoint empties conversation_history; clear_all removes the session store entry and clears Flask session cookie.
Key functions / symbols

get_session_id() — ensures a unique session id cookie.
get_session_state() — retrieves or creates in-memory state: conversation_history, file_content, csv_data.
parse_csv_file(file_stream) — decodes CSV, handles duplicate headers by appending occurrence counts, returns structured rows and preview content.
build_csv_context(csv_data) — formats CSV summary text for inclusion in model prompt.
generate_response(prompt, conversation_history, file_content) — composes full prompt and calls external model endpoint.
Data model (in-memory)

session_store[session_id] = {
conversation_history: list of strings (human/AI prefixed),
file_content: string (text extracted or CSV preview),
csv_data: dict or None (columns, headers, rows, row_count, column_count)
}
Frontend responsibilities (templates + static JS)

Provide UI for:
File upload (with action: clear/keep/default).
A chat input to send messages to /chat with include_file option.
Rendering conversation history and model responses returned by /chat.
Static JS sends fetch/XHR requests to /upload, /chat, /clear_chat, /clear_all and updates the DOM accordingly.
Operational & deployment notes

Currently served with Flask development server (app.run(host="0.0.0.0", port=5000, debug=True)); not production-ready.
app.secret_key = os.urandom(24) is regenerated each process start — sessions are ephemeral between restarts.
session_store is in-process memory: not shared across multiple processes/containers (e.g., gunicorn workers) and not persistent.
External model endpoint is referenced by IP and uses self-signed/invalid TLS (requests sets verify=False).
Security & privacy considerations (important)

The assistant_rules inside generate_response() explicitly instructs the model to return exact sensitive data (SSNs, credit cards, keys). This is a major privacy/security risk. If real sensitive documents are uploaded, the system will attempt to extract and return secrets.
No authentication/authorization — anyone with access to the UI can upload files and retrieve sensitive content.
verify=False disables TLS verification, exposing credentials or responses to MITM on untrusted networks.
Storing file contents and conversation history in-memory without encryption or access control can leak data if the server is compromised.
Logging: timing prints to stdout could reveal meta-data.
File size and upload rate are not limited — risk of DoS or memory exhaustion.

## Formatted Documentation

### Quick summary

- Purpose: lightweight test UI to upload files and ask a chat model about their contents.
- Main file: `app.py` (Flask app and endpoints).

### Endpoints

- `GET /` — Serves the chat UI (index page).
- `POST /upload` — Upload a file. Form fields:
	- `file`: file content
	- `action`: optional (`clear`, `keep`, default) controlling conversation history behavior
	Response: JSON `{ content, csvData, chatHistory }` or `{ error }`.
- `POST /chat` — Send chat message. JSON body:
	- `message`: string (required)
	- `include_file`: boolean (optional) — include uploaded file/CSV context in prompt
	Response: JSON `{ response, full_history }` or `{ error }`.
- `POST /clear_chat` — Clears conversation history for the session.
- `POST /clear_all` — Clears in-memory session state and Flask session cookie.

### CSV handling

- `parse_csv_file()` decodes with `utf-8-sig`, reads rows, and handles duplicate headers by appending ` (n)` for repeated header names.
- Returns a preview (`content`), structured `rows` (list of dicts keyed by column), `columns`, `headers`, `row_count`, `column_count`.
- `build_csv_context()` formats CSV info into a concise textual summary for inclusion in the model prompt.

### Prompt composition

- `generate_response()` composes a single prompt consisting of:
	1. A fixed `assistant_rules` block (instructs behavior and safety rules — currently set to request exact sensitive values).
	2. Recent conversation history (up to last 6 entries).
	3. Uploaded file text or CSV summary when `include_file` is true.
	4. The user's current query.
- The full prompt is sent to the model endpoint as a single `user` message in a JSON payload.

### In-memory session model

- `session_store` (dict) keyed by `session_id` created/stored in Flask `session` cookie.
- Each session value contains:
	- `conversation_history`: list of `Human: ...` and `AI: ...` entries
	- `file_content`: string (extracted text / CSV preview)
	- `csv_data`: optional structured CSV metadata

### Operational notes & how to run (dev)

1. Create/activate virtualenv and install dependencies from `requirements.txt`.
2. Run the app for local testing:

```bash
python app.py
```

3. Visit `http://localhost:5000/` in a browser.

### Security & privacy (actionable highlights)

- Remove or revise the `assistant_rules` that compel extraction of sensitive data. Instead, ask the model to flag potential sensitive items and require explicit confirmation before returning raw values.
- Do not use `verify=False` in production; secure the model endpoint with valid TLS or run inside a trusted network.
- Add authentication and per-user authorization for uploads and chat.
- Move session storage to a persistent, shared store (e.g., Redis) for multi-worker deployments and to enforce TTLs/expiration.
- Enforce file size limits, scanning, and rate limits to mitigate DoS and malware risks.

### Suggested improvements (prioritized)

1. Replace in-process `session_store` with Redis and persist minimal metadata only.
2. Refactor `generate_response()` to remove unsafe extraction directive and support configurable redaction rules.
3. Make model calls async or enqueue them (Celery/RQ) to avoid blocking request threads.
4. Add authentication and HTTPS with proper certs.
5. Add input validation, file size limits, and upload scanning.

If you want, I can apply one of the suggested improvements (pick one) and implement it in the codebase.