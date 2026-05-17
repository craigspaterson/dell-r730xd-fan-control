# Contributing

## Reporting bugs

Open an issue with:
- Your server model and iDRAC version
- GPU model
- Host OS and kernel version
- Relevant log output from `journalctl -u dell-fan-control` or `/var/log/dell-fan-control.log`

## Suggesting changes

Open an issue before starting work on non-trivial changes. This avoids duplicate effort and ensures the change fits the project's scope.

## Pull requests

1. Fork the repo and create a branch from `main`
2. Keep changes focused — one fix or feature per PR
3. Test on real hardware before submitting
4. Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages (`fix:`, `feat:`, `docs:`, etc.)
5. Update `CHANGELOG.md` under `[Unreleased]`

## Hardware compatibility

This project targets the **Dell PowerEdge R730xd** with iDRAC8. IPMI raw commands may differ on other Dell models. If you have tested on another model, note it in your PR.

## Scope

This is a focused utility — GPU-aware fan control via IPMI on Proxmox. PRs that add support for other hypervisors, GPU vendors, or server models are welcome provided they don't complicate the core use case.
