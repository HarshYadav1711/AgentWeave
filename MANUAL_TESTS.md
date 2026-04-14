# Manual demo script (copy-paste)

**Prerequisite:** server running from the repo root:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Use another terminal for the commands below. Base URL: `http://127.0.0.1:8000`

**Tip:** Examples use `curl` with single-quoted JSON (works in Git Bash, WSL, macOS, Linux). In **PowerShell**, call `curl.exe` explicitly (not the `curl` alias) or use the JSON file trick: `curl.exe ... --data-binary "@body.json"`.

---

### 1) Add an agent successfully

```bash
curl -s -X POST "http://127.0.0.1:8000/agents" -H "Content-Type: application/json" \
  -d '{"name":"DemoAgent","description":"Manual test agent","endpoint":"http://127.0.0.1:9000"}'
```

Expect: HTTP **201** and JSON with `"ok": true`, `"name": "DemoAgent"`.

---

### 2) Search by keyword in **name**

```bash
curl -s "http://127.0.0.1:8000/search?q=DemoAgent"
```

Expect: HTTP **200** and a JSON array containing the agent.

---

### 3) Search by keyword in **description**

```bash
curl -s "http://127.0.0.1:8000/search?q=Manual"
```

Expect: HTTP **200** and a JSON array containing the agent.

---

### 4) Add a second agent (for usage)

```bash
curl -s -X POST "http://127.0.0.1:8000/agents" -H "Content-Type: application/json" \
  -d '{"name":"DemoPeer","description":"Peer","endpoint":"http://127.0.0.1:9001"}'
```

---

### 5) Log usage successfully

```bash
curl -s -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"DemoAgent","target":"DemoPeer","units":4,"request_id":"manual-req-001"}'
```

Expect: HTTP **200**, `"status": "recorded"`, `"units": 4`.

---

### 6) Duplicate `request_id` is **ignored** (no double-count)

Run the **same** command again:

```bash
curl -s -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"DemoAgent","target":"DemoPeer","units":4,"request_id":"manual-req-001"}'
```

Expect: HTTP **200**, `"status": "ignored"`, `"operation": "ignored_duplicate_request"`.

Check summary still shows **4** total to `DemoPeer`:

```bash
curl -s "http://127.0.0.1:8000/usage-summary"
```

---

### 7) Unknown **caller** error

```bash
curl -s -i -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"NoSuchAgent","target":"DemoPeer","units":1,"request_id":"manual-req-002"}'
```

Expect: HTTP **404**, JSON includes `"error": "caller_not_found"`, `"ok": false`.

---

### 8) Unknown **target** error

```bash
curl -s -i -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"DemoAgent","target":"NoSuchAgent","units":1,"request_id":"manual-req-003"}'
```

Expect: HTTP **404**, `"error": "target_not_found"`.

---

### 9) Missing fields → validation error

```bash
curl -s -i -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"DemoAgent"}'
```

Expect: HTTP **422**, `"error": "validation_error"`, `"ok": false`.

---

### 10) Invalid **units** → validation error

```bash
curl -s -i -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"DemoAgent","target":"DemoPeer","units":0,"request_id":"manual-req-004"}'
```

Expect: HTTP **422**, `"ok": false`.

---

### Reset DB (optional)

Stop the server, delete `agentweave.db` in the project root, start the server again.
