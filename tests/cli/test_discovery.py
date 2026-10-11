"""Tests for cross-platform auto-discovery: config dirs, validators, and search.

The per-OS branches are exercised on any host by monkeypatching `os.name`,
`sys.platform`, and `HOME`, so Linux/macOS/Windows behavior is verified here
rather than only on the OS that happens to run CI.
"""

from pathlib import Path

from cli import discovery


def _make_codex_home(base) -> None:
    """Create a Codex home with one rollout file under base."""
    rollout = base / "sessions" / "2026" / "10" / "12" / "rollout-2026-10-12.jsonl"
    rollout.parent.mkdir(parents=True, exist_ok=True)
    rollout.write_text("{}\n", encoding="utf-8")


def _make_claude_home(base) -> None:
    session = base / "projects" / "-home-me" / "session.jsonl"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text("{}\n", encoding="utf-8")


# --- config directory, per OS (pure, so every host can verify all three) ---


def test_config_dir_on_windows() -> None:
    env = {"APPDATA": "C:/Users/me/AppData/Roaming"}
    assert discovery.config_dir_for("nt", "win32", env, Path("/home/me")) == Path(
        "C:/Users/me/AppData/Roaming/tokenly"
    )


def test_config_dir_on_windows_without_appdata() -> None:
    assert discovery.config_dir_for("nt", "win32", {}, Path("/home/me")) == Path(
        "/home/me/AppData/Roaming/tokenly"
    )


def test_config_dir_on_macos() -> None:
    assert discovery.config_dir_for("posix", "darwin", {}, Path("/home/me")) == Path(
        "/home/me/Library/Application Support/tokenly"
    )


def test_config_dir_on_linux_uses_xdg() -> None:
    env = {"XDG_CONFIG_HOME": "/xdg"}
    assert discovery.config_dir_for("posix", "linux", env, Path("/home/me")) == Path(
        "/xdg/tokenly"
    )


def test_config_dir_on_linux_falls_back_to_dot_config() -> None:
    assert discovery.config_dir_for("posix", "linux", {}, Path("/home/me")) == Path(
        "/home/me/.config/tokenly"
    )


# --- config round-trip ---


def test_config_round_trip(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    monkeypatch.setattr(discovery, "config_path", lambda: tmp_path / "config.json")
    discovery.save_config(discovery.DiscoveredPaths(codex_home=Path("/x/codex")))
    assert discovery.load_config() == {"codex_home": "/x/codex"}


def test_missing_config_loads_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(discovery, "config_path", lambda: tmp_path / "nope.json")
    assert discovery.load_config() == {}


def test_corrupt_config_loads_empty(monkeypatch, tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(discovery, "config_path", lambda: path)
    assert discovery.load_config() == {}


# --- validators & probes ---


def test_codex_probe_returns_the_home_above_sessions(tmp_path) -> None:
    _make_codex_home(tmp_path)
    assert discovery._probe_codex(tmp_path / "sessions") == tmp_path


def test_claude_probe_returns_the_home_above_projects(tmp_path) -> None:
    _make_claude_home(tmp_path)
    assert discovery._probe_claude(tmp_path / "projects") == tmp_path


def test_validators_reject_empty_directories(tmp_path) -> None:
    assert discovery._valid_codex(tmp_path) is False
    assert discovery._valid_claude(tmp_path) is False
    assert discovery._valid_cline(tmp_path) is False
    assert discovery._valid_opencode(tmp_path) is False


def test_opencode_probe_detects_the_database(tmp_path) -> None:
    (tmp_path / "opencode.db").write_text("", encoding="utf-8")
    assert discovery._probe_opencode(tmp_path) == tmp_path


# --- bounded search ---


def test_search_finds_a_non_default_codex_home(monkeypatch, tmp_path) -> None:
    _make_codex_home(tmp_path / "work" / "my-codex")
    monkeypatch.setattr(discovery, "_search_roots", lambda: [tmp_path])
    found = discovery._search(discovery._probe_codex)
    assert found == tmp_path / "work" / "my-codex"


def test_search_skips_noisy_directories(monkeypatch, tmp_path) -> None:
    _make_codex_home(tmp_path / "node_modules")
    monkeypatch.setattr(discovery, "_search_roots", lambda: [tmp_path])
    assert discovery._search(discovery._probe_codex) is None


def test_search_respects_the_depth_cap(monkeypatch, tmp_path) -> None:
    deep = tmp_path
    for level in ("d1", "d2", "d3", "d4", "d5", "d6", "d7"):
        deep = deep / level
    _make_codex_home(deep)  # `sessions` sits below MAX_DEPTH
    monkeypatch.setattr(discovery, "_search_roots", lambda: [tmp_path])
    assert discovery._search(discovery._probe_codex) is None


# --- end-to-end per-platform discovery ---


def test_codex_discovery_uses_the_environment_when_set(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "explicit"))
    found = discovery.discover_codex_home({}, force=False)
    assert found == tmp_path / "explicit"  # honoured even if currently empty


def test_codex_discovery_searches_when_default_is_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)
    _make_codex_home(tmp_path / "found" / "codex")
    monkeypatch.setattr(discovery, "codex_default", lambda: tmp_path / "does-not-exist")
    monkeypatch.setattr(discovery, "_search_roots", lambda: [tmp_path])
    assert discovery.discover_codex_home({}, force=False) == tmp_path / "found" / "codex"


def test_claude_discovery_finds_the_default_two_level_layout(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    _make_claude_home(tmp_path / ".claude")
    monkeypatch.setattr(discovery, "claude_default", lambda: tmp_path / ".claude")
    assert discovery.discover_claude_data_dir({}, force=False) == tmp_path / ".claude"
