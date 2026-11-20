# v3.6 — Operator-only OpenAI organization costs (official aggregate read)

**Scope:** implementation + offline fixture tests. **Not** a successful live provider request or an authenticated invoice in this release. The operator's actual credentials, account, and billing system have not been accessed.

The official OpenAI API documents `GET /v1/organization/costs`. The response returns **time buckets and aggregate amounts**, not response-by-response charges. This cannot determine whether a particular timed-out/retried WFS request incurred a charge or authorize clearing `billing_unknown`.

Reference: https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage

The new `scripts/provider-official-costs-v36.py` performs bounded **GET-only** calls to the exact HTTPS origin, validates the response body, and writes an exclusively created private JSON report (`0600`) with aggregate USD and SHA-256 hashes of fetched page bytes. It never writes the WFS database, never changes budgets or provider-side spending caps, and never embeds credentials in its output. Redirects, invalid currencies/amounts, malformed pagination, overlarge response bodies and long date windows fail closed. Tests use an in-memory fake opener; they do not contact the official API.

## Optional authorized operator procedure

On a separately controlled operator machine, not a public gateway, after explicit account-owner approval and a credential with the narrowest supported read-only billing privileges:

```powershell
# Example range in epoch seconds: substitute your approved actual UTC interval.
$env:WFS_OPENAI_ADMIN_KEY = Read-Host 'Admin API key (not stored by WFS)'
python scripts/provider-official-costs-v36.py `
  --start-epoch 1762473600 --end-epoch 1762560000 `
  --confirm READ_ONLY_OFFICIAL_COSTS --output C:\wfs-secure\official-costs-v36.json
Remove-Item Env:WFS_OPENAI_ADMIN_KEY
```

**Important:** `Read-Host` is displayed input, not masked. For secure input use your organization's approved secret manager or `Read-Host -AsSecureString` plus a temporary private process environment conversion; never paste an admin key into shell history or source. Do not upload the report or secrets to ChatGPT/GitHub by default. The output directory must already exist with restricted permissions.

Verify the report's provenance using operator-collected HTTPS/API logs and account identity, and compare the aggregate period only to an independently scoped internal summary. Aggregate values cannot be assigned to individual tenants, responses, or retries without supporting external transaction-level evidence. `billing_unknown` remains held and any provider-side cap remains unverified until separately proven by the authorized operator. An operator-supplied JSON copy alone is **not** independent authenticity proof.

## Reproduce offline safety tests

```bash
PYTHONPATH=. python -m pytest -q tests/test_v36_official_costs.py
```

The suite mocks HTTP transport to test parsing only. No billing API was invoked during v3.6 implementation.
