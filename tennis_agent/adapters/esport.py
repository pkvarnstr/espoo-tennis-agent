import re
from datetime import datetime
from urllib.parse import urlencode
from uuid import uuid4
from ..html import DOM, Node
from ..models import Slot, HELSINKI
from ..http import SourceError

BASE = "https://varaus.esportcenter.fi/varaus/index.php"
PAGES = {3: [f"Tennis {i}" for i in range(1, 9)], 4: [f"Tennis {i}" for i in range(10, 15)]}


class Esport:
    name = "Esport"

    def fetch(self, day, http):
        slots = []
        for page in PAGES:
            url = BASE + "?" + urlencode({"func": "mod_rc_v2", "pageId": page,
                "cdate": day.strftime("%d.%m.%Y"), "_": uuid4().hex})
            slots.extend(self.parse(day, page, http.get(url)))
        return slots

    def parse(self, day, page, html):
        dom = DOM(html).root
        selects = [n for n in dom.all("select") if n.attrs.get("name") == "cdate"]
        selected = [o.attrs.get("value") for s in selects for o in s.all("option") if "selected" in o.attrs]
        pages = [n.attrs.get("value") for n in dom.all("input") if n.attrs.get("name") == "pageId" and "checked" in n.attrs]
        if selected != [day.strftime("%d.%m.%Y")] or pages != [str(page)]:
            raise SourceError("Esport date or tennis page was not selected")
        courts = [n.text() for n in dom.all("th") if "rescal_header" in n.classes()]
        if courts != PAGES[page]:
            raise SourceError("Esport indoor court headers changed")
        slots, rows = [], 0
        for tr in dom.all("tr"):
            heads = [n for n in tr.children if isinstance(n, Node) and n.tag == "th" and "datarow" in n.classes()]
            if not heads:
                continue
            rows += 1
            match = re.fullmatch(r"(\d{2}:\d{2}) - (\d{2}:\d{2})", heads[0].text())
            if not match:
                raise SourceError("Unexpected Esport time row")
            cells = [n for n in tr.children if isinstance(n, Node) and n.tag == "td"]
            if len(cells) != len(courts) or any("rowspan" in c.attrs or "colspan" in c.attrs for c in cells):
                raise SourceError("Unexpected Esport calendar geometry")
            start, end = [datetime.combine(day, datetime.strptime(t, "%H:%M").time(), HELSINKI) for t in match.groups()]
            for court, cell in zip(courts, cells):
                states = {c for c in cell.classes() if c.startswith("state_")}
                if not states or not states <= {"state_white", "state_red", "state_grey", "state_gray", "state_black"}:
                    raise SourceError("Unknown Esport cell state")
                if states == {"state_white"} and "res_success" in cell.classes() and not cell.text():
                    slots.append(Slot(self.name, court, start, end, None,
                        BASE + "?" + urlencode({"func": "mod_rc_v2", "pageId": page, "cdate": day.strftime("%d.%m.%Y")})))
        if not rows:
            raise SourceError("Esport calendar has no time rows")
        return slots
