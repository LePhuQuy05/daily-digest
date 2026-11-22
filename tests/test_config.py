import subprocess
import sys

import yaml

from daily_digest.config import Config, ConfigError, load_config, redacted_config_dict
from daily_digest.util import load_env_file


def test_defaults_without_any_file(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    assert config.llm.model == "deepseek-v4.1-flash"
    assert config.llm.base_url == "https://opencode.ai/inference/go"
    assert config.sources.arxiv.categories == [
        "cs.CL",
        "cs.LG",
        "cs.AI",
        "stat.ML",
        "cs.RO",
        "cs.SE",
        "cs.CR",
    ]
    assert config.sources.arxiv.max_per_category == 30
    assert config.sources.arxiv.filter_categories == [
        "stat.ML",
        "cs.RO",
        "cs.SE",
        "cs.CR",
    ]
    assert config.template_path.exists()
    assert config.state_path.name == "state.json"


def test_yaml_override(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "llm:\n  model: kimi-k3\n  top_n: 5\nsources:\n  hn:\n    min_points: 100\nschedule:\n  time: '07:30'\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.llm.model == "kimi-k3"
    assert config.llm.top_n == 5
    assert config.sources.hn.min_points == 100
    assert config.schedule.time == "07:30"


def test_digest_size_config_is_clamped_not_fatal(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("llm:\n  top_n: 31\n", encoding="utf-8")
    assert load_config(path).llm.top_n == 30

    path.write_text("llm:\n  top_n: 0\n", encoding="utf-8")
    assert load_config(path).llm.top_n == 1

    path.write_text("llm:\n  top_n: 5\n  max_pool: 3\n", encoding="utf-8")
    assert load_config(path).llm.top_n == 3

    path.write_text("llm:\n  top_n: '12'\n", encoding="utf-8")
    assert load_config(path).llm.top_n == 12


def test_redacted_config_reports_effective_digest_size(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    data = redacted_config_dict(config)
    assert data["digest_size"]["config"] == 12
    assert data["digest_size"]["effective"] >= 1


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("bogus_top: 1\nllm:\n  not_a_key: 2\n", encoding="utf-8")
    config = load_config(path)  # must not raise
    assert config.llm.model == "deepseek-v4.1-flash"


def test_env_model_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DIGEST_LLM_MODEL", "glm-5.3-flash")
    config = load_config(tmp_path / "missing.yaml")
    assert config.llm.model == "glm-5.3-flash"


def test_invalid_schedule_time_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("schedule:\n  time: 9am\n", encoding="utf-8")
    try:
        load_config(path)
        raise AssertionError("expected ConfigError")
    except ConfigError:
        pass


def test_env_file_parser(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment line\nDIGEST_TEST_A=plain\nDIGEST_TEST_B=\"quoted value\"\nDIGEST_TEST_C='single'\n\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DIGEST_TEST_A", raising=False)
    monkeypatch.setenv("DIGEST_TEST_D", "already-set")
    (tmp_path / ".env2").write_text("DIGEST_TEST_D=from-file\n", encoding="utf-8")

    parsed = load_env_file(env_file)
    assert parsed == {
        "DIGEST_TEST_A": "plain",
        "DIGEST_TEST_B": "quoted value",
        "DIGEST_TEST_C": "single",
    }
    assert load_env_file(tmp_path / ".env2") == {"DIGEST_TEST_D": "from-file"}
    import os

    assert os.environ["DIGEST_TEST_D"] == "already-set"  # real env wins over .env


def test_redacted_config_is_yaml_safe_and_hides_secret(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    data = redacted_config_dict(config)
    assert data["llm"]["api_key"] in ("set", "not set")
    assert isinstance(data["output_dir"], str)  # Path objects stringified
    dumped = yaml.safe_dump(data)  # must not raise
    assert "oc_sk" not in dumped  # never a raw key in output


def test_config_dataclass_defaults_are_independent():
    a, b = Config(), Config()
    a.sources.arxiv.categories.append("cs.CV")
    assert b.sources.arxiv.categories == [
        "cs.CL",
        "cs.LG",
        "cs.AI",
        "stat.ML",
        "cs.RO",
        "cs.SE",
        "cs.CR",
    ]  # no shared mutable state


def test_cli_print_config_works_from_any_cwd():
    """CWD independence: the scheduled task runs with cwd=System32; config must still resolve."""
    proc = subprocess.run(
        [sys.executable, "-m", "daily_digest", "print-config"],
        cwd="C:\\Windows\\System32",
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "deepseek-v4.1-flash" in proc.stdout
    assert "model:" in proc.stdout
