import json


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"
