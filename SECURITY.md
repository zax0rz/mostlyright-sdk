# Security Policy

## Reporting an issue

Please report issues affecting the integrity, confidentiality, or availability of the SDK privately.

**Contact:** <vu@mostlyright.md>

Please **do not open a public GitHub issue** for these reports.

Include in the report:
- A description of the issue and its impact
- Steps to reproduce (a minimal proof of concept is ideal)
- The affected SDK package(s) and version(s)
- Your name and contact (or anonymous, if preferred)

We will acknowledge receipt within 3 business days. Communication will continue privately until a fix is available and coordinated disclosure is agreed.

## Disclosure timeline

We follow a **90-day coordinated disclosure window** by default:

1. Report received → private acknowledgement within 3 business days
2. Issue triaged and a fix is developed in a private branch
3. Fix released as a patch version on PyPI + npm
4. Public advisory and credit published within 90 days of the original report (or sooner, if the fix has shipped and consumers have had time to upgrade)

If the issue is being actively exploited, the timeline can be compressed by mutual agreement.

## Supported versions

| Version | Status | Patches |
|---|---|---|
| 1.0.x | Active | All issues |
| 0.1.x | Maintenance | Critical fixes only, through 2026-11-26 (6 months from v1.0 release) |
| 0.0.x (legacy `tradewinds*`) | End of life | None |

After the 6-month maintenance window for 0.1.x closes, only 1.x receives fixes.

## Scope

This policy covers the published packages:

**PyPI:** `mostlyrightmd`, `mostlyrightmd-weather`, `mostlyrightmd-markets`
**npm:** `@mostlyrightmd/core`, `@mostlyrightmd/weather`, `@mostlyrightmd/markets`, `mostlyright`

Out of scope:
- Issues in third-party APIs the SDK calls (NOAA, NWS, IEM, Kalshi, Polymarket) — please report those to the respective upstream
- Issues in the documentation site (`mostlyright.md`) infrastructure — please report those separately to the site maintainer
- Vulnerabilities in transitive dependencies that don't reach a code path the SDK invokes
