# Changelog

All notable changes to this project will be documented in this file.

This project follows semantic versioning where practical. Public releases are
tagged in Git as `vX.Y.Z` and published to PyPI with the same version.

## [0.1.1] - 2026-09-09

### Documentation

- Updated the publishing checklist for repeatable PyPI and TestPyPI releases.
- Replaced hard-coded release examples with version variables to reduce manual
  update errors.
- Clarified clean-environment install checks for public package verification.

## [0.1.0] - 2026-09-01

### Added

- Initial public release of `capsolver-agent`.
- Framework-agnostic tool definitions for CapSolver captcha solving.
- Async tool executor for use in custom agent loops.
- LangChain tool implementations behind the `langchain` extra.
- Optional browser-based tools behind the `browser` extra.
- `capsolver-agent` CLI for inspecting tools and schemas.
