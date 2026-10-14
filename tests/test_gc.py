"""Tests for the cycle collector pause used by the lexer and parser."""

from __future__ import annotations

import gc
import threading

import pytest

from oromscript import transpile
from oromscript._gc import gc_paused
from oromscript.lexer import OrmLexer
from oromscript.parser import OrmParser


@pytest.fixture(autouse=True)
def restore_gc():
    was = gc.isenabled()
    yield
    gc.enable() if was else gc.disable()


def test_collector_is_off_inside_the_block():
    gc.enable()
    with gc_paused():
        assert not gc.isenabled()


def test_collector_comes_back_afterwards():
    gc.enable()
    with gc_paused():
        pass
    assert gc.isenabled()


def test_collector_stays_off_if_it_was_off():
    gc.disable()
    with gc_paused():
        assert not gc.isenabled()
    assert not gc.isenabled()


def test_collector_comes_back_after_an_error():
    gc.enable()
    with pytest.raises(RuntimeError), gc_paused():
        raise RuntimeError("boom")
    assert gc.isenabled()


def test_nested_blocks_restore_the_outer_state():
    gc.enable()
    with gc_paused():
        with gc_paused():
            assert not gc.isenabled()
        assert not gc.isenabled()
    assert gc.isenabled()


def test_lexer_and_parser_restore_the_collector(oromo_adapter):
    gc.enable()
    tokens = OrmLexer("x = 1\n", oromo_adapter).tokenize()
    assert gc.isenabled()
    OrmParser(oromo_adapter).parse(tokens)
    assert gc.isenabled()


def test_collector_comes_back_after_a_lexer_or_parser_error(oromo_adapter):
    gc.enable()
    with pytest.raises(Exception):  # noqa: B017, PT011
        OrmLexer("x = $\n", oromo_adapter).tokenize()
    assert gc.isenabled()
    tokens = OrmLexer("x = = 1\n", oromo_adapter).tokenize()
    with pytest.raises(Exception):  # noqa: B017, PT011
        OrmParser(oromo_adapter).parse(tokens)
    assert gc.isenabled()


def test_user_setting_is_respected_by_transpile():
    gc.disable()
    transpile("x = 1\n")
    assert not gc.isenabled()


def test_threads_leave_the_collector_on():
    gc.enable()

    def work() -> None:
        for _ in range(100):
            transpile("x = [i for i in range(3)]\n")

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert gc.isenabled()
