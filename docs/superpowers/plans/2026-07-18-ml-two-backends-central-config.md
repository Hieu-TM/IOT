# ML Two Backends + Central Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the Aqua Scope detector into two independently usable backends — **Direction 1** (download the Roboflow *dataset*, self-train YOLO11n locally, own the `.pt`, path to TFLite/on-chip) and **Direction 2** (Roboflow hosted inference API, no local weights) — selected by a single `--backend` flag, and driven by one central, self-documenting TOML config file.

**Architecture:** The existing layered `ml/infer/` pipeline already isolates the model behind one module. Direction 2 adds `detector_roboflow.py` returning the *identical* `DetectionResult` contract, so `mapper`/`ingest_client`/`cli`/`preview` and all 28 existing tests are reused unchanged. A new `ml/infer/config.py` loads a layered TOML config (`config.toml` committed + documented, `config.local.toml` gitignored for secrets, env overrides), which supplies **defaults only** — CLI flags always win. Direction 1's training scripts move into an `ml/train/` package and read the same central config.

**Tech Stack:** Python 3.11+ (`tomllib` from the standard library — no PyYAML), Ultralytics YOLO11n (Direction 1), `requests` (Direction 2 + ingest), Pillow, pytest.

## Execution order (revised 2026-07-18)

**Direction 2 goes first.** Run tasks in this order: **1 → 2 → 3 → 4 → 7**.
Tasks **5 and 6 are DEFERRED** (Direction 1: dataset download + local training) — do not
start them in this pass. Task 7's README covers only what has shipped.

## Grounding limitation (read before Task 3)

The Roboflow integration targets a **Workflow** endpoint, not the simple
`detect.roboflow.com/{model}/{version}` API. Two facts constrain the design:

1. **The workflow's real output names are unknown at implementation time.** A workflow
   response is a JSON **list** (one entry per input image) where each entry is a dict keyed
   by *the workflow's own output names* — there is no guaranteed `predictions` key.
2. **There is no Roboflow MCP access and no API key in this environment**, so the real
   response cannot be captured before writing the parser.

Therefore the parser must **not hard-code output names**. It resolves predictions via a
configurable `roboflow.predictions_key` and, when that is empty, auto-detects by searching
the response for a list of prediction-shaped dicts. Task 3 also ships a **probe** command so
that once credentials exist, one run prints the real response *structure* (keys/types only —
never base64 image blobs) and the operator sets `predictions_key` accordingly.

## Global Constraints

- **Do NOT modify the web backend or the `particles`/`Sample` schema.** No file under `web/` may be touched.
- **All 28 existing tests must stay green, unchanged.** Existing CLI flags (`--weights --api-url --device-id --px-per-mm --batch-lot --dry-run`) keep working exactly as today; config supplies **defaults only**, CLI flags override.
- **The `px_per_mm` honesty guardrail must survive.** The committed `ml/config.toml` MUST leave `calibration.px_per_mm` unset (commented out), so an operator who does not set it still gets the `PLACEHOLDER, not a real calibration` warning. `ml/tests/test_cli.py::test_cli_warns_when_px_per_mm_omitted` depends on this.
- **Secrets are never committed.** `config.local.toml` is gitignored. Never print an API key in full (mask to last 4 chars at most).
- **Config precedence, highest wins:** CLI flag > environment variable > `config.local.toml` > `config.toml` > built-in default in `DEFAULTS`.
- **Env var naming:** `AQUA_<SECTION>_<KEY>` uppercased, e.g. `AQUA_ROBOFLOW_API_KEY`, `AQUA_INGEST_API_URL`.
- **Both backends return the identical contract:** `DetectionResult(detections: list[Detection], image_width: int, image_height: int)` where `Detection(bbox_xywh=(x, y, w, h) ints TOP-LEFT origin, class_name: str, confidence: float)`. Import these from `ml/infer/detector.py`; do not redefine them.
- **No Roboflow credentials, workspace, workflow id, or output names may be hard-coded anywhere.** Every one of them is a config key with an empty default. The values in the reference doc (`hieu-tran-crnbm`, the workflow slug) are EXAMPLES ONLY — they may change and must never appear in committed code or tests as required values.
- **Never log, print, or assert on base64 image blobs.** Workflow responses can carry image-shaped outputs of hundreds of KB. The probe prints structure (key names, types, lengths) only; any value that is a string longer than 200 chars is elided as `<base64 ...N bytes>`.
- **Do not add the `inference-sdk` dependency.** The workflow endpoint is a plain JSON POST — use `requests`, which is already a dependency. (The reference doc suggests `inference-sdk`; its own guardrail says to ask before adding heavy deps, and plain `requests` avoids one.)
- **Heavy/optional deps are imported lazily inside functions/`__init__`** (`ultralytics`, `roboflow`), so `import ml.infer.*` works without them installed.
- **`ml/infer/preview.py` stays local-backend only** and must still NOT contain the substring `ingest_client` (an existing test asserts this).
- Run tests with `python -m pytest ml/tests/ -v` from the repo root.

---

### Task 1: Central config loader

**Files:**
- Create: `ml/infer/config.py`
- Create: `ml/config.toml`
- Modify: `ml/.gitignore` (add `config.local.toml`)
- Test: `ml/tests/test_config.py`

**Interfaces:**
- Produces: `DEFAULTS: dict`; `Config` class with `.get(section, key)`, `.section(name) -> dict`, `.as_dict() -> dict`, `.missing_for(backend) -> list[str]`; `load(config_path=None, env=None) -> Config`.

- [ ] **Step 1: Write the failing test**

