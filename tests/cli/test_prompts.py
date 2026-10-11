"""Tests for the numbered terminal prompt (stdlib input() only, cross-platform)."""

import builtins

from cli import prompts

OPTIONS = [("a", "Option A"), ("b", "Option B")]


def _feed(monkeypatch, responses: list[str]) -> None:
    """Make input() return each response in turn."""
    iterator = iter(responses)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(iterator))


def test_a_valid_number_returns_its_value(monkeypatch) -> None:
    _feed(monkeypatch, ["2"])
    assert prompts.choose("Pick:", OPTIONS) == "b"


def test_zero_and_blank_and_quit_all_mean_no_choice(monkeypatch) -> None:
    for response in ("0", "", "q", "quit", "exit"):
        _feed(monkeypatch, [response])
        assert prompts.choose("Pick:", OPTIONS) is None


def test_an_invalid_choice_reprompts_until_valid(monkeypatch) -> None:
    _feed(monkeypatch, ["9", "abc", "1"])
    assert prompts.choose("Pick:", OPTIONS) == "a"


def test_an_out_of_range_number_reprompts(monkeypatch) -> None:
    _feed(monkeypatch, ["3", "2"])
    assert prompts.choose("Pick:", OPTIONS) == "b"


def test_end_of_stream_exits_cleanly(monkeypatch) -> None:
    def raise_eof(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    assert prompts.choose("Pick:", OPTIONS) is None


def test_keyboard_interrupt_exits_cleanly(monkeypatch) -> None:
    def raise_interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", raise_interrupt)
    assert prompts.choose("Pick:", OPTIONS) is None


def test_no_options_returns_none_without_prompting(monkeypatch) -> None:
    def fail(_prompt: str = "") -> str:
        raise AssertionError("input() should not be called with no options")

    monkeypatch.setattr(builtins, "input", fail)
    assert prompts.choose("Pick:", []) is None
