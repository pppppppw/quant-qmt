# Security Policy

## Scope

This repository includes:

- a Windows HTTP gateway for MiniQMT / xtquant
- cross-platform clients that can submit trading requests to that gateway

Please treat security issues carefully.

## Reporting

If you find a vulnerability, do not post the full exploit details in a public issue first.

Instead, contact the maintainers privately and include:

- affected version or commit
- attack surface
- reproduction steps
- impact assessment
- suggested mitigation if available

## Operational Recommendations

- do not expose the gateway directly to the public internet
- prefer LAN, VPN, or strict network ACLs
- do not commit live account identifiers, callback logs, or trade artifacts into the repository
