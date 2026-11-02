# Source discovery and validation

Initial direct HTTP investigation: 2026-11-01 UTC. Both 2026-11-02 and 2026-11-03 were requested explicitly. Sanitized fixtures preserve public resource metadata, availability rows and calendar fragments; scripts, tracking, cookies, CSRF values, customer details and credentials are not included. These fixtures are regression evidence, not current availability.

## Cintoia: Rosegarden, Tapiolan Tennispuisto, Targa Arena

All three homepages returned the same 4,888-byte JavaScript shell. This was rejected as availability evidence. The public JavaScript bundle `/static/js/main.19877318.chunk.js` exposed the web application's actual read path:

1. Public Firestore `inits` lookup matched the hostname to an account key. The production adapter uses those observed public account identifiers, which are not credentials.
2. The public read-only `ui-get` callable with `q=getResources` returned court names, sports and categories. No authentication or booking request was made.
3. Public Firestore `freeindex/{account}/indexes/public` contains date-keyed pointers. The adapter requests only the target date using a quoted numeric field mask.
4. Fetch the exact versioned JSON URL supplied by the index under `https://falconft.s3.eu-north-1.amazonaws.com/{account}/{YYYYMMDD}/…json`. Both venue and requested date must match the URL path. The adapter never guesses a storage URL.
5. Vacancy rows contain local `s`/`e` times, `p` price in cents and optional `ex` offers with explicit duration and price. Client function `ge` confirms this interpretation. Only explicit 60-minute offers are accepted, including explicit 60-minute extensions of shorter base offers. Longer gaps are not split or priced speculatively.

Both dates returned different current version pointers and different slot data for each venue. November 2/3 response sizes were Rosegarden 33,455/33,391 bytes, Tennispuisto 266/233 bytes and Targa Arena 47,189/47,941 bytes. A small or empty preferred-hours result is not confused with access failure.

Indoor mappings: Rosegarden numbered `Tennis N` resources in category `tennis`, supported by the [official indoor tennis description](https://rosegarden.fi/tennis); Tennispuisto category `sisätennis`; Targa category `tennis`, separate from `ulkotennis`, consistent with [Grani Tennis indoor courts](https://granitennis.fi/fi/kentat/sisakentat/). Equipment, padel, squash and outdoor categories are excluded. Rosegarden currently exposes nine numbered resources despite its website describing ten courts; monitoring covers the exposed resources only.

## Esport

The [official tennis page](https://esport.fi/mailapelit/lajit/tennis/) links “Varaa pelivuoro” to `https://varaus.esportcenter.fi/varaus/index.php?func=mod_rc_v2` (My Esport / Confirma).

Direct HTTP GET with `pageId=3` / `pageId=4` and `cdate=02.11.2026` / `03.11.2026` returned server-rendered tennis tables. The requested date was the selected calendar option and the requested tennis group was checked. Headers explicitly identify Tennis 1–8 and 10–14. Time rows show free cells (`state_white res_success`) and occupied cells (`state_red`), with date-specific differences. November 2/3 sizes: group 3 22,950/22,740 bytes; group 4 19,177/19,163 bytes. Blank arbitrary cells are never interpreted as availability: the known free classes and validated table geometry are required. Only full 60-minute rows within the user's hours survive filtering; for example a 20:30–21:30 row is excluded on weekdays. Public calendar prices are absent; report price as unknown.

## Smash Olari

The [official Olari venue page](https://www.smash.fi/pelipaikat/olarin-tennishalli/) identifies `smash.play.fi`. The generic subdomain request returned HTTP 400 in this environment; the public canonical Play.fi calendar works at `https://play.fi/smashcenter/booking/booking-calendar?BookingCalForm%5Bp_laji%5D=7`.

Explicit `BookingCalForm[p_pvm]=2026-11-02` and `2026-11-03` returned 41,922 and 42,421 bytes, selected date inputs, the Olari title and date-specific available/reserved cells. Available links contain `alkuaika`, `kesto=60`, and resource IDs 36/37/38 mapped to Te1/Te2/Te3. Resource 41 is a ball machine and is excluded. These links are parsed but **never followed**. Reports link to the date-specific calendar. Prices are absent and remain unknown.

## Freshness and limits

Each run re-reads each requested date rather than reusing fixtures or a previously known storage pointer. Requests ask for no-cache; HTML/index URLs include a fresh request nonce. Responses with excessive HTTP Age or an old/missing HTTP Date are rejected. Cintoia's versioned JSON is intentionally a published availability snapshot: an old object modification time alone does not mean stale availability if the freshly read authoritative date index still selects it. This establishes date-specific public offers, not atomic real-time booking guarantees.

See `validation-summary.json` for the successful end-to-end check timestamp, target dates, counts and request hashes. Tests also reject wrong-date pages, shells, unknown resource IDs, changed table states, and cross-date storage pointers. No vendor stability guarantee is assumed. All sources have direct access, so no browser fallback was needed.
