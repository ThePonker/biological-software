"""Thin, polite wrapper around the BHL API v3 (stdlib only - no requests needed).

Throttles to config.REQUEST_INTERVAL, retries transient failures with
exponential backoff, and never puts the API key into error messages.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config


class BHLError(RuntimeError):
    """Raised when BHL returns an error status or a request ultimately fails."""


class BHLClient:
    def __init__(self, api_key, interval=config.REQUEST_INTERVAL):
        self._key = api_key
        self._interval = interval
        self._last = 0.0
        self.request_count = 0

    # --- public API -----------------------------------------------------
    def raw(self, op, **params):
        """Full JSON response for an operation (used by the probe command)."""
        query = {"op": op, "apikey": self._key, "format": "json"}
        query.update({k: v for k, v in params.items() if v is not None})
        return self._get_json(config.API_BASE + "?" + urllib.parse.urlencode(query), op)

    def call(self, op, **params):
        """Return the Result list for an operation, raising on non-ok status."""
        data = self.raw(op, **params)
        status = data.get("Status")
        if status != "ok":
            raise BHLError(f"{op}: status={status!r} {data.get('ErrorMessage') or ''}".strip())
        result = data.get("Result")
        if result is None:
            return []
        return result if isinstance(result, list) else [result]

    def name_metadata(self, name):
        """Titles/items/pages on which a scientific name appears."""
        return self.call("GetNameMetadata", name=name)

    def page_metadata(self, page_id):
        """One page's metadata including OCR text and names found on it."""
        result = self.call("GetPageMetadata", pageid=page_id, ocr="t", names="t")
        return result[0] if result else {}

    # --- internals ------------------------------------------------------
    def _throttle(self):
        wait = self._interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _get_json(self, url, op):
        last_error = None
        for attempt in range(config.MAX_RETRIES):
            self._throttle()
            self.request_count += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
                with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8-sig"))
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code not in config.RETRY_STATUS:
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = f"network error: {getattr(exc, 'reason', exc)}"
            except json.JSONDecodeError:
                last_error = "response was not valid JSON"
            time.sleep(2 ** attempt * self._interval)
        raise BHLError(f"{op} failed after {config.MAX_RETRIES} attempts ({last_error})")
