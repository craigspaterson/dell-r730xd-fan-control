# Contributing

## Reporting bugs

Open an issue using the **Bug report** template. It will prompt you for the hardware details, iDRAC version, and log output needed to diagnose the problem.

## Suggesting changes

Open an issue using the **Feature request** template before starting work on non-trivial changes. This avoids duplicate effort and ensures the change fits the project's scope.

## Pull requests

1. Fork the repo and create a branch from `main`
2. Keep changes focused — one fix or feature per PR
3. Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages (`fix:`, `feat:`, `docs:`, etc.)
4. Fill out the PR template — in particular the hardware section, since IPMI behaviour varies between Dell models
5. Before submitting, confirm:
   - Tested on real hardware with `ipmitool` fan speed commands verified
   - Service restarts cleanly
   - Watchdog behaves correctly
   - `CHANGELOG.md` updated under `[Unreleased]`
   - No hardcoded values that belong in `config.yaml`

## Hardware compatibility

This project targets the **Dell PowerEdge R730xd** with iDRAC8. IPMI raw commands may differ on other Dell models. If you have tested on another model, note it in your PR.

## Scope

This is a focused utility — GPU-aware fan control via IPMI on Proxmox. PRs that add support for other hypervisors, GPU vendors, or server models are welcome provided they don't complicate the core use case.
