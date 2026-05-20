import pytest
from oromscript import transpile
from oromscript.errors import OrmNameError

def test_semantic_strict_name_error():
    with pytest.raises(OrmNameError) as exc:
        transpile('y', strict=True)
    assert exc.value.code == "E0020"

def test_semantic_functions_and_classes():
    src = '''
gosa MyClass:
    hojii __init__(of):
        darbii
    yeroo_eeguu hojii my_async(of):
        darbii
'''
    py_src = transpile(src, lang="afan_oromo")
    assert "class MyClass:" in py_src
    assert "def __init__(self):" in py_src
    assert "async def my_async(self):" in py_src
