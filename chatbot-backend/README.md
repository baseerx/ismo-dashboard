# ISMO HR Assistant (chatbot-backend)

A FastAPI service behind the chat widget in the dashboard. It does two separate
jobs:

1. **Answers policy questions** from documents an administrator has trained into
   it — retrieval-augmented generation over the HR Policies Manual, with the
   page it quoted named in the answer.
2. **Answers questions about the asker's own record** — leave balance, leave
   history, official work and attendance for any period — and turns any of those
   into an Excel or PDF report.

Both models run locally through [Ollama](https://ollama.com); no employee data
leaves the network.

---

## Running it

```bat
run_server.bat
```

First run creates `venv\`, installs `requirements.txt`, warns if Ollama is not
answering, and starts uvicorn on `0.0.0.0:8000`. Override with `set PORT=9010`
before calling it.

Prerequisites on the host:

| Requirement | Why |
|---|---|
| Python 3.12 | the service |
| ODBC Driver 17 for SQL Server | reading the dashboard's database |
| Ollama, with `mistral` and `nomic-embed-text` pulled | answering and embedding |

```bat
ollama pull mistral
ollama pull nomic-embed-text
```

Then copy `.env.example` to `.env` and set **`DJANGO_SECRET_KEY` to the exact
value of `SECRET_KEY` in `backend/hris/settings.py`**. Every request is
authenticated with the token the dashboard's own login issues; if the keys
differ, everything returns 401.

## Training documents

The vector store (`chroma_db/`) is derived data and is deliberately **not** in
version control — it is large, binary, and changes on every upload. The seeded
HR manual in `uploads/` is committed, so a new deployment can build its own
index from it. Anything trained later through the widget stays on that host
(`uploads/` is git-ignored), which is why each environment is trained
separately:

```bat
train_documents.bat            REM index what is in uploads\
train_documents.bat --reset    REM drop the collection and rebuild
train_documents.bat status     REM what is indexed right now
```

**Restart the service after training from the command line.** Chroma shares its
metadata between processes but not its search index, so a service that was
already running keeps answering from the documents it loaded at startup and
silently omits anything the CLI added. The CLI prints this reminder, the service
logs a warning when it notices, and `GET /` reports `"stale": true`. Training
through the chat widget is unaffected — that happens inside the service itself.

Day to day, an administrator trains documents from the paperclip button in the
chat widget; PDF, DOCX, TXT and MD are accepted. Duplicate uploads are rejected
by content hash, so re-uploading the same manual under a new name cannot double
every passage in the search results.

`--reset` is required after changing `EMBEDDING_MODEL`: Chroma fixes a
collection's vector dimension on first insert, and mixing models silently
degrades retrieval.

---

## How a question is answered

```
question + Authorization: Bearer <dashboard JWT>
        │
        ├─ app/auth/identity.py      verify signature -> ERP id, name, is_admin
        ├─ app/chat/intent.py        what is being asked, about whom
        ├─ app/chat/dates.py         "last month" -> two dates
        │
        ├── data question ──► app/hr/queries.py ──► app/chat/answers.py
        │                     (SQL, dashboard rules)  (templated wording)
        │
        ├── policy question ─► app/rag/retriever.py ─► mistral
        │                     (cosine search, filtered) (writes the prose)
        │
        └── neither ────────► one tool-calling turn, tools scoped to the asker
```

**Why the classification is in code.** A local 7B model is a good writer and an
unreliable clerk: asked "how many casual leaves do I have left", it will
sometimes answer from its own idea of HR practice, or call the right tool with
the wrong dates. Every HR answer here is a factual claim about someone's
employment, so the intent, the dates and the figures are decided by
`intent.py` / `dates.py` / `queries.py`, and the wording is templated in
`answers.py`. The model writes policy answers, where prose is the point, and
gets one tool-calling turn as a fallback for phrasings the router does not
recognise. A miss therefore degrades to "slower and vaguer", never to "wrong
number, stated confidently".

**Why the numbers match the dashboard.** `app/hr/queries.py` reproduces the
rules the Django views apply: the 1 July – 30 June financial year, entitlements
from `leave_type_counts`, pending leave counted as spent, the 10-day Casual
Leave reduction once Rest & Recreational leave is taken, and the day-status
precedence `present > leave > official work > holiday > weekend > absent`.

## Read-only by construction

The assistant answers questions about HR records and **never changes them**. No
code path writes to `leaves`, `attendance`, `employees`, `official_work_leaves`,
`public_holidays` or `leave_type_counts`, and that is enforced rather than
assumed: [`app/database/guard.py`](app/database/guard.py) inspects every
statement before it reaches SQL Server and refuses any INSERT, UPDATE, DELETE,
MERGE, TRUNCATE, DDL, EXEC or GRANT that names a table other than the
assistant's own three. Unrecognised write statements are refused too — it fails
closed.

The three tables it does write are its own bookkeeping:

| Table | Written when | Turn it off with |
|---|---|---|
| `conversations`, `messages` | a question is asked and answered | `PERSIST_CHAT_HISTORY=false` |
| `documents` | an administrator trains or removes a document | — (that is the training feature) |

`PERSIST_CHAT_HISTORY=false` makes the service write nothing at all while
answering. Answers are identical; what is lost is follow-up context ("and for
medical leave?" no longer knows what came before) and the "past chats" panel.

**Recommended: make it read-only at the server too.** The in-process guard stops
mistakes, not someone who can already run code here. The connection currently
ships configured for `sa`, which can do anything. Create a least-privilege login
instead and set `DB_USER` / `DB_PASSWORD` to it:

```sql
CREATE LOGIN ismo_assistant WITH PASSWORD = 'a strong password here';
USE Attendance_System;
CREATE USER ismo_assistant FOR LOGIN ismo_assistant;

-- read everything the assistant answers from
ALTER ROLE db_datareader ADD MEMBER ismo_assistant;

-- write only its own three tables
GRANT INSERT, UPDATE, DELETE ON dbo.conversations TO ismo_assistant;
GRANT INSERT, UPDATE, DELETE ON dbo.messages      TO ismo_assistant;
GRANT INSERT, UPDATE, DELETE ON dbo.documents     TO ismo_assistant;

-- and nothing else
DENY INSERT, UPDATE, DELETE ON dbo.leaves               TO ismo_assistant;
DENY INSERT, UPDATE, DELETE ON dbo.attendance           TO ismo_assistant;
DENY INSERT, UPDATE, DELETE ON dbo.employees            TO ismo_assistant;
DENY INSERT, UPDATE, DELETE ON dbo.official_work_leaves TO ismo_assistant;
DENY INSERT, UPDATE, DELETE ON dbo.leave_type_counts    TO ismo_assistant;
DENY INSERT, UPDATE, DELETE ON dbo.public_holidays      TO ismo_assistant;
```

Create the three tables once (start the service as a user that may create them,
or run the DDL by hand) before switching the login over, since a read-only user
cannot create them itself.

## Privacy

- The ERP id used for every lookup comes from the **verified** token, never from
  the request body and never from model output. Editing the cached profile in
  devtools changes nothing, because the payload no longer matches the signature.
- An employee asking about a colleague is **refused**, not quietly shown their
  own record. Only `is_superuser` accounts can name another employee — the same
  test the dashboard UI uses to decide what to show.
- The HR tool schemas expose dates and leave types and **no employee id**, so
  prompt injection inside a trained document has no parameter to abuse.
- Conversations carry `owner_erp_id`, and reading somebody else's thread returns
  404 rather than 403 — a "forbidden" would confirm the thread exists.
- Reports re-authorise the ERP id server-side before a file is built, and are
  streamed from memory rather than written to disk.

---

## API

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/` | anyone | health check, indexed chunk count |
| GET | `/me` | signed in | what the service thinks your identity is |
| POST | `/chat/` | signed in | ask a question |
| GET | `/chat/conversations` | signed in | your own threads |
| GET | `/chat/conversations/{id}/messages` | owner | one thread |
| DELETE | `/chat/conversations/{id}` | owner | delete a thread |
| POST | `/reports/generate` | signed in | Excel or PDF, own records |
| GET | `/documents/` | signed in | what can be searched |
| GET | `/documents/{id}/status` | signed in | training progress |
| POST | `/documents/upload` | **admin** | train a document |
| DELETE | `/documents/{id}` | **admin** | untrain a document |

`POST /chat/` returns the answer plus, where they apply: `data` (a table the
widget renders), `report` (an offer the widget turns into download buttons),
`sources` (documents and pages cited) and `actions` (a page to open).

Interactive docs while the service is running: <http://localhost:8000/docs>

## Tuning

| Setting | Default | Effect |
|---|---|---|
| `RETRIEVAL_MAX_DISTANCE` | `0.45` | cosine ceiling for relevance. Real matches on the HR manual measure 0.20–0.37; unrelated questions 0.45+. Raising it invites confident answers from passages that merely look similar |
| `RETRIEVAL_TOP_K` | `6` | passages per question |
| `MODEL_TEMPERATURE` | `0.1` | this assistant quotes policy; it should not improvise |
| `PERSIST_CHAT_HISTORY` | `true` | `false` stops the service writing anything at all while answering, at the cost of follow-up context and the past-chats panel |
| `REPORT_MAX_RANGE_DAYS` | `800` | longest period one report may cover |

## Troubleshooting

| Symptom | Cause |
|---|---|
| every request 401 | `DJANGO_SECRET_KEY` does not match `backend/hris/settings.py`, or the login token has expired (they last an hour) |
| policy answers say nothing is indexed | empty vector store — run `train_documents.bat` |
| startup warns about distance space | store predates the switch to cosine — run `train_documents.bat --reset` |
| "Invalid column name 'owner_erp_id'" | an older copy of the chatbot tables; the service adds the column itself at startup, so restart once |
| widget cannot reach the service | origin missing from `CORS_ORIGINS`, or `VITE_CHATBOT_API_URL` in the frontend points elsewhere |
| slow first answer | Ollama is loading the model into memory; subsequent answers are quick |
