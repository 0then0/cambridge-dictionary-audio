# Security policy

## Supported versions

Security fixes target the latest stable release. Update to the latest release
before reporting a vulnerability where practical. Older releases and development
snapshots do not have a separate security maintenance commitment.

Official downloads and signing limitations are described in the
[README](README.md) and [mobile installation guide](docs/mobile/install.md).
Checksums verify file integrity; they do not replace a trusted signing certificate.

## Report a vulnerability

Email [zheltov_pe@mail.ru](mailto:zheltov_pe@mail.ru) with the subject
`Cambridge Dictionary Audio security report`. Do not open a public issue or
publish an exploit before the maintainer has had an opportunity to investigate.
For ordinary bugs and feature requests, use [GitHub Issues](https://github.com/0then0/cambridge-dictionary-audio/issues).

Please include:

- Affected version, platform and installation source.
- Reproduction steps and expected versus observed behavior.
- Potential impact and any prerequisites an attacker would need.
- A minimal sanitized sample or proof of concept, if available.

Remove tokens, signing keys, personal collections and other private data from
reports. Request a secure transfer method before sending sensitive attachments.
Limit testing to systems and data you own or have permission to test.

The maintainer will assess the report and coordinate fixes and disclosure with
the reporter. This is a volunteer-maintained project; no response deadline or
bug-bounty payment is promised. Reports involving third-party services should
also be directed to the affected provider without probing its systems further.
