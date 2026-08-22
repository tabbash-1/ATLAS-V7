# ATLAS AI server layer

ATLAS keeps `collector_server.py` unchanged and starts through `atlas_ai_server.py`, which subclasses the existing HTTP handler and preserves every legacy route.

## AI route

`POST /api/ai/analyze`

- Accepts only `ATLAS_AI_ANALYSIS_PACKET_V1` packets.
- Same-origin requests only.
- Payload size limited by `ATLAS_AI_MAX_BODY` (default 700 KB).
- Uses the OpenAI Responses API when `OPENAI_API_KEY` is configured.
- Model defaults to `gpt-5.6-terra` and can be changed with `ATLAS_AI_MODEL`.
- Returns research-only JSON; live execution remains disabled.
- Browser automatically falls back to the deterministic ATLAS thesis if the AI gateway is unavailable.

## Required environment variable

`OPENAI_API_KEY`

Optional:

- `ATLAS_AI_MODEL`
- `ATLAS_AI_MAX_BODY`

The API key is never sent to the browser.
