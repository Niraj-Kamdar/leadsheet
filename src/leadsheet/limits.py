"""Guardrail constants.

These exist to bound render time (and, historically, the base64 payload
size of compose's now-removed inline audio response), not for any musical
reason -- named constants so they're easy to raise later.
"""

MAX_TRACKS = 16
MAX_BARS_PER_TRACK = 128
MAX_DURATION_SECONDS = 120
MAX_PAYLOAD_BYTES = 15 * 1024 * 1024  # base64-encoded mp3 size cap
