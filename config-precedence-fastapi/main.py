"""FastAPI service for the 12-factor configuration precedence exercise."""
from pathlib import Path
import os
from typing import Any

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS: dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# This exercise explicitly assigns config.development.yaml as a config layer.
with (BASE_DIR / "config.development.yaml").open("r", encoding="utf-8") as file:
    YAML_CONFIG = yaml.safe_load(file) or {}

# Read the .env file as a distinct layer; do not inject it into os.environ,
# because OS environment variables must have higher precedence than .env.
DOTENV_CONFIG = dotenv_values(BASE_DIR / ".env")

# Environment-variable values pictured in the assignment are fallbacks for
# local runs. Real OS/container variables override these fallbacks.
OS_ENV_FALLBACKS = {
    "APP_PORT": "8321",
    "APP_WORKERS": "7",
    "APP_DEBUG": "false",
    "APP_LOG_LEVEL": "info",
}

CONFIG_KEYS = {"port", "workers", "debug", "log_level", "api_key"}


def bool_value(value: Any) -> bool:
    """Convert common true/false strings or values to a boolean."""
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    # Invalid boolean input is treated as false rather than raising an error.
    return False


def normalize_config(values: dict[str, Any]) -> dict[str, Any]:
    """Apply the assignment's type-coercion rules to the final merged config."""
    normalized = dict(values)
    for key in ("port", "workers"):
        try:
            normalized[key] = int(normalized[key])
        except (TypeError, ValueError):
            # Keep the service robust if an invalid value is sent as an override.
            normalized[key] = int(DEFAULTS[key])
    normalized["debug"] = bool_value(normalized.get("debug", False))
    normalized["log_level"] = str(normalized.get("log_level", "info"))
    normalized["api_key"] = str(normalized.get("api_key", ""))
    return normalized


def effective_config(overrides: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Merge defaults -> YAML -> .env -> OS env -> CLI/query overrides."""
    config = dict(DEFAULTS)

    # Layer 2: config.development.yaml
    config.update({key: value for key, value in YAML_CONFIG.items() if key in CONFIG_KEYS})

    # Layer 3: .env. Alias NUM_WORKERS to workers.
    dotenv_map = {
        "APP_PORT": "port",
        "NUM_WORKERS": "workers",
        "APP_DEBUG": "debug",
        "APP_LOG_LEVEL": "log_level",
        "APP_API_KEY": "api_key",
    }
    for env_key, config_key in dotenv_map.items():
        value = DOTENV_CONFIG.get(env_key)
        if value is not None:
            config[config_key] = value

    # Layer 4: OS/container variables. The fallback values reproduce the
    # assigned OS layer in the exercise when running locally without variables.
    os_map = {
        "APP_PORT": "port",
        "APP_WORKERS": "workers",
        "APP_DEBUG": "debug",
        "APP_LOG_LEVEL": "log_level",
        "APP_API_KEY": "api_key",
    }
    for env_key, config_key in os_map.items():
        value = os.environ.get(env_key, OS_ENV_FALLBACKS.get(env_key))
        if value is not None:
            config[config_key] = value

    # Layer 5: query parameters named set-key=value, e.g. ?set-port=9000.
    for param_name, raw_value in (overrides or []):
        if not param_name.startswith("set-"):
            continue
        key = param_name[4:].replace("-", "_").lower()
        if key in CONFIG_KEYS:
            config[key] = raw_value

    config = normalize_config(config)
    # Never expose the actual secret, regardless of its source or overrides.
    config["api_key"] = "****"
    return config


app = FastAPI(title="Effective Config API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "endpoint": "/effective-config"}


@app.get("/effective-config")
async def get_effective_config(request: Request) -> dict[str, Any]:
    return effective_config(list(request.query_params.multi_items()))