`ml/tests/test_config.py`:
```python
from ml.infer import config as cfgmod


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_when_no_file(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml", env={})
    assert cfg.get("general", "backend") == "local"
    assert cfg.get("ingest", "api_url") == "http://localhost:8000"
    assert cfg.get("calibration", "px_per_mm") is None


def test_config_toml_overrides_defaults(tmp_path):
    p = _write(tmp_path / "config.toml",
               '[ingest]\napi_url = "http://example:9000"\n')
    cfg = cfgmod.load(p, env={})
    assert cfg.get("ingest", "api_url") == "http://example:9000"
    assert cfg.get("ingest", "device_id") == "pc-infer"  # untouched default


def test_local_toml_overrides_config_toml(tmp_path):
    _write(tmp_path / "config.toml", '[roboflow]\napi_key = "from-config"\n')
    _write(tmp_path / "config.local.toml", '[roboflow]\napi_key = "from-local"\n')
    cfg = cfgmod.load(tmp_path / "config.toml", env={})
    assert cfg.get("roboflow", "api_key") == "from-local"


def test_env_overrides_files_and_coerces_types(tmp_path):
    _write(tmp_path / "config.toml", '[train]\nepochs = 10\n')
    cfg = cfgmod.load(
        tmp_path / "config.toml",
        env={"AQUA_ROBOFLOW_API_KEY": "from-env", "AQUA_TRAIN_EPOCHS": "42"},
    )
    assert cfg.get("roboflow", "api_key") == "from-env"
    assert cfg.get("train", "epochs") == 42          # coerced str -> int
    assert isinstance(cfg.get("train", "epochs"), int)


def test_env_coerces_bool_and_float(tmp_path):
    cfg = cfgmod.load(
        tmp_path / "missing.toml",
        env={"AQUA_EXPORT_INT8": "false", "AQUA_ROBOFLOW_CONFIDENCE": "0.6"},
    )
    assert cfg.get("export", "int8") is False
    assert cfg.get("roboflow", "confidence") == 0.6


def test_section_returns_copy(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml", env={})
    sec = cfg.section("roboflow")
    sec["api_key"] = "mutated"
    assert cfg.get("roboflow", "api_key") == ""      # original untouched


def test_missing_for_roboflow_reports_every_unset_key(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml", env={})
    problems = cfg.missing_for("roboflow")
    assert any("api_key" in p for p in problems)
    assert any("workspace" in p for p in problems)
    assert any("workflow_id" in p for p in problems)


def test_missing_for_roboflow_clean_when_set(tmp_path):
    cfg = cfgmod.load(
        tmp_path / "missing.toml",
        env={"AQUA_ROBOFLOW_API_KEY": "k",
             "AQUA_ROBOFLOW_WORKSPACE": "ws",
             "AQUA_ROBOFLOW_WORKFLOW_ID": "wf"},
    )
    assert cfg.missing_for("roboflow") == []


def test_roboflow_defaults_are_empty_no_hardcoded_workspace(tmp_path):
    """Credentials/slugs must never ship as defaults - they are per-user."""
    cfg = cfgmod.load(tmp_path / "missing.toml", env={})
    assert cfg.get("roboflow", "api_key") == ""
    assert cfg.get("roboflow", "workspace") == ""
    assert cfg.get("roboflow", "workflow_id") == ""
    assert cfg.get("roboflow", "predictions_key") == ""
    assert cfg.get("roboflow", "endpoint") == "https://serverless.roboflow.com"


def test_missing_for_local_reports_absent_weights(tmp_path):
    cfg = cfgmod.load(
        tmp_path / "missing.toml",
        env={"AQUA_LOCAL_WEIGHTS": str(tmp_path / "nope.pt")},
    )
    problems = cfg.missing_for("local")
    assert any("weights" in p for p in problems)


def test_missing_for_local_clean_when_weights_exist(tmp_path):
    w = tmp_path / "best.pt"
    w.write_bytes(b"fake")
    cfg = cfgmod.load(tmp_path / "missing.toml",
                      env={"AQUA_LOCAL_WEIGHTS": str(w)})
    assert cfg.missing_for("local") == []


def test_missing_for_rejects_unknown_backend(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml", env={})
    problems = cfg.missing_for("bogus")
    assert any("bogus" in p for p in problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'config' from 'ml.infer'`

- [ ] **Step 3: Write minimal implementation**

`ml/infer/config.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_config.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Create the committed, self-documenting config file**

`ml/config.toml` — this is the file an operator reads to learn what can be configured:
```toml
# Aqua Scope — cau hinh tap trung cho package ml/
#
# Thu tu uu tien (cao thang thap):
#   co CLI  >  bien moi truong  >  config.local.toml  >  file nay  >  mac dinh trong code
#
# File NAY duoc commit: chi chua gia tri KHONG bi mat, va tai lieu hoa moi khoa.
# Bi mat (API key) -> dat trong ml/config.local.toml (da gitignore) hoac bien moi truong.
# Ten bien moi truong: AQUA_<SECTION>_<KEY>, vd AQUA_ROBOFLOW_API_KEY.

[general]
# Chon huong chay:
#   "local"    = Huong 1 - model .pt tu train (can weights, chay offline, xuong duoc chip)
#   "roboflow" = Huong 2 - goi API Roboflow (khong can weights, can mang + api_key)
backend = "local"

[ingest]
api_url = "http://localhost:8000"   # backend web nhan ket qua
device_id = "pc-infer"              # ghi vao ban ghi audit
# batch_lot = "LOT-001"             # tuy chon: ma lo san xuat
timeout_s = 30

[calibration]
# CO Y DE TRONG. Chua set => CLI se in canh bao "size_mm la PLACEHOLDER,
# khong phai hieu chuan that". Chi set khi ban DA DO duoc px/mm that tren rig.
# px_per_mm = 14.0

[local]
# Huong 1 - weights tu train. Tao ra bang: python -m ml.train.train_detector
weights = "ml/models/best.pt"
confidence = 0.25

[roboflow]
# Huong 2 - hosted Workflow API. KHONG dien api_key vao day (file nay duoc commit).
# Dat trong ml/config.local.toml hoac: export AQUA_ROBOFLOW_API_KEY=...
api_key = ""
endpoint = "https://serverless.roboflow.com"
workspace = ""                      # workspace slug, lay tu URL workflow cua ban
workflow_id = ""                    # workflow SLUG (khong phai document id)
image_input_name = "image"          # ten input anh ma workflow khai bao
# Ten khoa output chua predictions trong response cua workflow.
# De TRONG => tu do tim. Chay lenh sau de xem cau truc response that:
#   python -m ml.infer.probe <anh.jpg>
# roi dien ten khoa vao day, vd "model_predictions" hoac "model_predictions.predictions"
predictions_key = ""
timeout_s = 30
retries = 2

[dataset]
# Huong 1 - tai dataset ve de tu train (weights KHONG tai duoc, nhung dataset thi duoc)
workspace = "iam"
project = "microplastics-m7mf5"
version = 1
format = "yolov11"
out_dir = "ml/datasets"

[train]
base_model = "yolo11n.pt"
epochs = 100
imgsz = 416
batch = 16

[export]
tflite_imgsz = 192                  # nho nhat ma van phan giai duoc hat ~2mm
int8 = true
```

- [ ] **Step 6: Gitignore the secrets file**

Append to `ml/.gitignore`:
```
# Cau hinh cuc bo: chua API key + ghi de theo may. KHONG commit.
config.local.toml
```

- [ ] **Step 7: Run the full suite to confirm nothing regressed**

Run: `python -m pytest ml/tests/ -v`
Expected: 40 passed, 1 skipped (28 existing + 12 new; smoke test still skips).

- [ ] **Step 8: Commit**

```bash
git add ml/infer/config.py ml/config.toml ml/.gitignore ml/tests/test_config.py
git commit -m "feat(ml): central layered TOML config (defaults<toml<local<env)"
```

---

### Task 2: Wire config into the CLI as defaults

**Files:**
- Modify: `ml/infer/cli.py`
- Test: `ml/tests/test_cli.py` (add tests; do not change existing ones)

**Interfaces:**
- Consumes: `config.load(config_path, env) -> Config` (Task 1).
- Produces: `build_arg_parser()` gains `--config` and `--backend`; `main(argv=None) -> int` resolves each setting as `flag if flag is not None else config value`. `config` is referenced as the module attribute `cli.config` so tests can monkeypatch it.

- [ ] **Step 1: Write the failing test**

Append to `ml/tests/test_cli.py`:
```python
def test_cli_uses_config_defaults_when_flags_omitted(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[ingest]\napi_url = "http://from-config:1234"\n'
        'device_id = "dev-from-config"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    seen = {}

    def fake_post(api_url, metadata, image_bytes, image_name):
        seen["api_url"] = api_url
        seen["device_id"] = metadata["device_id"]

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--config", str(cfg_file), "--px-per-mm", "10"])

    assert rc == 0
    assert seen["api_url"] == "http://from-config:1234"
    assert seen["device_id"] == "dev-from-config"


def test_cli_flag_overrides_config(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[ingest]\napi_url = "http://from-config:1234"\n',
                        encoding="utf-8")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    seen = {}

    def fake_post(api_url, metadata, image_bytes, image_name):
        seen["api_url"] = api_url

        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--config", str(cfg_file),
                   "--api-url", "http://from-flag:9999", "--px-per-mm", "10"])

    assert rc == 0
    assert seen["api_url"] == "http://from-flag:9999"   # flag beats config


