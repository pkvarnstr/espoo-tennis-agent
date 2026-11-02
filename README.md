# Espoo Tennis Agent

Read-only indoor tennis availability monitoring through GitHub Actions. Never books, holds a court, signs in, or pays. No credentials or private data are required.

## Venues and verified access

| Priority | Venue | Public source | Coverage |
|---|---|---|---|
| 1 | Rosegarden | Cintoia public date index and vacancy JSON | Numbered indoor tennis courts; excludes ball machine |
| 1 | Tapiolan Tennispuisto | Cintoia public date index and vacancy JSON | `sisätennis` category; excludes outdoor courts |
| 1 | Esport | [Official My Esport calendar](https://varaus.esportcenter.fi/varaus/index.php?func=mod_rc_v2) | Tennis 1–8 and 10–14 |
| 2 | Targa Arena | Cintoia public date index and vacancy JSON | Indoor `tennis` category; excludes `ulkotennis` |
| 2 | Smash Olari | [Official Play.fi Olari tab](https://play.fi/smashcenter/booking/booking-calendar?BookingCalForm%5Bp_laji%5D=7) | Te1, Te2, Te3; excludes ball machine |

Source discovery and date-specific validation evidence are described in [docs/source-validation.md](docs/source-validation.md). A successful homepage request does **not** validate availability. Source support is established by date-specific offers and metadata, then checked again on every run. Targa Arena is in Kauniainen and is included because it was explicitly requested.

## Rules

- Tomorrow and the following day, based on `Europe/Helsinki`, including DST.
- Exactly 60 minutes, entirely within 17:00–21:00 on weekdays or 10:00–20:00 on weekends.
- At least two hours before the session starts.
- Indoor tennis only. Availability is a snapshot; the calendar may change before a user books.
- Cintoia prices come from live slot data in cents, converted to EUR. Esport and Play.fi prices are `null` / “Unknown”: no price is invented or fetched from a booking creation page.

## Run and read reports

Python 3.11+ with system timezone data; no runtime dependencies:

```sh
python -m unittest discover -s tests -v
python -m tennis_agent --validate --output reports
python -m tennis_agent --output reports
```

The `--validate` mode additionally requires at least one observed 60-minute offer per venue across the two dates, even outside preferred hours. This intentionally fails conservatively if a venue is completely booked; it does not prove the integration is broken. Normal monitoring accepts an empty, structurally valid date calendar.

Every run writes `availability.json` and `availability.md`. JSON includes venue, court, date, local start/end, offset-aware timestamps, EUR price (nullable), booking calendar URL, per-source health, duplicate counts and HTTP evidence (URL, server date, response age, hash and size). No response bodies, cookies or authentication headers are saved to artifacts.

Failures produce a partial report and nonzero exit status. A venue failing either date contributes no slots, and is explicitly shown as unknown. Other venues continue. Requests have timeouts, bounded response sizes and retries for transient errors. Unknown dates, courts or page structures fail closed. Duplicate venue/court/start/end offers are collapsed; conflicting prices fail the source.

## GitHub Actions

After merging, open **Actions → Validate tennis booking sources → Run workflow**. Download the `tennis-source-validation-…` artifact. Both the unit tests and live validation must succeed before enabling recurring monitoring.

**Recurring monitoring is disabled by default.** After reviewing successful live validation, a repository maintainer can set **Settings → Secrets and variables → Actions → Variables → New repository variable**, named `MONITORING_ENABLED`, with value `true`. Delete it or set `false` to stop. No secret or token is needed. The pull request does not set this variable or merge itself.

The monitor uses UTC cron candidates 06:00, 07:00, 12:00 and 13:00, with an IANA timezone gate selecting precisely the seasonal candidates corresponding to **09:00 and 15:00 Europe/Helsinki**. Tests cover both daylight-saving transitions. The gate uses the event's cron expression so modest runner delays do not discard the intended run. GitHub may delay or drop scheduled runs; exact wall-clock execution is not guaranteed. Schedules only operate from the default branch. Disabled monitoring can still create skipped schedule records; it sends no booking-system requests.

For an immediate check, use **Actions → Indoor tennis availability → Run workflow**. Manual runs bypass the schedule and enable-variable gates. Reports appear in the run summary and as a 14-day artifact, including partial results on failure. Workflows have read-only repository permissions and pinned actions.

## Delivery and maintenance

`ReportSink` in `tennis_agent/delivery.py` is the delivery boundary. `FileSink` produces the GitHub artifact and summary inputs. There is no supported connection configured to deliver directly from GitHub Actions into this ChatGPT conversation; add another sink only after establishing a supported integration. Do not put tokens, credentials, session cookies or personal booking data in this public repository.

Cintoia's endpoints are public client interfaces, not a promised supported vendor API. Parsers may require maintenance if schemas or court mappings change. Revalidate mappings before extending court coverage. All current sources were accessible without Playwright; browser automation is unnecessary. If access changes, record the failure, keep that source unknown, and evaluate a read-only Playwright fallback separately rather than bypassing authentication or anti-bot challenges.
