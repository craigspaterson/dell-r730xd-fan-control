# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security vulnerabilities.

Report them privately via [GitHub's private vulnerability reporting](https://github.com/craigspaterson/dell-r730xd-fan-control/security/advisories/new).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix

You can expect an acknowledgement within 48 hours.

## Scope

This project runs as root on a local Proxmox host and communicates with iDRAC via IPMI. It has no network-facing interface. The primary attack surface is the configuration file at `/etc/dell-fan-control/config.yaml`, which should be owned and writable only by root.
