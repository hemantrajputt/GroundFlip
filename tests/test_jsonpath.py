import pytest

from groundflip import jsonpath
from groundflip.models import InterventionError


def test_get_set_delete_and_quoted_keys():
    value = {"rows": [{"net-value": 7}], "space key": True}
    assert jsonpath.get(value, "$.rows[0].net-value") == 7
    assert jsonpath.get(value, "$['space key']") is True
    jsonpath.set_value(value, "$.rows[0].net-value", 9)
    assert value["rows"][0]["net-value"] == 9
    jsonpath.delete(value, "$.rows[0].net-value")
    assert "net-value" not in value["rows"][0]


@pytest.mark.parametrize("path", ["rows[0]", "$..secret", "$[*]", "$[?(@.x)]", "$"])
def test_unsafe_or_root_mutation_paths_are_rejected(path):
    if path == "$":
        with pytest.raises(InterventionError):
            jsonpath.set_value({"x": 1}, path, 2)
    else:
        with pytest.raises(InterventionError):
            jsonpath.parse(path)


def test_flatten_scalars_is_stable():
    assert list(jsonpath.flatten_scalars({"b": [2], "a": 1})) == [
        ("$.a", 1),
        ("$.b[0]", 2),
    ]