def test_cli_config_px_per_mm_suppresses_placeholder_warning(tmp_path, monkeypatch, capsys):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[calibration]\npx_per_mm = 20.0\n', encoding="utf-8")
    monkeypatch.setattr(cli, "Detector", _FakeDetector)

    def fake_post(api_url, metadata, image_bytes, image_name):
        class R:
            status = "created"
            http_status = 201
            detail = ""

        return R()

    monkeypatch.setattr(cli, "post", fake_post)

    rc = cli.main([str(tmp_path), "--config", str(cfg_file)])  # no --px-per-mm
    out = capsys.readouterr().out

    assert rc == 0
    assert "PLACEHOLDER" not in out   # a configured calibration is a deliberate choice
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_cli.py -v`
Expected: FAIL — `unrecognized arguments: --config`

- [ ] **Step 3: Write minimal implementation**

In `ml/infer/cli.py`, add the import (top of file, alongside the others):
```python
from . import config
```

Replace `build_arg_parser()` with (note: defaults become `None` so "not given" is distinguishable from "given the old default"):
```python
def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="python -m ml.infer",
        description="Run the detector on images and POST count/size/label to "
                    "/api/ingest. Settings come from ml/config.toml unless a "
                    "flag overrides them.",
    )
    p.add_argument("input", nargs="?", help="Image file or folder of images")
    p.add_argument("--config", default=None,
                   help="Path to config.toml (default: ml/config.toml)")
    p.add_argument("--backend", choices=["local", "roboflow"], default=None,
                   help="local = self-trained .pt; roboflow = hosted API")
    p.add_argument("--weights", default=None)
    p.add_argument("--api-url", default=None)
    p.add_argument("--device-id", default=None)
    p.add_argument("--px-per-mm", type=float, default=None)
    p.add_argument("--batch-lot", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="Detect and print only; do not POST to the API")
    return p
```

Then at the top of `main()`, replace the first lines (from `args = ...` through the `detector = Detector(args.weights)` line) with:
```python
def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    cfg = config.load(args.config)

    if not args.input:
        print("[error] missing input (image file or folder). See --help.")
        return 2

    api_url = args.api_url if args.api_url is not None else cfg.get("ingest", "api_url")
    device_id = args.device_id if args.device_id is not None else cfg.get("ingest", "device_id")
    batch_lot = args.batch_lot if args.batch_lot is not None else cfg.get("ingest", "batch_lot")
    weights = args.weights if args.weights is not None else cfg.get("local", "weights")

    px_setting = (args.px_per_mm if args.px_per_mm is not None
                  else cfg.get("calibration", "px_per_mm"))
    px, used_default = resolve_px_per_mm(px_setting)
    if used_default:
        print(f"[warn] px_per_mm not set; using default {px} px/mm. "
              "size_mm is a PLACEHOLDER, not a real calibration.")

    detector = Detector(weights)
    source = FolderSource(args.input)
```

In the body of the loop, replace the three `args.` usages that moved to locals:
- `device_id=args.device_id,` → `device_id=device_id,`
- `batch_lot=args.batch_lot,` → `batch_lot=batch_lot,`
- `res = post(args.api_url, metadata, ...)` → `res = post(api_url, metadata, ...)`

Leave everything else (collision handling, tallies, summary, return code) exactly as it is.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_cli.py -v`
Expected: PASS — all 5 pre-existing cli tests plus the 3 new ones (8 passed).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest ml/tests/ -v`
Expected: 43 passed, 1 skipped. If `test_cli_warns_when_px_per_mm_omitted` fails, `ml/config.toml` has `px_per_mm` set — it must stay commented out (Global Constraints).

- [ ] **Step 6: Commit**

```bash
git add ml/infer/cli.py ml/tests/test_cli.py
git commit -m "feat(ml): CLI reads central config for defaults; flags still win"
```

---

### Task 3: Roboflow Workflow backend + response probe (Direction 2)

**Files:**
- Create: `ml/infer/detector_roboflow.py`
- Create: `ml/infer/probe.py`
- Test: `ml/tests/test_detector_roboflow.py`

**Interfaces:**
- Consumes: `Detection`, `DetectionResult` from `ml/infer/detector.py` (import them; do NOT redefine); `config.load()` (Task 1, used by the probe).
- Produces:
  - `RoboflowWorkflowDetector(api_key, workspace, workflow_id, endpoint="https://serverless.roboflow.com", image_input_name="image", predictions_key="", timeout=30, retries=2)` with `.url` property, `.fetch_raw(image_bytes) -> parsed JSON`, `.run(image_bytes) -> DetectionResult`, `.run_array(rgb_array, width=None, height=None) -> DetectionResult` (interface parity with `Detector`).
  - Module functions `extract_predictions(entry, predictions_key="") -> list[dict]` and `summarize_response(value, depth=0, max_depth=4) -> str`.
  - `ml.infer.probe.main(argv=None) -> int`.

**Two critical shape details — both are pinned by the tests below:**

1. **Endpoint + envelope (Workflow, not the simple detect API):**
   `POST {endpoint}/{workspace}/workflows/{workflow_id}` with JSON body
   `{"api_key": ..., "inputs": {"<image_input_name>": {"type": "base64", "value": "<b64>"}}}`.
2. **Response is a LIST** (one entry per input image) and each entry is keyed by *the
   workflow's own output names* — there is **no** guaranteed `predictions` key. Locate the
   prediction list via the configured `predictions_key` (dotted paths supported), else
   auto-detect. Never hard-code an output name.

**Bbox mapping:** Roboflow returns each box as **CENTER** `x, y` plus `width, height`. Our
`Detection.bbox_xywh` is **TOP-LEFT** origin. Convert `x_topleft = x - width/2`,
`y_topleft = y - height/2`. Image dimensions come from decoding the image locally (the
workflow response may not carry them).

- [ ] **Step 1: Write the failing test**

`ml/tests/test_detector_roboflow.py`:
```python
import io

import numpy as np
import pytest
from PIL import Image

from ml.infer import detector_roboflow as rfmod
from ml.infer.detector import Detection, DetectionResult


def _jpeg_bytes(w=64, h=48):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _detector(**kw):
    kw.setdefault("api_key", "k")
    kw.setdefault("workspace", "ws")
    kw.setdefault("workflow_id", "wf")
    return rfmod.RoboflowWorkflowDetector(**kw)


class _Resp:
    def __init__(self, payload, code=200):
        self._payload = payload
        self.status_code = code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise rfmod.requests.HTTPError(f"status {self.status_code}")


# --- construction / validation -------------------------------------------

def test_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        _detector(api_key="")


