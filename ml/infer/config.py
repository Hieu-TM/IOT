"""Central configuration for the ml/ package.

Precedence (highest wins):
    CLI flag > environment variable > config.local.toml > config.toml > DEFAULTS

  * ml/config.toml       — COMMITTED. Documents every configurable key. Non-secret
                           defaults only. This is the file you read to find out
                           "what can I configure?".
  * ml/config.local.toml — GITIGNORED. Your API key and machine-specific overrides.

Env var names are AQUA_<SECTION>_<KEY> uppercased, e.g. AQUA_ROBOFLOW_API_KEY.
Env values arrive as strings and are coerced to the type of the matching DEFAULTS
entry (bool / int / float / str).

TOML is parsed with the standard library `tomllib` (Python 3.11+), so this adds
no third-party dependency.
"""

import os
import tomllib
from pathlib import Path

# Every configurable key lives here with its built-in default. `ml/config.toml`
# mirrors this structure with documentation. Keep the two in sync.
DEFAULTS = {
    "general": {
        "backend": "local",              # "local" (self-trained .pt) | "roboflow" (hosted API)
    },
    "ingest": {
        "api_url": "http://localhost:8000",
        "device_id": "pc-infer",
        "batch_lot": None,
        "timeout_s": 30,
    },
    "calibration": {
        # Intentionally None: an unset px_per_mm makes the CLI print the
        # "size_mm is a PLACEHOLDER" honesty warning. Only set this once you have
        # measured a real px/mm on the rig.
        "px_per_mm": None,
    },
    "local": {                            # Direction 1 — self-trained weights
        "weights": "ml/models/best.pt",
        "confidence": 0.25,
    },
    "roboflow": {                         # Direction 2 — hosted Workflow API
        "api_key": "",                    # SECRET — config.local.toml or AQUA_ROBOFLOW_API_KEY
        "endpoint": "https://serverless.roboflow.com",
        "workspace": "",                  # workspace slug
        "workflow_id": "",                # workflow slug (NOT the document id)
        "image_input_name": "image",      # the workflow's declared image input
        "predictions_key": "",            # empty => auto-detect (see probe)
        "confidence": 0.5,
        "timeout_s": 30,
        "retries": 2,
    },
    "dataset": {                          # Direction 1 — dataset download
        "workspace": "iam",
        "project": "microplastics-m7mf5",
        "version": 1,
        "format": "yolov11",
        "out_dir": "ml/datasets",
    },
    "train": {                            # Direction 1 — training
        "base_model": "yolo11n.pt",
        "epochs": 100,
        "imgsz": 416,
        "batch": 16,
    },
    "export": {                           # Direction 1 — TFLite export
        "tflite_imgsz": 192,
        "int8": True,
    },
}

DEFAULT_CONFIG_PATH = Path("ml/config.toml")
LOCAL_CONFIG_NAME = "config.local.toml"

# Keys whose DEFAULTS value is None carry no type to infer from, so declare it
# explicitly here. Anything not listed stays a string (e.g. ingest.batch_lot, where
# a lot code like "123" must NOT become a number).
_NONE_DEFAULT_TYPES = {
    ("calibration", "px_per_mm"): float,
}


def _deep_merge(base, override):
    out = {section: dict(values) for section, values in base.items()}
    for section, values in (override or {}).items():
        out.setdefault(section, {})
        for key, value in (values or {}).items():
            out[section][key] = value
    return out


def _read_toml(path):
    if path is None or not Path(path).is_file():
        return {}
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _coerce(section, key, value):
    """Coerce an env-var string to the type of the matching DEFAULTS entry."""
    if not isinstance(value, str):
        return value
    default = DEFAULTS.get(section, {}).get(key)
    if default is None:
        caster = _NONE_DEFAULT_TYPES.get((section, key))
        return caster(value) if caster else value
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int) and not isinstance(default, bool):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value


def _env_overrides(env):
    out = {}
    for section, keys in DEFAULTS.items():
        for key in keys:
            name = f"AQUA_{section.upper()}_{key.upper()}"
            if name in env:
                out.setdefault(section, {})[key] = _coerce(section, key, env[name])
    return out


class Config:
    """Read-only view over the merged configuration."""

    def __init__(self, data):
        self._data = data

    def get(self, section, key):
        return self._data.get(section, {}).get(key)

    def section(self, name):
        return dict(self._data.get(name, {}))

    def as_dict(self):
        return {section: dict(values) for section, values in self._data.items()}

    def missing_for(self, backend):
        """Human-readable messages for keys that are required but unset.

        Empty list == ready to run with this backend.
        """
        problems = []
        if backend == "roboflow":
            if not self.get("roboflow", "api_key"):
                problems.append(
                    "roboflow.api_key is not set - put it in ml/config.local.toml "
                    "or set AQUA_ROBOFLOW_API_KEY (never commit it).")
            if not self.get("roboflow", "workspace"):
                problems.append(
                    "roboflow.workspace is not set - the workspace slug from your "
                    "Roboflow workflow URL.")
            if not self.get("roboflow", "workflow_id"):
                problems.append(
                    "roboflow.workflow_id is not set - the workflow SLUG (not the "
                    "document id).")
        elif backend == "local":
            weights = self.get("local", "weights")
            if not weights or not Path(weights).is_file():
                problems.append(
                    f"local.weights not found at {weights!r} - train first "
                    "(python -m ml.train.train_detector) or set local.weights.")
        else:
            problems.append(
                f"general.backend={backend!r} is not one of: local, roboflow")
        return problems


def load(config_path=None, env=None):
    """Load layered config: DEFAULTS < config.toml < config.local.toml < env."""
    env = os.environ if env is None else env
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    data = _deep_merge(DEFAULTS, _read_toml(path))
    data = _deep_merge(data, _read_toml(Path(path).parent / LOCAL_CONFIG_NAME))
    data = _deep_merge(data, _env_overrides(env))
    return Config(data)
