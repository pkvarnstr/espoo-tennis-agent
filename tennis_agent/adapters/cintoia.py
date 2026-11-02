import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit, urlencode
from uuid import uuid4
from ..models import Slot, HELSINKI
from ..http import SourceError

FIRESTORE = "https://firestore.googleapis.com/v1/projects/falcon-328a1/databases/(default)/documents"


class Cintoia:
    """Public Firestore index -> versioned vacancy JSON, as used by the web client."""
    def __init__(self, name, host, customer, category):
        self.name, self.host, self.customer, self.category = name, host, customer, category

    def fetch(self, day, http):
        resources = http.resources(self.customer).get("result")
        if not isinstance(resources, dict) or not resources:
            raise SourceError("Missing resource metadata")
        # Request only this date's field; no credentials or user collections.
        key = day.strftime("%Y%m%d")
        url = f"{FIRESTORE}/freeindex/{self.customer}/indexes/public?" + urlencode({
            "mask.fieldPaths": f"`{key}`", "_": uuid4().hex})
        index = json.loads(http.get(url))
        try:
            vacancy_url = index["fields"][key]["mapValue"]["fields"]["key"]["stringValue"]
        except (KeyError, TypeError):
            raise SourceError("Requested date absent from public index; availability unknown") from None
        p = urlsplit(vacancy_url)
        prefix = f"/{self.customer}/{key}/"
        if (p.scheme != "https" or p.netloc != "falconft.s3.eu-north-1.amazonaws.com"
                or not p.path.startswith(prefix) or not re.fullmatch(r"[\w-]+\.json", p.path[len(prefix):])
                or p.query or p.fragment):
            raise SourceError("Vacancy URL does not match venue and requested date")
        raw = json.loads(http.get(vacancy_url))
        return self.parse(day, resources, raw)

    def parse(self, day, resources, raw):
        if not isinstance(raw, dict):
            raise SourceError("Unexpected Cintoia availability schema")
        indoor = {k: v for k, v in resources.items() if v.get("category") == self.category
                  and v.get("sport") == "Tennis" and v.get("type") == "court"
                  and (re.fullmatch(r"Tennis \d+", v.get("displayName", "")) if self.host.startswith("rosegarden") else True)}
        if not indoor:
            raise SourceError("No verified indoor tennis resource metadata")
        if set(raw) - set(resources):
            raise SourceError("Unknown resource IDs in vacancy data")
        slots = []
        for rid, court in indoor.items():
            for row in raw.get(rid, []):
                start = datetime.combine(day, datetime.strptime(row["s"], "%H%M").time(), HELSINKI)
                variants = [{"e": row["e"], "p": row["p"]}] + row.get("ex", [])
                for variant in variants:
                    end = datetime.combine(day, datetime.strptime(variant["e"], "%H%M").time(), HELSINKI)
                    if end - start != timedelta(minutes=60):
                        continue
                    if "du" in variant and variant["du"] != 60:
                        raise SourceError("Inconsistent Cintoia duration")
                    cents = variant["p"]
                    if isinstance(cents, bool) or not isinstance(cents, int) or cents < 0:
                        raise SourceError("Invalid Cintoia price")
                    slots.append(Slot(self.name, court["displayName"], start, end,
                                      str((Decimal(cents) / 100).quantize(Decimal("0.01"))),
                                      f"https://{self.host}/"))
        return slots