def test_requires_workspace():
    with pytest.raises(ValueError, match="workspace"):
        _detector(workspace="")


def test_requires_workflow_id():
    with pytest.raises(ValueError, match="workflow_id"):
        _detector(workflow_id="")


def test_url_is_endpoint_workspace_workflows_id():
    det = _detector(workspace="my-ws", workflow_id="my-wf")
    assert det.url == "https://serverless.roboflow.com/my-ws/workflows/my-wf"


# --- request envelope ----------------------------------------------------

def test_run_posts_workflow_envelope(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp([{}])

    monkeypatch.setattr(rfmod.requests, "post", fake_post)

    det = _detector(image_input_name="photo")
    det.run(_jpeg_bytes())

    assert captured["url"] == det.url
    assert captured["json"]["api_key"] == "k"
    image_input = captured["json"]["inputs"]["photo"]
    assert image_input["type"] == "base64"
    assert isinstance(image_input["value"], str) and image_input["value"]


# --- prediction extraction (output names are NOT hard-coded) -------------

def test_extract_with_explicit_key():
    entry = {"my_out": {"predictions": [{"x": 1, "y": 1, "width": 2, "height": 2}]}}
    assert len(rfmod.extract_predictions(entry, "my_out")) == 1


def test_extract_with_dotted_key():
    entry = {"a": {"b": [{"x": 1, "y": 1, "width": 2, "height": 2}]}}
    assert len(rfmod.extract_predictions(entry, "a.b")) == 1


def test_extract_autodetects_nested_predictions():
    entry = {"model_predictions": {"predictions": [
        {"x": 1, "y": 1, "width": 2, "height": 2}]}}
    assert len(rfmod.extract_predictions(entry)) == 1


def test_extract_autodetects_arbitrary_output_name():
    entry = {"whatever_the_user_named_it": [
        {"x": 1, "y": 1, "width": 2, "height": 2}]}
    assert len(rfmod.extract_predictions(entry)) == 1


def test_extract_returns_empty_when_nothing_matches():
    assert rfmod.extract_predictions({"stats": {"count": 3}}) == []
    assert rfmod.extract_predictions({}) == []


# --- bbox conversion -----------------------------------------------------

def test_run_converts_center_bbox_to_top_left(monkeypatch):
    payload = [{"model_predictions": {"predictions": [
        # center (100, 200), size 40x60 -> top-left (80, 170)
        {"x": 100, "y": 200, "width": 40, "height": 60,
         "class": "fragment", "confidence": 0.87}]}}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))

    result = _detector().run(_jpeg_bytes(w=640, h=480))

    assert isinstance(result, DetectionResult)
    assert result.image_width == 640 and result.image_height == 480
    assert len(result.detections) == 1
    d = result.detections[0]
    assert isinstance(d, Detection)
    assert d.bbox_xywh == (80, 170, 40, 60)
    assert d.class_name == "fragment"
    assert d.confidence == 0.87


def test_run_handles_multiple_predictions(monkeypatch):
    payload = [{"out": [
        {"x": 10, "y": 10, "width": 4, "height": 4, "class": "fiber", "confidence": 0.5},
        {"x": 50, "y": 60, "width": 10, "height": 20, "class": "film", "confidence": 0.9}]}]
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(payload))

    result = _detector().run(_jpeg_bytes())

    assert [d.bbox_xywh for d in result.detections] == [(8, 8, 4, 4), (45, 50, 10, 20)]
    assert [d.class_name for d in result.detections] == ["fiber", "film"]


def test_run_returns_empty_detections_when_workflow_found_none(monkeypatch):
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp([{"out": []}]))
    result = _detector().run(_jpeg_bytes(w=32, h=32))
    assert result.detections == []
    assert result.image_width == 32 and result.image_height == 32


def test_run_array_encodes_and_delegates(monkeypatch):
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp([{}]))
    result = _detector().run_array(np.zeros((32, 48, 3), dtype=np.uint8))
    assert isinstance(result, DetectionResult)
    assert result.image_width == 48 and result.image_height == 32


# --- retries -------------------------------------------------------------

def test_run_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    payload = [{"out": [{"x": 5, "y": 5, "width": 2, "height": 2}]}]

    def flaky(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise rfmod.requests.ConnectionError("boom")
        return _Resp(payload)

    monkeypatch.setattr(rfmod.requests, "post", flaky)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    result = _detector(retries=2).run(_jpeg_bytes())

    assert calls["n"] == 2
    assert len(result.detections) == 1


def test_run_raises_after_retries_exhausted(monkeypatch):
    def always_fail(url, json=None, timeout=None):
        raise rfmod.requests.ConnectionError("down")

    monkeypatch.setattr(rfmod.requests, "post", always_fail)
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)

    with pytest.raises(rfmod.requests.ConnectionError):
        _detector(retries=1).run(_jpeg_bytes())


def test_run_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(rfmod.requests, "post",
                        lambda url, json=None, timeout=None: _Resp({}, code=403))
    monkeypatch.setattr(rfmod.time, "sleep", lambda s: None)
    with pytest.raises(rfmod.requests.HTTPError):
        _detector(retries=0).run(_jpeg_bytes())


# --- probe summariser (must never emit blobs) ----------------------------

def test_summarize_elides_large_blobs():
    out = rfmod.summarize_response({"visualization": "A" * 5000})
    assert "A" * 100 not in out
    assert "elided" in out


def test_summarize_reports_keys_and_types():
    out = rfmod.summarize_response({"count": 3, "preds": [{"x": 1}]})
    assert "count" in out
    assert "preds" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_detector_roboflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.infer.detector_roboflow'`

- [ ] **Step 3: Write minimal implementation**

