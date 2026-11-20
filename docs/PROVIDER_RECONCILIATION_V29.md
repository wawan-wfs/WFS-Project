# WFS PROJECT v2.9 — Provider billing uncertainty and offline comparison

**Status: partial security controls; no paid provider request, official invoice, authenticated export or provider-side spending limit was exercised in this release.** `app/provider.py` records provider-returned input/output tokens; `app/store.py` now also stores optional provider response IDs (unique if present). These are not official invoices.

## Fail-closed billability

When a provider call returns unusable/missing usage, incomplete output, a network timeout, HTTP error, or an intermediate failed retry, it **may still incur a charge**. The source now writes a durable `billing_unknown` provider attempt. Under any configured organizational, workspace or project hard estimated-cost limit, **new calls are denied until operator reconciliation**. Existing estimated reservations associated with a failed attempt stay held with non-expiring liability instead of being released as $0. Do not change these records directly or clear them merely to pass a test. Responses that have recorded usage but invalid generated content keep their settled usage when a reservation was active.

This admission control estimates potential cost, not provider invoices, not refundable credits or a provider-enforced hard daily cap. Separate provider-account hard caps and operator review of chargebacks remain necessary. Data exported from a provider account may include billable retries even if the application failed to read the response.

## Operator-only offline read-only comparison

If the real provider offers exportable **per-response cost** records, an authorized operator can normalize the independently authenticated provider export to a CSV with the exact header `response_id,actual_usd` and one row per response. Preserve original official export and proof of provenance outside this repository. Unsupported provider reports with daily/model-only aggregate costs cannot establish per-response allocations and must not be made to look like they can.

```powershell
Get-FileHash -Algorithm SHA256 C:\wfs-secure\provider-response-costs.csv
python scripts/provider-reconcile-report.py --db .\data\wfs.sqlite3 `
  --export C:\wfs-secure\provider-response-costs.csv `
  --expected-sha256 <export_sha256> `
  --output C:\wfs-secure\provider-reconciliation-v29.json
```

The utility reads the local database in SQLite read-only mode, compares only matching provider response IDs and USD amounts against **local estimates** with configurable tolerance; reports differences, unmatched responses/ledger rows and unresolved billing attempts. It never updates usage, clears quarantine or attributes an unmatched provider charge to a guessed organization. Duplicate response IDs and malformed prices fail closed; hashes of unmatched provider IDs are printed instead of raw identifiers. The report is **not verification of a provider invoice's authenticity** and is not an operator authorization to release uncertain liability. An actual invoice/usage export, evidence of account identity, and human review of failed attempts remain required before changing spending status.
