import pytest

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


def test_extra_inputs_table_loads_from_toml(tmp_path):
    _write(tmp_path / "config.toml",
           '[roboflow.extra_inputs]\nmodel_id = "proj/3"\nconfidence = 0.6\n')
    cfg = cfgmod.load(tmp_path / "config.toml", env={})
    assert cfg.get("roboflow", "extra_inputs") == {"model_id": "proj/3",
                                                   "confidence": 0.6}


def test_extra_inputs_defaults_to_empty_dict(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml", env={})
    assert cfg.get("roboflow", "extra_inputs") == {}


def test_extra_inputs_env_var_is_json(tmp_path):
    cfg = cfgmod.load(
        tmp_path / "missing.toml",
        env={"AQUA_ROBOFLOW_EXTRA_INPUTS": '{"model_id": "proj/4"}'},
    )
    assert cfg.get("roboflow", "extra_inputs") == {"model_id": "proj/4"}


def test_extra_inputs_env_var_rejects_non_object(tmp_path):
    with pytest.raises(ValueError, match="must be a JSON object"):
        cfgmod.load(tmp_path / "missing.toml",
                    env={"AQUA_ROBOFLOW_EXTRA_INPUTS": '["a"]'})


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


def test_env_coerces_none_default_px_per_mm_to_float(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml",
                      env={"AQUA_CALIBRATION_PX_PER_MM": "14.0"})
    assert cfg.get("calibration", "px_per_mm") == 14.0
    assert isinstance(cfg.get("calibration", "px_per_mm"), float)


def test_env_leaves_batch_lot_as_string(tmp_path):
    cfg = cfgmod.load(tmp_path / "missing.toml",
                      env={"AQUA_INGEST_BATCH_LOT": "123"})
    assert cfg.get("ingest", "batch_lot") == "123"
    assert isinstance(cfg.get("ingest", "batch_lot"), str)


def test_station_defaults_present():
    cfg = cfgmod.load(config_path="ml/config.toml", env={})
    assert cfg.get("station", "timeout_s") == 20
    assert cfg.get("station", "retries") == 3
    assert cfg.get("station", "interval_s") == 2.0


def test_missing_for_station_flags_empty_host():
    cfg = cfgmod.Config({"station": {"host": ""}})
    problems = cfg.missing_for("station")
    assert len(problems) == 1
    assert "station.host" in problems[0]


def test_missing_for_station_ok_when_host_set():
    cfg = cfgmod.Config({"station": {"host": "192.168.1.50"}})
    assert cfg.missing_for("station") == []