`ml/infer/detector_roboflow.py`:
```python
"""Direction 2 - Roboflow hosted WORKFLOW inference. Same contract as detector.Detector.

Why this exists: Roboflow's free tier does not let you download the TRAINED WEIGHTS
of a model trained on their platform, only run it. This backend needs no local
weights and no ultralytics - but it needs the network plus an API key, and it CANNOT
be exported to TFLite/on-chip. That is Direction 1's job.

Endpoint shape (a Workflow, not the simple detect API):
    POST {endpoint}/{workspace}/workflows/{workflow_id}
    {"api_key": ..., "inputs": {"<image_input_name>": {"type": "base64", "value": ...}}}

The response is a LIST (one entry per input image); each entry is a dict keyed by the
WORKFLOW'S OWN output names - there is no guaranteed "predictions" key, and the names
change per workflow. So predictions are located via the configured `predictions_key`
(dotted paths supported) or auto-detected. Nothing about a specific workspace,
workflow, or output name is hard-coded here.

Run `python -m ml.infer.probe <image>` once you have credentials to print the real
response structure, then pin roboflow.predictions_key in ml/config.toml.
"""

import base64
import time
from io import BytesIO

import requests
from PIL import Image

from .detector import Detection, DetectionResult

# A prediction dict is recognised by carrying a full bbox, whatever it is nested under.
_BBOX_KEYS = ("x", "y", "width", "height")


def _looks_like_predictions(value):
    return (isinstance(value, list) and value
            and isinstance(value[0], dict)
            and all(k in value[0] for k in _BBOX_KEYS))


def _dig(node, dotted):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def extract_predictions(entry, predictions_key=""):
    """Locate the list of prediction dicts inside ONE workflow output entry.

    With `predictions_key` set, read exactly that path (and unwrap a nested
    "predictions" list if the path lands on a dict). With it empty, search
    breadth-first so the shallowest bbox-shaped list wins.
    """
    if predictions_key:
        node = _dig(entry, predictions_key)
        if isinstance(node, dict):
            node = node.get("predictions")
        return node if _looks_like_predictions(node) else []

    queue = [entry]
    while queue:
        node = queue.pop(0)
        if _looks_like_predictions(node):
            return node
        if isinstance(node, dict):
            queue.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            queue.extend(v for v in node if isinstance(v, (dict, list)))
    return []


def _to_detection(pred):
    w = int(round(float(pred["width"])))
    h = int(round(float(pred["height"])))
    # Roboflow gives the bbox CENTER; Detection.bbox_xywh is TOP-LEFT.
    x = int(round(float(pred["x"]) - w / 2))
    y = int(round(float(pred["y"]) - h / 2))
    return Detection(
        bbox_xywh=(x, y, w, h),
        class_name=str(pred.get("class") or pred.get("class_name") or "unknown"),
        confidence=float(pred.get("confidence", 0.0)),
    )


def _describe(value):
    if isinstance(value, str):
        if len(value) > 200:
            return f"<blob elided, {len(value)} chars>"
        return f"str({value!r})"
    if isinstance(value, bool):
        return f"bool({value})"
    if isinstance(value, (int, float)):
        return f"{type(value).__name__}({value})"
    if isinstance(value, list):
        return f"list(len={len(value)})"
    if isinstance(value, dict):
        return f"dict(keys={list(value.keys())})"
    return type(value).__name__


def summarize_response(value, depth=0, max_depth=4):
    """Render a response's STRUCTURE (key names, types, lengths).

    Never emits raw values longer than 200 chars - workflow outputs can carry
    base64 images of hundreds of KB, which must not be logged.
    """
    pad = "  " * depth
    if isinstance(value, dict):
        if depth >= max_depth:
            return f"{pad}dict(keys={list(value.keys())})"
        parts = []
        for key, sub in value.items():
            parts.append(f"{pad}{key}: {_describe(sub)}")
            if isinstance(sub, (dict, list)) and sub:
                parts.append(summarize_response(sub, depth + 1, max_depth))
        return "\n".join(parts)
    if isinstance(value, list):
        if not value:
            return f"{pad}(empty list)"
        head = value[0]
        out = f"{pad}[0] {_describe(head)}"
        if isinstance(head, (dict, list)) and depth < max_depth:
            out += "\n" + summarize_response(head, depth + 1, max_depth)
        return out
    return f"{pad}{_describe(value)}"


class RoboflowWorkflowDetector:
    def __init__(self, api_key, workspace, workflow_id,
                 endpoint="https://serverless.roboflow.com",
                 image_input_name="image", predictions_key="",
                 timeout=30, retries=2):
        if not api_key:
            raise ValueError(
                "roboflow.api_key is required - set it in ml/config.local.toml "
                "or AQUA_ROBOFLOW_API_KEY")
        if not workspace:
            raise ValueError("roboflow.workspace is required")
        if not workflow_id:
            raise ValueError("roboflow.workflow_id is required")
        self.api_key = api_key
        self.workspace = workspace
        self.workflow_id = workflow_id
        self.endpoint = str(endpoint).rstrip("/")
        self.image_input_name = image_input_name or "image"
        self.predictions_key = predictions_key or ""
        self.timeout = timeout
        self.retries = retries

    @property
    def url(self):
        return f"{self.endpoint}/{self.workspace}/workflows/{self.workflow_id}"

    def fetch_raw(self, image_bytes):
        """POST the image and return the parsed JSON response (used by the probe)."""
        payload = {
            "api_key": self.api_key,
            "inputs": {
                self.image_input_name: {
                    "type": "base64",
                    "value": base64.b64encode(image_bytes).decode("ascii"),
                }
            },
        }
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))  # backoff
        raise last_error

    def run(self, image_bytes):
        # Dimensions come from decoding locally: the workflow response may not carry them.
        width, height = Image.open(BytesIO(image_bytes)).size
        raw = self.fetch_raw(image_bytes)
        entries = raw if isinstance(raw, list) else [raw]
        entry = entries[0] if entries else {}
        predictions = extract_predictions(entry, self.predictions_key)
        return DetectionResult(
            detections=[_to_detection(p) for p in predictions],
            image_width=width,
            image_height=height,
        )

    def run_array(self, rgb_array, width=None, height=None):
        """Interface parity with Detector.run_array - encodes then delegates."""
        buf = BytesIO()
        Image.fromarray(rgb_array).save(buf, format="JPEG")
        return self.run(buf.getvalue())
```

- [ ] **Step 4: Write the probe command**

`ml/infer/probe.py`:
```python
"""Print the STRUCTURE of a real Roboflow workflow response - never its blobs.

The workflow's output names are chosen by whoever built the workflow, so they
cannot be known ahead of time. Run this once with real credentials to see them,
then set roboflow.predictions_key in ml/config.toml.

Usage:
    python -m ml.infer.probe path/to/image.jpg
"""

import argparse
import sys
from pathlib import Path

from . import config as config_mod
from .detector_roboflow import (
    RoboflowWorkflowDetector,
    extract_predictions,
    summarize_response,
)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m ml.infer.probe")
    parser.add_argument("image", help="A sample image to send to the workflow")
    parser.add_argument("--config", default=None,
                        help="Path to config.toml (default: ml/config.toml)")
    args = parser.parse_args(argv)

    cfg = config_mod.load(args.config)
    problems = cfg.missing_for("roboflow")
    if problems:
        print("Config NOT ready:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    rf = cfg.section("roboflow")
    detector = RoboflowWorkflowDetector(
        api_key=rf.get("api_key"),
        workspace=rf.get("workspace"),
        workflow_id=rf.get("workflow_id"),
        endpoint=rf.get("endpoint"),
        image_input_name=rf.get("image_input_name"),
        predictions_key=rf.get("predictions_key"),
        timeout=rf.get("timeout_s"),
        retries=rf.get("retries"),
    )

    raw = detector.fetch_raw(Path(args.image).read_bytes())
    print(f"POST {detector.url}")
    print("\n--- response structure (long values elided) ---")
    print(summarize_response(raw))

    entries = raw if isinstance(raw, list) else [raw]
    key = rf.get("predictions_key")
    found = extract_predictions(entries[0] if entries else {}, key)
    print(f"\nResolved {len(found)} prediction(s) with predictions_key={key!r}")
    if not found:
        print("No predictions resolved. Set roboflow.predictions_key to the key "
              "above that holds the bbox list (dotted paths supported).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_detector_roboflow.py -v`
Expected: PASS (18 passed)

