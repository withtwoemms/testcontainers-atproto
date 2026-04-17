# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

### Added

- `PDSContainer` subclasses `DockerContainer` with auto-generated secrets (`PDS_ADMIN_PASSWORD`, `PDS_JWT_SECRET`, `PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX`)
- Health-check wait strategy polling `GET /xrpc/_health` until HTTP 200
- Container teardown via context manager (`__enter__` / `__exit__`)
- `host`, `port`, `base_url`, and `admin_password` properties
- `create_account(handle, email=, password=)` — invite code generation + account creation via XRPC
- `Account` with `did`, `handle`, `access_jwt`, and `refresh_jwt` read-only properties
- Handle-domain resolution using `PDS_SERVICE_HANDLE_DOMAINS=".test"` for test handles
- Local PLC directory on a shared Docker network — DID registration never touches the public internet
- `plc_mode` parameter: `"mock"` (default, in-memory PLC) or `"real"` (Postgres-backed PLC for production parity)
- Docker-gated integration tests (`test_container.py`, `test_create_account.py`) with adversarial coverage
- AT Protocol glossary (`docs/glossary.md`) linked from README

## [0.0.0]

### Added

- Initial package scaffold with src layout and `testcontainers_atproto` top-level module
- `RecordRef` frozen dataclass with AT URI validation and `as_strong_ref()` helper
- `PDSContainer`, `Account`, and `FirehoseSubscription` stubs (method bodies raise `NotImplementedError` pending Phase 1+ work)
- Pytest fixtures (`pds`, `pds_module`, `pds_pair`, `pds_image`) auto-registered via the `pytest11` entry point
- Makefile-driven dev workflow (venv, install, test, coverage, build, clean) modeled after the `ucon-tools` pattern, using `uv`
- `setuptools_scm` with `local_scheme = "no-local-version"` for git-tag-derived versioning
- `[tool.uv]` configuration pinning `python-preference = "managed"` and `cache-dir = ".uv_cache"`
- Apache-2.0 copyright headers across source and config files
- GitHub Actions `tests` workflow (Python 3.10–3.14 matrix, Codecov upload, CHANGELOG gate, consolidated CI status)
- GitHub Actions `publish` workflow (main → Test PyPI, tags → Test+Prod PyPI + GitHub Release with changelog-extracted notes)

<!-- Links -->
[Unreleased]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.1.0...HEAD
[0.1.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.0.0...0.1.0
[0.0.0]: https://github.com/withtwoemms/testcontainers-atproto/releases/tag/0.0.0
