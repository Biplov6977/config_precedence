import asyncio
import hashlib
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import duckdb
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import requests
import yaml
import zoneinfo

load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STUDENT_EMAIL = "23f1001103@ds.study.iitm.ac.in"
AIPIPE_TOKEN = os.getenv("AIPIPE_TOKEN", "YOUR_AI_PIPE_TOKEN")

# Data URLs provided for Question 15
EXPORT_URL = "https://exam.sanand.workers.dev/questionData?email=23f1001103%40ds.study.iitm.ac.in&quizSign=y926rmwLDXU2ubFkAqRmzno5h7qat4%2FUE%2BB%2Bnqo7PKIa2ninz1AF9G4Lf99WOBOsjrAHSHYFzA1zCi2m6uFXUdhs5GSVu1nvqNJgBZX4J%2FLkX6fgOBxtbHjihogOYbwt4F%2F%2BqA24sq1HxeI%2Fc566EKHY5eSAWxd82Sq8%2BbwTF49IU9LSdxP%2FgDGFb3Al7LdKPNsZtNeDLcBxxKZSMZrBwp9NGEdxljQv0BdiuMu4iJEBBN6eNCyT7m2KljXCVeCn%2B8ltMkKKEwisMdZ875XbV%2BvpzaYrQOCDVmtEQP6U%2Bm4uXmN4IWx9%2Bb4NpEVcXWrr42LsJYFaYYspqIPKvM4esw%3D%3D&questionId=q-ledger-agent-server&path=%2Fexport"
RATES_URL = "https://exam.sanand.workers.dev/questionData?email=23f1001103%40ds.study.iitm.ac.in&quizSign=y926rmwLDXU2ubFkAqRmzno5h7qat4%2FUE%2BB%2Bnqo7PKIa2ninz1AF9G4Lf99WOBOsjrAHSHYFzA1zCi2m6uFXUdhs5GSVu1nvqNJgBZX4J%2FLkX6fgOBxtbHjihogOYbwt4F%2F%2BqA24sq1HxeI%2Fc566EKHY5eSAWxd82Sq8%2BbwTF49IU9LSdxP%2FgDGFb3Al7LdKPNsZtNeDLcBxxKZSMZrBwp9NGEdxljQv0BdiuMu4iJEBBN6eNCyT7m2KljXCVeCn%2B8ltMkKKEwisMdZ875XbV%2BvpzaYrQOCDVmtEQP6U%2Bm4uXmN4IWx9%2Bb4NpEVcXWrr42LsJYFaYYspqIPKvM4esw%3D%3D&questionId=q-ledger-agent-server&path=%2Frates"

RATES = {"USD": 1.0, "EUR": 1.05, "INR": 0.01212}
KOLKATA_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")
db_conn = duckdb.connect(database=":memory:")


def init_ledger_database():
    try:
        # 1. Fetch exchange rates
        r_rates = requests.get(RATES_URL, timeout=10)
        if r_rates.status_code == 200:
            data = r_rates.json()
            if "usd_per_unit" in data:
                RATES.update(data["usd_per_unit"])
    except Exception as e:
        print(f"Error fetching rates: {e}")

    try:
        # 2. Fetch all raw ledger entries
        r_export = requests.get(EXPORT_URL, timeout=15)
        raw_text = r_export.text
    except Exception as e:
        print(f"Error fetching export: {e}")
        raw_text = ""

    orders_map = {}
    for line in raw_text.strip().split("\n"):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            oid = item["id"]
            # Keep latest entry by updated_at
            if (
                oid not in orders_map
                or item["updated_at"] > orders_map[oid]["updated_at"]
            ):
                orders_map[oid] = item
        except Exception:
            continue

    processed_orders = []
    for item in orders_map.values():
        currency = item.get("currency", "USD")
        rate = RATES.get(currency, 1.0)
        amount = float(item.get("amount", 0.0))
        amount_usd = round(amount * rate, 2)

        # Parse created_at and convert to Asia/Kolkata business date
        created_str = item.get("created_at", "")
        dt_kolkata = None
        date_str = ""
        year_val, month_val = 0, 0
        if created_str:
            try:
                # Normalize trailing 'Z' if present
                clean_ts = created_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_ts)
                dt_kolkata = dt.astimezone(KOLKATA_TZ)
                date_str = dt_kolkata.strftime("%Y-%m-%d")
                year_val = dt_kolkata.year
                month_val = dt_kolkata.month
            except Exception:
                pass

        processed_orders.append(
            {
                "id": item["id"],
                "customer": item.get("customer", ""),
                "region": item.get("region", ""),
                "product": item.get("product", ""),
                "qty": int(item.get("qty", 0)),
                "unit_price": float(item.get("unit_price", 0.0)),
                "amount": amount,
                "currency": currency,
                "amount_usd": amount_usd,
                "status": item.get("status", ""),
                "date": date_str,
                "year": year_val,
                "month": month_val,
            }
        )

    # 3. Load into in-memory table
    db_conn.execute("DROP TABLE IF EXISTS orders")
    db_conn.execute("""
        CREATE TABLE orders (
            id VARCHAR,
            customer VARCHAR,
            region VARCHAR,
            product VARCHAR,
            qty INTEGER,
            unit_price DOUBLE,
            amount DOUBLE,
            currency VARCHAR,
            amount_usd DOUBLE,
            status VARCHAR,
            date VARCHAR,
            year INTEGER,
            month INTEGER
        )
    """)

    if processed_orders:
        import pandas as pd

        df = pd.DataFrame(processed_orders)
        db_conn.register("df_orders", df)
        db_conn.execute("INSERT INTO orders SELECT * FROM df_orders")


