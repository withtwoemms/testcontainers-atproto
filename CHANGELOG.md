# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.0]

### Added

- Initial package scaffold with src layout and `testcontainers_atproto` top-level module
- Makefile-driven dev workflow (venv, install, test, coverage, build, clean) modeled after the `ucon-tools` pattern, using `uv`
- `setuptools_scm` with `local_scheme = "no-local-version"` for git-tag-derived versioning
- `[tool.uv]` configuration pinning `python-preference = "managed"` and `cache-dir = ".uv_cache"`
- Apache-2.0 copyright headers across source and config files
- GitHub Actions `tests` workflow (Python 3.10–3.14 matrix, Codecov upload, CHANGELOG gate, consolidated CI status)
- GitHub Actions `publish` workflow (main → Test PyPI, tags → Test+Prod PyPI + GitHub Release with changelog-extracted notes)

<!-- Links -->
[Unreleased]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.0.0...HEAD
[0.0.0]: https://github.com/withtwoemms/testcontainers-atproto/releases/tag/0.0.0
