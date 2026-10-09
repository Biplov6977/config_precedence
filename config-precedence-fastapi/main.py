import asyncio
import hashlib
import os
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import yaml
from dotenv import load_dotenv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STUDENT_EMAIL = "23f1001103@ds.study.iitm.ac.in"


# ==========================================
# 1. QUESTION 7: 12-FACTOR CONFIG LOGIC (GET)
# ==========================================
def get_resolved_config(query_params):
    # 1. Base default / YAML config
    config = {}
    yaml_path = "config.development.yaml"
    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f) or {}

    # 2. .env overrides
    load_dotenv(override=True)
    for key, val in os.environ.items():
        if key in config:
            config[key] = val

    # 3. Query string overrides (e.g. ?set=workers=12)
    for qk, qv in query_params.items():
        if qk == "set":
            for pair in (qv if isinstance(qv, list) else [qv]):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    config[k] = int(v) if v.isdigit() else v
        elif qk in config:
            config[qk] = int(qv) if qv.isdigit() else qv

    return config


@app.get("/")
@app.get("/{path:path}")
async def handle_get(request: Request, path: str = ""):
    # Support MCP SSE streaming if the grader requests it
    accept_header = request.headers.get("accept", "")
    if "text/event-stream" in accept_header:

        async def sse_stream():
            yield "event: endpoint\ndata: /\n\n"
            while True:
                await asyncio.sleep(15)
                yield ": ping\n\n"

        return StreamingResponse(
            sse_stream(), media_type="text/event-stream"
        )

    # Standard GET -> returns Q7 12-factor configuration
    query_params = dict(request.query_params)
    return get_resolved_config(query_params)


# ==========================================
# 2. QUESTION 14: LIVE MCP SERVER (POST)
# ==========================================
@app.post("/")
@app.post("/{path:path}")
async def handle_post(request: Request, path: str = ""):
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    method = body.get("method")
    req_id = body.get("id")

    # Handshake: initialize
    if method == "initialize":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": body.get("params", {}).get(
                        "protocolVersion", "2024-11-05"
                    ),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "exam-mcp-server", "version": "1.0.0"},
                },
            }
        )

    # Handshake: notifications/initialized
    elif method == "notifications/initialized":
        if req_id is not None:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return Response(status_code=200)

    # Tool discovery: tools/list
    elif method == "tools/list":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "solve_challenge",
                            "description": "Solves challenge from header",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                            },
                        }
                    ]
                },
            }
        )

    # Execution: tools/call (runs 5 times)
    elif method == "tools/call":
        challenge = request.headers.get("x-exam-challenge", "")

        if not challenge and "params" in body:
            args = body["params"].get("arguments", {})
            if isinstance(args, dict):
                challenge = args.get("challenge", "")

        # SHA-256("${challenge}:${normalizedEmail}")[:16]
        hash_payload = f"{challenge}:{STUDENT_EMAIL.strip().lower()}"
        result_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()[
            :16
        ]

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result_hash}]},
            }
        )

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"},
        }
    )
