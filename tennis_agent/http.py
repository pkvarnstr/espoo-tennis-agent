"""Bounded public HTTP reads; deliberately no generic mutation interface."""
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, parse_qs

LOG = logging.getLogger(__name__)
ALLOWED = {"rosegarden.cintoia.com", "tennispuisto.cintoia.com", "targaarena.cintoia.com",
           "firestore.googleapis.com", "europe-west1-falcon-328a1.cloudfunctions.net",
           "falconft.s3.eu-north-1.amazonaws.com", "varaus.esportcenter.fi", "play.fi"}


class SourceError(RuntimeError):
    pass


def check_url(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED or p.username or p.password or p.port:
        raise SourceError("Unexpected public source URL")
    if p.hostname == "play.fi" and p.path != "/smashcenter/booking/booking-calendar":
        raise SourceError("Only the public Play.fi calendar may be fetched")
    if p.hostname == "varaus.esportcenter.fi" and (
        p.path != "/varaus/index.php" or parse_qs(p.query).get("func") != ["mod_rc_v2"]
    ):
        raise SourceError("Only the public Esport calendar may be fetched")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Http:
    def __init__(self):
        self.evidence = []
        self.opener = urllib.request.build_opener(SafeRedirect())

    def get(self, url):
        return self._read(url)

    def resources(self, customer):
        # A read-only callable used by Cintoia's public web application.
        payload = {"data": {"q": "getResources", "customerid": customer}}
        return json.loads(self._read(
            "https://europe-west1-falcon-328a1.cloudfunctions.net/ui-get", payload))

    def _read(self, url, payload=None):
        check_url(url)
        if payload is not None and url != "https://europe-west1-falcon-328a1.cloudfunctions.net/ui-get":
            raise SourceError("POST is restricted to the read-only resource lookup")
        headers = {"User-Agent": "espoo-tennis-agent/0.1 (public availability; read-only)",
                   "Cache-Control": "no-cache", "Pragma": "no-cache"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers=headers)
                with self.opener.open(req, timeout=25) as r:
                    if r.status != 200:
                        raise SourceError(f"Unexpected HTTP {r.status}")
                    body = r.read(4_000_001)
                    if len(body) > 4_000_000:
                        raise SourceError("Source response too large")
                    age = int(r.headers.get("Age", "0"))
                    server_date = r.headers.get("Date")
                    if age > 300 or not server_date:
                        raise SourceError("Stale response or missing server date")
                    if abs((datetime.now(timezone.utc) - parsedate_to_datetime(server_date)).total_seconds()) > 600:
                        raise SourceError("Stale HTTP server date")
                    self.evidence.append({"url": url, "status": r.status, "server_date": server_date,
                                          "age_seconds": age, "sha256": hashlib.sha256(body).hexdigest(),
                                          "bytes": len(body)})
                    return body.decode("utf-8")
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504):
                    raise SourceError(f"HTTP {exc.code}") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            if attempt < 2:
                LOG.warning("Public source request retry %s", attempt + 1)
                time.sleep(2 ** attempt)
        raise SourceError("Public source request failed after 3 attempts")
