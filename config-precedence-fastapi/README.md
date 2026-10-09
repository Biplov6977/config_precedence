# Effective Config API

A FastAPI service for the 12-factor configuration precedence exercise.

## Local run

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Git Bash/macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/effective-config` or test overrides with:

`http://127.0.0.1:8000/effective-config?set-port=9000&set-debug=true&set-workers=2`

The expected precedence is defaults -> `config.development.yaml` -> `.env` -> OS/container environment -> query overrides. `NUM_WORKERS` in `.env` maps to `workers`; OS `APP_WORKERS` also maps to `workers`. `api_key` is always returned as `****`.

## Deploy to Render

1. Create a GitHub repository and upload the contents of this folder.
2. In Render, create a new **Blueprint** from that repository (it reads `render.yaml`), or create a Python web service with build command `pip install -r requirements.txt` and start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Wait for the service to deploy. Open `https://YOUR-SERVICE.onrender.com/effective-config`.
4. Paste that full URL into the assignment. The grader can add its own `set-...` query parameters.

For local runs the assigned OS environment values are used as fallbacks: `APP_PORT=8321`, `APP_WORKERS=7`, `APP_DEBUG=false`, `APP_LOG_LEVEL=info`. Real OS/container variables take precedence over those fallbacks.
