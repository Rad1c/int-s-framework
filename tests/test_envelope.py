from integration_framework.envelope import envelope, error, ok


def test_ok():
    assert ok({"data": 1}) == {"success": 0, "payload": {"data": 1}, "error_message": ""}


def test_ok_default_payload():
    assert ok() == {"success": 0, "payload": {}, "error_message": ""}


def test_error():
    assert error("boom") == {"success": 1, "payload": {}, "error_message": "boom"}


def test_envelope_from_handler_result():
    assert envelope(True, {"data": 1}, "") == {"success": 0, "payload": {"data": 1}, "error_message": ""}
    assert envelope(False, None, "bad") == {"success": 1, "payload": {}, "error_message": "bad"}
