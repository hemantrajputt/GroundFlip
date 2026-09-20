import json

from groundflip.demo import procurement_scenario
from groundflip.providers.openai import OpenAIProvider


class FakeUsage:
    input_tokens = 10
    output_tokens = 4
    total_tokens = 14


class FakeResponse:
    id = "resp_test"
    usage = FakeUsage()
    output_text = json.dumps(
        {
            "decision": "APPROVE",
            "vendor": "Nimbus Analytics",
            "amount": 95000,
            "risk_score": 32,
            "policy_version": "POL-2026-08",
            "rationale": "Evidence meets policy.",
        }
    )


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_openai_adapter_uses_responses_structured_output_without_persisting():
    client = FakeClient()
    provider = OpenAIProvider(model="test-model", client=client)
    output = provider.synthesize(procurement_scenario(), seed=3, branch="control")
    assert output.data["decision"] == "APPROVE"
    assert output.usage["total_tokens"] == 14
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["text"]["format"]["type"] == "json_schema"
    assert "OPENAI_API_KEY" not in str(client.responses.kwargs)
