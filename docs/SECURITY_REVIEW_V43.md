# v4.3 Security scope

- No app authentication, tenant permissions, preview transport, event authorization or provider billing behavior changed.
- PostgreSQL admission remains an isolated, trusted-input experiment. The strict replica mode checks for a synchronous standby and treats warning-based commit uncertainty as unavailable. The local stop-before-promote guard is not a distributed leader fence and must not be reused as one.
- Artifact compensation retains evidence when it cannot restore state. The exact-match verifier remains read-only, requires an offline paired snapshot and is not a release approval. Windows clone verification was prepared, not executed.
- Real Unix transport was blocked before socket creation. No fallback was introduced and the existing UDS, broker and authority tests remain runnable on an approved Linux host.
- Production admission remains denied. No production host, paid provider, DNS, external ingress, customer data or real credentials were touched.