Also confirm the probe imports cleanly (it must not need credentials to import):
Run: `python -c "import ml.infer.probe"`
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add ml/infer/detector_roboflow.py ml/infer/probe.py ml/tests/test_detector_roboflow.py
git commit -m "feat(ml): Roboflow Workflow backend + response probe (Direction 2)"
```

---

### Task 4: Backend selection + `--check-config` in the CLI

**Files:**
- Modify: `ml/infer/cli.py`
- Test: `ml/tests/test_cli.py` (add tests)

**Interfaces:**
- Consumes: `RoboflowWorkflowDetector` (Task 3), `Config.missing_for` (Task 1).
- Produces: `cli.RoboflowWorkflowDetector` module attribute (monkeypatchable, same as `cli.Detector`); `build_detector(cfg, backend, weights)` helper; `--check-config` flag that validates and exits without running.

- [ ] **Step 1: Write the failing test**

Append to `ml/tests/test_cli.py`:
```python
def test_check_config_reports_ok_for_local_with_weights(tmp_path, capsys):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fake")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f'[local]\nweights = "{weights.as_posix()}"\n',
                        encoding="utf-8")

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "OK" in out


def test_check_config_reports_missing_roboflow_key(tmp_path, capsys):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[general]\nbackend = "roboflow"\n', encoding="utf-8")

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "api_key" in out


