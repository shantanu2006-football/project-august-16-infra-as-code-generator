import pytest

from iacgen.validators import ValidationError, validate_hcl, validate_yaml


def test_validate_yaml_accepts_valid_document():
    result = validate_yaml("a: 1\nb:\n  - 2\n  - 3\n")
    assert result == {"a": 1, "b": [2, 3]}


def test_validate_yaml_rejects_broken_document():
    with pytest.raises(ValidationError):
        validate_yaml("a: [1, 2\nb: broken")


def test_validate_hcl_accepts_valid_document():
    result = validate_hcl('variable "x" {\n  default = 1\n}\n')
    assert "variable" in result


def test_validate_hcl_rejects_broken_document():
    with pytest.raises(ValidationError):
        validate_hcl("resource aws_s3_bucket {{{ not hcl")
