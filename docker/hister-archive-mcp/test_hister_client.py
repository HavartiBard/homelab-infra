"""Run: python3 test_hister_client.py — stdlib only, no pip deps."""

import hister_client as hc

# Valid payload with label
p = hc.build_payload("https://example.com/a", "A title", "body text", label="research")
assert p == {"url": "https://example.com/a", "title": "A title", "text": "body text", "label": "research"}

# Title defaults to url; label omitted when not given
p = hc.build_payload("https://example.com/b", None, "body")
assert p == {"url": "https://example.com/b", "title": "https://example.com/b", "text": "body"}
assert "label" not in p

# Rejects non-http url
try:
    hc.build_payload("ftp://nope", "t", "x")
    raise AssertionError("expected ValueError for non-http url")
except ValueError:
    pass

# Rejects empty text
try:
    hc.build_payload("https://example.com", "t", "   ")
    raise AssertionError("expected ValueError for empty text")
except ValueError:
    pass

print("OK")