def test_check_config_never_prints_the_api_key(tmp_path, capsys):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[general]\nbackend = "roboflow"\n'
        '[roboflow]\napi_key = "SUPERSECRET123"\nmodel_id = "m"\n',
        encoding="utf-8",
    )

    rc = cli.main(["--config", str(cfg_file), "--check-config"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "SUPERSECRET123" not in out   # secrets must never be echoed


def test_backend_roboflow_builds_workflow_detector(tmp_path, monkeypatch):
    _jpeg(tmp_path / "a.jpg")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[roboflow]\napi_key = "k"\nworkspace = "ws"\nworkflow_id = "wf"\n'
        'predictions_key = "out"\n',
        encoding="utf-8",
    )

    built = {}

    class _FakeWorkflowDetector:
        def __init__(self, **kwargs):
            built.update(kwargs)

        def run(self, image_bytes):
            return DetectionResult(
                detections=[Detection((1, 2, 3, 4), "fiber", 0.8)],
                image_width=32, image_height=32,
            )

    monkeypatch.setattr(cli, "RoboflowWorkflowDetector", _FakeWorkflowDetector)
    monkeypatch.setattr(
        cli, "post",
        lambda *a, **k: type("R", (), {"status": "created",
                                       "http_status": 201, "detail": ""})(),
    )

    rc = cli.main([str(tmp_path), "--config", str(cfg_file),
                   "--backend", "roboflow", "--px-per-mm", "10"])

    assert rc == 0
    assert built["api_key"] == "k"
    assert built["workspace"] == "ws"
    assert built["workflow_id"] == "wf"
    assert built["predictions_key"] == "out"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_cli.py -v`
Expected: FAIL — `unrecognized arguments: --check-config`

- [ ] **Step 3: Write minimal implementation**

In `ml/infer/cli.py`, add the import next to the existing `from .detector import Detector`:
```python
from .detector_roboflow import RoboflowWorkflowDetector
```

Add the flag inside `build_arg_parser()`, after `--dry-run`:
```python
    p.add_argument("--check-config", action="store_true",
                   help="Validate the resolved config for the chosen backend and exit")
```

Add this helper above `main()`:
```python
def build_detector(cfg, backend, weights):
    """Construct the detector for the chosen backend.

    Both backends return the identical DetectionResult contract, so everything
    downstream (mapper, ingest_client) is backend-agnostic.
    """
    if backend == "roboflow":
        rf = cfg.section("roboflow")
        return RoboflowWorkflowDetector(
            api_key=rf.get("api_key"),
            workspace=rf.get("workspace"),
            workflow_id=rf.get("workflow_id"),
            endpoint=rf.get("endpoint"),
            image_input_name=rf.get("image_input_name"),
            predictions_key=rf.get("predictions_key"),
            timeout=rf.get("timeout_s"),
            retries=rf.get("retries"),
        )
    return Detector(weights)
```

In `main()`, right after `cfg = config.load(args.config)`, insert the backend resolution and the check-config early exit (this runs *before* the missing-input guard, so `--check-config` needs no input path):
```python
    backend = args.backend if args.backend is not None else cfg.get("general", "backend")

    if args.check_config:
        problems = cfg.missing_for(backend)
        print(f"backend = {backend}")
        if problems:
            print("Config NOT ready:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("Config OK - ready to run.")
        return 0
```

Finally replace `detector = Detector(weights)` with:
```python
    detector = build_detector(cfg, backend, weights)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_cli.py -v`
Expected: PASS (12 passed — 5 original + 3 from Task 2 + 4 new)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest ml/tests/ -v`
Expected: 65 passed, 1 skipped (28 existing + 12 config + 3 cli/T2 + 18 roboflow + 4 cli/T4).

- [ ] **Step 6: Commit**

```bash
git add ml/infer/cli.py ml/tests/test_cli.py
git commit -m "feat(ml): --backend selection and --check-config validation"
```

> **After this task, skip to Task 7.** Tasks 5 and 6 are Direction 1 and are deferred.

---

### Task 5: Create the `ml/train/` package and move the training scripts

> **DEFERRED — do not run in this pass.** Direction 1 only.

**Files:**
- Create: `ml/train/__init__.py` (empty)
- Move: `ml/train_detector.py` → `ml/train/train_detector.py`
- Move: `ml/export_tflite.py` → `ml/train/export_tflite.py`
- Move: `ml/benchmark_tflite.py` → `ml/train/benchmark_tflite.py`
- Test: `ml/tests/test_train_package.py`

**Interfaces:**
- Produces: importable modules `ml.train.train_detector`, `ml.train.export_tflite`, `ml.train.benchmark_tflite`, each exposing `build_arg_parser() -> argparse.ArgumentParser` (added in Task 6) and `main()`.

**Note:** these three scripts import `ultralytics` / `tensorflow` at module top today. Moving them must not make `ml/tests/` fail to collect, so the test below only checks the files exist at their new paths and that the old paths are gone — it does NOT import them (those heavy deps are not installed).

- [ ] **Step 1: Write the failing test**

`ml/tests/test_train_package.py`:
```python
from pathlib import Path


def test_train_package_exists():
    assert Path("ml/train/__init__.py").is_file()


def test_training_scripts_moved_into_package():
    for name in ("train_detector.py", "export_tflite.py", "benchmark_tflite.py"):
        assert Path("ml/train") .joinpath(name).is_file(), f"missing ml/train/{name}"


def test_old_script_locations_are_gone():
    for name in ("train_detector.py", "export_tflite.py", "benchmark_tflite.py"):
        assert not Path("ml").joinpath(name).exists(), f"ml/{name} should have moved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_train_package.py -v`
Expected: FAIL — `ml/train/__init__.py` does not exist.

- [ ] **Step 3: Create the package and move the scripts**

```bash
mkdir -p ml/train
touch ml/train/__init__.py
git mv ml/train_detector.py ml/train/train_detector.py
git mv ml/export_tflite.py ml/train/export_tflite.py
git mv ml/benchmark_tflite.py ml/train/benchmark_tflite.py
```

- [ ] **Step 4: Update the usage lines in each moved script's docstring**

In `ml/train/train_detector.py`, change the `Usage:` line to:
```
    python -m ml.train.train_detector --data ml/datasets/<version>/data.yaml
```
In `ml/train/export_tflite.py`:
```
    python -m ml.train.export_tflite --weights runs/detect/train/weights/best.pt
```
In `ml/train/benchmark_tflite.py`:
```
    python -m ml.train.benchmark_tflite --model best_int8.tflite --runs 50
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_train_package.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest ml/tests/ -v`
Expected: 57 passed, 1 skipped.

- [ ] **Step 7: Commit**

```bash
git add ml/train ml/tests/test_train_package.py
git commit -m "refactor(ml): move training scripts into ml/train package"
```

---

### Task 6: Dataset download + config-driven training defaults (Direction 1)

> **DEFERRED — do not run in this pass.** Direction 1 only.

**Files:**
- Create: `ml/train/download_dataset.py`
- Modify: `ml/train/train_detector.py`, `ml/train/export_tflite.py`
- Modify: `ml/requirements.txt` (add `roboflow`)
- Test: `ml/tests/test_train_config_defaults.py`

**Interfaces:**
- Consumes: `config.load()` (Task 1), sections `[dataset]`, `[train]`, `[export]`.
- Produces: `ml.train.download_dataset.build_arg_parser()` and `main(argv=None) -> int`; `ml.train.train_detector.build_arg_parser()`; `ml.train.export_tflite.build_arg_parser()` — each with defaults pulled from the central config so `--flags` remain optional overrides.

- [ ] **Step 1: Add the dependency**

Append `roboflow` to `ml/requirements.txt`. Resulting file:
```
ultralytics>=8.3.0
tensorflow>=2.15.0
numpy
requests
opencv-python
roboflow
```
Do NOT `pip install` it now — it is imported lazily and the tests below never import it.

- [ ] **Step 2: Write the failing test**

`ml/tests/test_train_config_defaults.py` (imports only the parser builders, which must not require ultralytics/roboflow at import time — see Step 4's lazy-import requirement):
```python
from ml.train import download_dataset


def test_download_defaults_come_from_config(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[dataset]\nworkspace = "ws-x"\nproject = "proj-y"\n'
        'version = 7\nformat = "yolov8"\nout_dir = "some/dir"\n',
        encoding="utf-8",
    )
    args = download_dataset.build_arg_parser(str(cfg_file)).parse_args([])
    assert args.workspace == "ws-x"
    assert args.project == "proj-y"
    assert args.version == 7
    assert args.format == "yolov8"
    assert args.out_dir == "some/dir"


def test_download_flags_override_config(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[dataset]\nversion = 7\n', encoding="utf-8")
    args = download_dataset.build_arg_parser(str(cfg_file)).parse_args(["--version", "9"])
    assert args.version == 9


def test_download_main_errors_without_api_key(tmp_path, capsys):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[roboflow]\napi_key = ""\n', encoding="utf-8")
    rc = download_dataset.main(["--config", str(cfg_file)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "api_key" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest ml/tests/test_train_config_defaults.py -v`
Expected: FAIL with `ImportError: cannot import name 'download_dataset' from 'ml.train'`

- [ ] **Step 4: Write the download script**

`ml/train/download_dataset.py`:
```python
"""Direction 1 - download the Roboflow DATASET so you can train locally.

Roboflow's free tier does not let you download the trained WEIGHTS of a model
trained on their platform - but the dataset is downloadable. Pull it here, train
with train_detector.py, and you own the .pt outright. That is the only path that
continues on to TFLite / on-chip deployment.

Reads defaults from the central config ([dataset] + [roboflow].api_key).

Usage:
    python -m ml.train.download_dataset                  # all defaults from ml/config.toml
    python -m ml.train.download_dataset --version 3 --format yolov11
"""

import argparse
import sys

from ml.infer import config as config_mod


def build_arg_parser(config_path=None):
    cfg = config_mod.load(config_path)
    ds = cfg.section("dataset")
    p = argparse.ArgumentParser(
        prog="python -m ml.train.download_dataset",
        description="Download the Roboflow dataset for local training.",
    )
    p.add_argument("--config", default=config_path,
                   help="Path to config.toml (default: ml/config.toml)")
    p.add_argument("--workspace", default=ds.get("workspace"))
    p.add_argument("--project", default=ds.get("project"))
    p.add_argument("--version", type=int, default=ds.get("version"))
    p.add_argument("--format", default=ds.get("format"),
                   help="Roboflow export format, e.g. yolov11 / yolov8")
    p.add_argument("--out-dir", default=ds.get("out_dir"))
    return p


def main(argv=None):
    # Two-pass parse: read --config first so the real defaults come from that file.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    known, _ = pre.parse_known_args(argv)

    args = build_arg_parser(known.config).parse_args(argv)
    cfg = config_mod.load(known.config)

    api_key = cfg.get("roboflow", "api_key")
    if not api_key:
        print("[error] roboflow.api_key is not set - put it in ml/config.local.toml "
              "or set AQUA_ROBOFLOW_API_KEY (never commit it).")
        return 1

    from roboflow import Roboflow  # lazy: heavy/optional dependency

    rf = Roboflow(api_key=api_key)
    project = rf.workspace(args.workspace).project(args.project)
    dataset = project.version(args.version).download(args.format, location=args.out_dir)
    location = getattr(dataset, "location", args.out_dir)
    print(f"Downloaded to: {location}")
    print(f"Next: python -m ml.train.train_detector --data {location}/data.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Make the training scripts read the config**

In `ml/train/train_detector.py`, replace the body of `main()`'s argument setup with a config-backed `build_arg_parser`. The file becomes:
```python
"""Train a compact object detector on a Roboflow-exported (YOLO format) dataset.

Direction 1 - you own the resulting .pt, which is what makes TFLite/on-chip export
possible. Defaults come from ml/config.toml [train]; flags override them.

Usage:
    python -m ml.train.train_detector --data ml/datasets/<version>/data.yaml
"""
import argparse
import sys

from ml.infer import config as config_mod


def build_arg_parser(config_path=None):
    cfg = config_mod.load(config_path)
    tr = cfg.section("train")
    p = argparse.ArgumentParser(
        prog="python -m ml.train.train_detector", description=__doc__)
    p.add_argument("--config", default=config_path)
    p.add_argument("--data", required=True, help="Path to Roboflow-exported data.yaml")
    p.add_argument("--model", default=tr.get("base_model"),
                   help="Base checkpoint to fine-tune from")
    p.add_argument("--epochs", type=int, default=tr.get("epochs"))
    p.add_argument("--imgsz", type=int, default=tr.get("imgsz"))
    p.add_argument("--batch", type=int, default=tr.get("batch"))
    return p


def main(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    known, _ = pre.parse_known_args(argv)
    args = build_arg_parser(known.config).parse_args(argv)

    from ultralytics import YOLO  # lazy: heavy/optional dependency

    model = YOLO(args.model)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch)
    metrics = model.val(data=args.data, split="test")
    print("Test-split metrics:", metrics.results_dict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

In `ml/train/export_tflite.py`, apply the same pattern:
```python
"""Export a trained Ultralytics detector to an int8-quantized TFLite model.

Direction 1 only - a hosted-API model (Direction 2) cannot be exported. Defaults
come from ml/config.toml [export]; flags override them.

Usage:
    python -m ml.train.export_tflite --weights runs/detect/train/weights/best.pt \
        --data ml/datasets/<version>/data.yaml
"""
import argparse
import sys

from ml.infer import config as config_mod


def build_arg_parser(config_path=None):
    cfg = config_mod.load(config_path)
    ex = cfg.section("export")
    p = argparse.ArgumentParser(
        prog="python -m ml.train.export_tflite", description=__doc__)
    p.add_argument("--config", default=config_path)
    p.add_argument("--weights", required=True, help="Path to trained .pt weights")
    p.add_argument("--imgsz", type=int, default=ex.get("tflite_imgsz"),
                   help="Lowest resolution that still resolves ~2mm particles")
    p.add_argument("--data", required=True,
                   help="data.yaml used to build the int8 representative dataset")
    p.add_argument("--int8", action="store_true", default=ex.get("int8"))
    return p


def main(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    known, _ = pre.parse_known_args(argv)
    args = build_arg_parser(known.config).parse_args(argv)

    from ultralytics import YOLO  # lazy: heavy/optional dependency

    model = YOLO(args.weights)
    exported_path = model.export(format="tflite", int8=args.int8,
                                 imgsz=args.imgsz, data=args.data)
    print(f"Exported int8 TFLite model to: {exported_path}")
    print(f"Next: python -m ml.train.benchmark_tflite --model {exported_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> Leave `ml/train/benchmark_tflite.py` alone apart from its `Usage:` line (Task 5) — it has no config-worthy settings beyond `--model` and `--runs`.

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest ml/tests/test_train_config_defaults.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest ml/tests/ -v`
Expected: 60 passed, 1 skipped.

- [ ] **Step 8: Commit**

```bash
git add ml/train ml/requirements.txt ml/tests/test_train_config_defaults.py
git commit -m "feat(ml): dataset download + config-driven training defaults"
```

---

### Task 7: Documentation + full sweep

**Files:**
- Modify: `ml/README.md`

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest ml/tests/ -v`
Expected: 65 passed, 1 skipped (`test_detector_smoke.py` still skips — no weights). Tasks 5 and 6 are deferred, so their tests do not exist yet.

- [ ] **Step 2: Document both directions and the config**

Replace the existing "Nhánh 1 — chạy inference trên PC (offload)" section of `ml/README.md` with the following (it supersedes it — the CLI now covers both backends):

````markdown
## Hai hướng model (2 backend, cùng một pipeline)

Cùng dùng chung `ml/infer/` (source → detector → mapper → ingest). Chỉ khác ở
tầng detector, chọn bằng `--backend`:

| | Hướng 1 — `local` | Hướng 2 — `roboflow` |
|---|---|---|
| Trạng thái | Chưa làm (hoãn) | **Đã làm xong** |
| Weights local | Cần (tự train ra) | Không cần |
| Mạng khi chạy | Không | Có (+ API key) |
| Xuống chip (TFLite) | **Được** | Không |
| Chạy được ngay | Sau khi train | Ngay |

### Cấu hình tập trung

Mọi thiết lập nằm ở **`ml/config.toml`** (được commit, tài liệu hoá đầy đủ mọi
khoá — mở file này ra là biết cần cấu hình gì).

Thứ tự ưu tiên: `cờ CLI` > `biến môi trường` > `ml/config.local.toml` > `ml/config.toml` > mặc định trong code.

API key **không bao giờ** để trong `config.toml`. Tạo `ml/config.local.toml` (đã gitignore):
```toml
[roboflow]
api_key = "rf_xxxxxxxx"
workspace = "<workspace-slug>"
workflow_id = "<workflow-slug>"
```
Hoặc dùng biến môi trường: `AQUA_ROBOFLOW_API_KEY`, `AQUA_ROBOFLOW_WORKSPACE`, `AQUA_INGEST_API_URL`, ...

Kiểm tra cấu hình đã đủ chưa (không chạy inference, **không in ra API key**):
```bash
python -m ml.infer --check-config
python -m ml.infer --check-config --backend roboflow
```

### Hướng 2 — Roboflow Workflow API (đã làm xong)

```bash
python -m ml.infer <ảnh|thư mục> --backend roboflow --px-per-mm <n>
```
Không cần weights, không cần ultralytics. Cần mạng + `roboflow.api_key` + `workspace` + `workflow_id`.

**Bước bắt buộc lần đầu — dò tên output của workflow.** Response của Workflow API là
một *list*, mỗi phần tử là dict khoá theo **tên output do chính workflow đặt** (không có
khoá `predictions` cố định). Chạy lệnh probe một lần để xem cấu trúc thật (chỉ in tên
khoá + kiểu, **không in blob base64**):
```bash
python -m ml.infer.probe path/to/anh.jpg
```
Rồi điền tên khoá vừa thấy vào `roboflow.predictions_key` trong `ml/config.toml`
(hỗ trợ đường dẫn có dấu chấm, vd `model_predictions.predictions`). Để trống thì
code sẽ **tự dò** — probe sẽ cho biết tự dò có ra hay không.

### Hướng 1 — tự train (CHƯA LÀM)

Roboflow bản miễn phí **không cho tải weights** đã train trên nền tảng họ, nhưng
**cho tải dataset**. Hướng này tải dataset về, tự train, sở hữu luôn `.pt` — và là
đường **duy nhất** đi tiếp xuống chip (TFLite).

Phần này chưa triển khai (Task 5 + 6 trong plan, đang hoãn). Backend `local` trong
CLI đã sẵn sàng nhận `ml/models/best.pt` khi có weights.

### Ghi chú chung

- `--px-per-mm` bỏ trống → dùng mặc định 14.0 **kèm cảnh báo**: `size_mm` chỉ là
  placeholder, không phải hiệu chuẩn thật (với ảnh dataset công khai thì đúng là vậy).
- `--dry-run`: chỉ detect + in số hạt, không POST.
- Chạy lại cùng thư mục là idempotent (sample_code suy từ tên file) → server trả `already_exists`.
- Hai file khác nhau ra cùng `sample_code` (vd `a.jpg` và `a.png`) sẽ bị báo
  `[warn] collision` và **không gửi** — đổi tên file rồi chạy lại.

Preview trực quan (chỉ backend `local`, KHÔNG ghi DB):
```bash
python -m ml.infer.preview --source webcam:0 --weights ml/models/best.pt --fps 2
```
Preview cố ý không dùng backend `roboflow`: gọi API mỗi khung hình sẽ rất tốn và dễ đụng rate limit.
````

- [ ] **Step 3: Commit**

```bash
git add ml/README.md
git commit -m "docs(ml): document both backends + central config"
```

---

## Notes for the implementer

- `ml/models/`, `ml/datasets/`, `ml/runs/`, `*.pt`, `*.tflite` and `ml/config.local.toml` are gitignored — local only.
- Do not install `ultralytics`, `tensorflow`, or `roboflow` to make tests pass. Every test in this plan runs without them; the heavy deps are imported lazily inside functions.
- The detector smoke test (`test_detector_smoke.py`) skipping is the expected, correct state until real weights exist at `ml/models/best.pt`.
- If `python -m ml.infer` cannot find the `ml` package, confirm you are running from the repo root (`C:\University\Semester 4\IOT102\project`).
- End-to-end verification against a live backend and a real trained model is a manual step (needs `ml/models/best.pt` or a real Roboflow key) — do not fabricate its results.
