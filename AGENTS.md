# AGENTS.md

Notes for running this repo in the Base44 sandbox. Only the non-obvious bits.

## What runs here

`apax.py` is one self-contained Python 3 program with **zero dependencies** (stdlib only:
`http.server`, `urllib`, `json`). Nothing to install, no lockfile, no pip step. Three modes:

| command | what it is |
|---|---|
| `python3 apax.py` | interactive CLI; needs a TTY, so it is not used in the sandbox |
| `python3 apax.py --ui [port]` | the web UI (chat, capabilities, brain stats); default port 8080 |
| `python3 apax.py --door [repo]` | git "door" poller daemon |

`docs/` is a separate static site (`index.html`, `demo.html`, the in-browser Pyodide demo).
It is *not* what the preview serves.

## Sandbox run

```bash
docker compose -f docker-compose.base44.yml up -d
```

One service, `apax`, from `python:3.12-slim` with the repo bind-mounted at `/app`
(no build, no installed image, so source edits are picked up). Container port **8080** is
published on host **3000** because the preview proxies port 3000.

Verify: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/` → `200`,
and the chat endpoint answers:
`curl -s -X POST http://localhost:3000/api/say -H 'Content-Type: application/json' -d '{"text":"a dog is an animal"}'`.

## Gotchas

- **No auto-reload.** `http.server` has none. After editing `apax.py` run
  `docker compose -f docker-compose.base44.yml restart apax` and reload the preview.
- **The brain is runtime data**, `apax_brain.json` next to the script (created on first
  write, gitignored, regenerated blank). Delete it to reset APAX to "born blank".
- **`apax-webkey.txt` is intentionally absent** → the app runs in its documented public
  mode: chatting works, but capability grants from the UI return `403` ("caps locked").
  Create the file with 24 hex chars to allow grants from the web UI.
- **No host/origin allowlists.** The stdlib server does not check `Host` or `Origin`, so
  the preview proxy host needs no configuration.
- **No credentials are required to boot.** Local brain + outbound page reading use no keys.
- Optional AI "veins" (`ask gemini|grok|chatgpt|mistral|deepseek|together <prompt>`) read
  keys from the environment: `APAX_GEMINI_KEY`, `APAX_XAI_KEY`, `APAX_OPENAI_KEY`,
  `APAX_MISTRAL_KEY`, `APAX_DEEPSEEK_KEY`, `APAX_TOGETHER_KEY`. None are set, so those
  replies say "set the key first". Add them via Base44 secrets (they then arrive in
  `/run/base44/app.env`, which a service must list as its last `env_file:`).
- **GPIO does not exist** in a container; `/grant gpio` succeeds but pin writes fail
  harmlessly (`gpio pin 17 on` → "no gpio here" style reply).
