import asyncio
import hashlib
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STUDENT_EMAIL = "23f1001103@ds.study.iitm.ac.in"


@app.get("/")
@app.get("/{path:path}")
async def handle_get(request: Request, path: str = ""):
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
    return {"status": "ok", "message": "Live MCP Server Running"}


@app.post("/")
@app.post("/{path:path}")
async def handle_post(request: Request, path: str = ""):
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    method = body.get("method")
    req_id = body.get("id")

    # 1. MCP Handshake: initialize
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

    # 2. MCP Handshake: notifications/initialized
    elif method == "notifications/initialized":
        if req_id is not None:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return Response(status_code=200)

    # 3. Tool Discovery: tools/list
    elif method == "tools/list":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "solve_challenge",
                            "description": "Solves challenge by reading X-Exam-Challenge header",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                            },
                        }
                    ]
                },
            }
        )

    # 4. Tool Execution: tools/call (repeated 5 times)
    elif method == "tools/call":
        # Read challenge strictly from the incoming HTTP request headers
        challenge = request.headers.get("x-exam-challenge", "")

        # Fallback to arguments if header was forwarded internally
        if not challenge and "params" in body:
            args = body["params"].get("arguments", {})
            if isinstance(args, dict):
                challenge = args.get("challenge", "")

        # Compute SHA-256("${challenge}:${normalizedEmail}")[:16]
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

    # Fallback for other standard RPC calls
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"},
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
