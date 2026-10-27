"""Validate configuration bodies before they can reach PostgreSQL."""

import pytest
from app.features.detection_configurations.create_configuration.request import CreateConfigurationRequest
from app.features.detection_configurations.list_configurations.request import ListConfigurationsRequest
from app.features.detection_configurations.update_configuration.request import UpdateConfigurationRequest
from pydantic import ValidationError


def test_create_trims_identifiers_and_preserves_nested_json() -> None:
    parameters = {"window_s": 10, "enabled": True, "services": [22, 3389], "nested": {"optional": None}, "ratio": 1.5}
    request = CreateConfigurationRequest(detection_type=" port_scan ", method=" rule ", parameters=parameters)
    assert request.detection_type == "port_scan"
    assert request.method == "rule"
    assert request.parameters == parameters


@pytest.mark.parametrize("field", ["detection_type", "method", "parameters"])
def test_create_requires_every_field(field) -> None:
    body = {"detection_type": "port_scan", "method": "rule", "parameters": {}}
    del body[field]
    with pytest.raises(ValidationError):
        CreateConfigurationRequest.model_validate(body)


@pytest.mark.parametrize("model", [CreateConfigurationRequest, UpdateConfigurationRequest])
@pytest.mark.parametrize("field", ["detection_type", "method"])
@pytest.mark.parametrize("value", [None, "", " \t\n", "x" * 129, "bad\x00value", "bad\ud800value", 123])
def test_write_requests_reject_invalid_identifiers(model, field, value) -> None:
    body = {"detection_type": "port_scan", "method": "rule", "parameters": {}, field: value}
    with pytest.raises(ValidationError) as error:
        model.model_validate(body)
    assert any(entry["loc"][0] == field for entry in error.value.errors())


@pytest.mark.parametrize("model", [CreateConfigurationRequest, UpdateConfigurationRequest])
@pytest.mark.parametrize(
    "parameters",
    [
        None,
        [],
        "text",
        1,
        True,
        {"value": float("nan")},
        {"nested": [float("inf")]},
        {"bad\x00key": 1},
        {"nested": ["bad\x00value"]},
        {"nested": {"value": "bad\udfffvalue"}},
    ],
)
def test_write_requests_reject_values_not_storable_as_jsonb(model, parameters) -> None:
    with pytest.raises(ValidationError) as error:
        model(detection_type="port_scan", method="rule", parameters=parameters)
    assert any(entry["loc"][0] == "parameters" for entry in error.value.errors())


@pytest.mark.parametrize("model", [CreateConfigurationRequest, UpdateConfigurationRequest])
@pytest.mark.parametrize("extra", [{"active": True}, {"configuration_id": "ignored"}, {"unknown": "value"}])
def test_write_requests_reject_unowned_fields(model, extra) -> None:
    with pytest.raises(ValidationError):
        model(detection_type="port_scan", method="rule", parameters={}, **extra)


def test_patch_only_changes_explicitly_supplied_fields() -> None:
    assert UpdateConfigurationRequest(method="statistical").model_dump(exclude_unset=True) == {"method": "statistical"}
    assert UpdateConfigurationRequest(parameters={}).model_dump(exclude_unset=True) == {"parameters": {}}
    with pytest.raises(ValidationError):
        UpdateConfigurationRequest()


@pytest.mark.parametrize(
    "query",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"active": "invalid"},
        {"sort_order": "invalid"},
        {"detection_type": " "},
        {"method": " "},
    ],
)
def test_list_rejects_invalid_filters_and_bounds(query) -> None:
    with pytest.raises(ValidationError):
        ListConfigurationsRequest.model_validate(query)