init_ledger_database()


# ==========================================
# 1. QUESTION 7: 12-FACTOR CONFIG (GET)
# ==========================================
def get_resolved_config(query_params):
    config = {}
    yaml_path = "config.development.yaml"
    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f) or {}

    load_dotenv(override=True)
    for key, val in os.environ.items():
        if key in config:
            config[key] = val

    for qk, qv in query_params.items():
        if qk == "set":
            for pair in qv if isinstance(qv, list) else [qv]:
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    config[k] = int(v) if v.isdigit() else v
        elif qk in config:
            config[qk] = int(qv) if qv.isdigit() else qv

    return config


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

    return get_resolved_config(dict(request.query_params))


# ==========================================
# 2. QUESTIONS 14 & 15: POST HANDLER
# ==========================================
@app.post("/")
@app.post("/{path:path}")
async def handle_post(request: Request, path: str = ""):
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    # --------------------------------------------------
    # BRANCH A: QUESTION 15 (Ledger Agent Question)
    # --------------------------------------------------
    if "question" in body:
        user_question = body["question"]

        system_prompt = """You are a SQL generator for DuckDB.
Table Schema:
orders(id VARCHAR, customer VARCHAR, region VARCHAR, product VARCHAR, qty INTEGER, unit_price DOUBLE, amount DOUBLE, currency VARCHAR, amount_usd DOUBLE, status VARCHAR, date VARCHAR, year INTEGER, month INTEGER)

CRITICAL RULES:
1. ONLY orders with status = 'paid' count as revenue or valid sales.
2. If asking for money/revenue, use SUM(amount_usd).
3. If asking for product names or customer IDs, match exact capitalization as stored.
4. Month numbers: Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12.
5. Return ONLY a single raw SQL query. No markdown, no quotes, no explanations."""

        try:
            # Call AI Pipe model
            headers = {
                "Authorization": f"Bearer {AIPIPE_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question},
                ],
                "temperature": 0.0,
            }
            resp = requests.post(
                "https://api.aipipe.org/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=8,
            )
            raw_sql = (
                resp.json()["choices"][0]["message"]["content"]
                .strip()
                .replace("```sql", "")
                .replace("```", "")
                .strip()
            )

            result = db_conn.execute(raw_sql).fetchone()[0]

            # Format result according to specification
            if isinstance(result, float):
                answer_val = round(result, 2)
            else:
                answer_val = result

            return JSONResponse({"answer": answer_val})
        except Exception as e:
            # Fallback direct response
            return JSONResponse({"answer": 0.0, "error": str(e)})

    # --------------------------------------------------
    # BRANCH B: QUESTION 14 (Live MCP Server)
    # --------------------------------------------------
    method = body.get("method")
    req_id = body.get("id")

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

    elif method == "notifications/initialized":
        if req_id is not None:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return Response(status_code=200)

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

    elif method == "tools/call":
        challenge = request.headers.get("x-exam-challenge", "")
        if not challenge and "params" in body:
            args = body["params"].get("arguments", {})
            if isinstance(args, dict):
                challenge = args.get("challenge", "")

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
