# Security policy

## Supported versions

GroundFlip is pre-1.0. Security fixes are applied to the latest main branch and
most recent release only.

## Reporting a vulnerability

Do not open a public issue for credential exposure, arbitrary command execution,
path traversal, report injection, cassette tampering bypass, or unsafe replay.
Use the repository's private security-advisory channel once the project is
published. Include a minimal reproduction with synthetic data and no live key.

Expected response targets after publication:

- acknowledgement within 3 business days;
- initial severity assessment within 7 business days;
- coordinated disclosure after a fix or mitigation is available.

## Secret handling

GroundFlip reads provider keys from the environment through provider SDKs. It
does not load `.env`, accept keys in contracts, or intentionally persist them.
If a secret appears in a cassette/report despite redaction, treat it as exposed:
remove the artifact, rotate the credential, and report the bypass privately.

See [the threat model](docs/THREAT_MODEL.md) for trust boundaries and residual
risks. v0.1 is not yet security-audited for hostile production workloads.

