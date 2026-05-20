from oromscript import transpile


def test_hello_world_roundtrip():
    result = transpile('agarsiisi("Akkam, Addunyaa!")', lang="afan_oromo")
    assert result == "print('Akkam, Addunyaa!')"


def test_for_loop_roundtrip():
    orm = "hanga i keessa lakkoofsa(5):\n    agarsiisi(i)"
    expected = "for i in range(5):\n    print(i)"
    assert transpile(orm) == expected


def test_class_roundtrip():
    orm = "gosa Barataa:\n    darbii"
    result = transpile(orm)
    assert "class Barataa:" in result


def test_emit_map_returns_tuple():
    result = transpile('agarsiisi("x")', emit_map=True)
    assert isinstance(result, tuple)
    assert len(result) == 2
    py_src, map_json = result
    assert 'print' in py_src
    assert '"version"' in map_json


def test_deterministic_output():
    """Same input must always produce identical output."""
    src = "hanga i keessa lakkoofsa(10):\n    agarsiisi(i * 2)"
    assert transpile(src) == transpile(src)
