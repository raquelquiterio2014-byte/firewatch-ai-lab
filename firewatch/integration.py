"""Provider-only probe, separate from fire analysis and synthetic evaluation."""
from .gateway import GeminiGateway, GatewayError
from .models import ConnectionProbe, LLMCallRecord


def check_gemini(model=None, store=None):
    gateway = None
    try:
        gateway = GeminiGateway(model=model)
        gateway.call("ConnectionProbe", ConnectionProbe, {"configuration_probe": True, "incident_data_included": False})
        record = gateway.last_call.model_copy(deep=True)
    except Exception as exc:
        code = exc.code if isinstance(exc, GatewayError) else "CALL_OR_VALIDATION_FAILED"
        if gateway is not None and gateway.last_call is not None:
            record = gateway.last_call.model_copy(deep=True)
        else:
            record = LLMCallRecord(component="ConnectionProbe", requested_model="invalid_configuration",
                                   source="configuration", error_code=code)
    if store is not None:
        store.save_provider_check(record)
    return record
