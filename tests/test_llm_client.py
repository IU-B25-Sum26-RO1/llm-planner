import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "decomposer"))

from decomposer.llm_client import LLMClient  # noqa: E402


class APIException(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def test_response_format_fallback_is_limited_to_relevant_client_errors():
    unsupported = APIException("response_format json_object is unsupported", 400)
    network_failure = APIException("connection failed", 503)
    unrelated_bad_request = APIException("model does not exist", 400)

    assert LLMClient._is_response_format_unsupported(unsupported)
    assert not LLMClient._is_response_format_unsupported(network_failure)
    assert not LLMClient._is_response_format_unsupported(unrelated_bad_request)
