# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0]

### Added

- `PDSContainer.admin_get(method, params=)` — raw XRPC query with HTTP Basic admin auth
- `PDSContainer.admin_post(method, data=)` — raw XRPC procedure with HTTP Basic admin auth
- `PDSContainer.takedown(account)` — take down an account via `com.atproto.admin.updateSubjectStatus`
- `PDSContainer.restore(account)` — restore a taken-down account
- `PDSContainer.get_subject_status(account)` — query admin status for an account via `com.atproto.admin.getSubjectStatus`
- `PDSContainer.disable_invite_codes(codes=, accounts=)` — disable invite codes via `com.atproto.admin.disableInviteCodes`
- `Account.deactivate(delete_after=)` — deactivate account via `com.atproto.server.deactivateAccount`
- `Account.activate()` — re-activate a deactivated account via `com.atproto.server.activateAccount`
- `Account.check_account_status()` — check account status via `com.atproto.server.checkAccountStatus`
- `Account.request_account_delete()` — request deletion token via `com.atproto.server.requestAccountDelete`
- `Account.delete_account(password, token)` — permanently delete account via `com.atproto.server.deleteAccount`
- Integration tests: deactivate/activate, takedown/restore, delete, status queries, round-trips

### Changed

- `create_account` now uses `admin_post` internally for invite code creation — invite code failures now raise `XrpcError` instead of `httpx.HTTPStatusError`

## [0.5.0]

### Added

- `email_mode` parameter on `PDSContainer`: `"none"` (default) or `"capture"` — capture mode starts a Mailpit companion container on the shared Docker network and configures PDS SMTP to route emails through it
- `PDSContainer.mailbox(address=)` — query captured emails from Mailpit, optionally filtered by recipient address
- `PDSContainer.await_email(address, timeout, poll_interval)` — poll Mailpit until an email for the given address arrives
- `PDSContainer.email_mode` read-only property
- `Account.email` read-only property — stores the email address used during account creation
- `Account.request_email_confirmation()` — trigger `com.atproto.server.requestEmailConfirmation`
- `Account.confirm_email(token)` — confirm email ownership via `com.atproto.server.confirmEmail`
- `Account.request_password_reset()` — trigger `com.atproto.server.requestPasswordReset`
- `Account.reset_password(token, new_password)` — complete password reset via `com.atproto.server.resetPassword`
- Mailpit container lifecycle managed by `PDSContainer.start()` and `stop()`
- Integration tests: email verification flow, password reset flow, mailbox filtering, timeout behavior
- `test-unit` and `test-integration` Makefile targets for running tests by scope

### Fixed

- `xrpc_get` and `xrpc_post` now return `{}` for XRPC methods that return empty bodies instead of raising `JSONDecodeError`

## [0.4.0]

### Added

- `Seed` fluent builder for declarative PDS test state — chain `.account()`, `.post()`, `.record()`, `.follow()`, `.like()`, `.repost()`, `.blob()` calls and materialize with `.apply()`
- `World` frozen dataclass returned by `Seed.apply()` — maps handles to `Account` instances, ordered `RecordRef` lists, and blob references
- Cross-account reference resolution: `.like("alice.test", 0)` resolves to Alice's first record URI automatically during `apply()`
- `Seed.did(handle)` — placeholder that resolves to an account's DID at `apply()` time, for embedding DIDs in custom record dicts
- `Seed.ref(handle, index)` — placeholder that resolves to a record's `{uri, cid}` strong ref at `apply()` time, for cross-record references in custom Lexicons
- Recursive placeholder resolution: `_resolve_placeholders()` walks nested dicts and lists in record payloads before each `create_record()` call
- Account revisiting: calling `.account(handle)` on an already-declared handle switches context back without creating a duplicate — enables interleaving records across accounts (e.g. conversation threads, mutual attestations)
- Three-phase execution in `apply()`: accounts first, then blobs and records, then interactions (follows, likes, reposts)
- `seed_from_dict(pds, spec)` — dict-based alternative for data-driven and YAML-loaded fixtures
- `PDSContainer.seed(spec)` — convenience wrapper for `seed_from_dict`
- Support for custom Lexicon collections via `.record(collection, record, rkey=)` — not limited to `app.bsky.*`
- Eager validation: undeclared targets and missing account context raise at declaration time
- `Seed` and `World` added to top-level package exports

### Removed

- Copyright headers removed from all source, test, and config files

## [0.3.0]

### Added

- `FirehoseSubscription` — WebSocket client for `com.atproto.sync.subscribeRepos` with binary CBOR frame decoding
- `FirehoseSubscription.events(timeout)` — async generator yielding decoded `{"header": {...}, "body": {...}}` events until timeout
- `FirehoseSubscription.collect(count, timeout)` — synchronous helper that collects events for test assertions via `asyncio.run()`
- `FirehoseSubscription.close()` — graceful WebSocket teardown
- `FirehoseSubscription` context manager support (`with sub:` and `async with sub:`)
- `PDSContainer.subscribe(cursor)` — factory method returning a `FirehoseSubscription` bound to the container's WebSocket endpoint
- Guarded import: actionable `ImportError` with install instructions when the `firehose` extra is not installed
- `FirehoseSubscription` added to top-level package exports

## [0.2.0]

### Added

- `PDSContainer.xrpc_get(method, params, auth)` — authenticated XRPC query (HTTP GET)
- `PDSContainer.xrpc_post(method, data, auth, *, content, content_type)` — authenticated XRPC procedure (HTTP POST) with support for both JSON and raw byte payloads
- `PDSContainer.health()` — convenience method returning PDS version info
- `Account.create_record(collection, record, rkey=, validate=)` — create a record, returns `RecordRef`
- `Account.get_record(collection, rkey)` — fetch a record's value
- `Account.list_records(collection, limit=)` — list records in a collection
- `Account.delete_record(collection, rkey)` — delete a record
- `Account.put_record(collection, rkey, record)` — create or update (upsert), returns `RecordRef`
- `Account.upload_blob(data, mime_type)` — upload binary data, returns blob reference
- `Account.strong_ref(collection, rkey)` — fetch current `{uri, cid}` for a record
- `Account.refresh_session()` — rotate access and refresh tokens
- `XrpcError` exception with `method`, `status_code`, `error`, and `message` attributes for structured XRPC error handling

### Changed

- `create_account` now raises `XrpcError` instead of `httpx.HTTPStatusError` on failure

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
[Unreleased]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.6.0...HEAD
[0.6.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.5.0...0.6.0
[0.5.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.4.0...0.5.0
[0.4.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.3.0...0.4.0
[0.3.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.2.0...0.3.0
[0.2.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.1.0...0.2.0
[0.1.0]: https://github.com/withtwoemms/testcontainers-atproto/compare/0.0.0...0.1.0
[0.0.0]: https://github.com/withtwoemms/testcontainers-atproto/releases/tag/0.0.0
