"""
Grammar hooks for the Afan Oromo adapter.
All functions are optional. The core engine checks for their existence before calling.
"""


def pre_parse(source: str) -> str:
    """Pre-process the untokenised Python source before ast.parse().

    Args:
        source: The source string after keyword translation.

    Returns:
        Modified source string. Must still be valid Python after modification.
    """
    return source
