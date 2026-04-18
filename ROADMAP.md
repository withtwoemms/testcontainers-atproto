# testcontainers-atproto Roadmap

> *From skeleton to production-ready ephemeral PDS testing.*

---

## Vision

testcontainers-atproto is a testing infrastructure module for anyone building on AT Protocol. Spin up a real PDS in a container, create accounts, publish records, and observe firehose events — all from pytest fixtures.

**Target users:**

- Application developers building on AT Protocol (not just Bluesky)
- Library authors writing SDKs against custom Lexicons
- CI pipelines that need hermetic integration tests without touching shared infrastructure

---

## Release Timeline

| Version | Theme | Status |
|---------|-------|--------|
| v0.0.0 | Package Scaffold | Complete |
| v0.1.0 | Container Lifecycle + Account Creation | Complete |
| v0.2.0 | XRPC Ergonomics | Complete |
| v0.3.0 | Firehose Subscription | Complete |
| v0.4.0 | Email Verification + Password Reset | Planned |
| v0.5.0 | Account Lifecycle + Admin Operations | Planned |
| v0.6.0 | Repo Sync | Planned |
| v0.7.0 | Declarative Seeding | Planned |
| v1.0.0 | Hermeticity + Federation | Planned |

---

## v0.0.0 — Package Scaffold (Complete)

**Theme:** Build toolchain and module skeleton.

- [x] `src` layout with `testcontainers_atproto` top-level module
- [x] `RecordRef` frozen dataclass with AT URI validation and `as_strong_ref()`
- [x] `PDSContainer`, `Account`, and `FirehoseSubscription` stubs
- [x] Pytest fixtures (`pds`, `pds_module`, `pds_pair`, `pds_image`) registered via `pytest11` entry point
- [x] Makefile-driven dev workflow using `uv` (venv, install, test, coverage, build, clean)
- [x] `setuptools_scm` for git-tag-derived versioning
- [x] GitHub Actions CI (Python 3.10–3.14 matrix, Codecov, CHANGELOG gate)
- [x] GitHub Actions publish pipeline (Test PyPI on main, Prod PyPI on tags)

**Outcomes:**
- Package installs, builds, and passes import-level tests
- Fixtures are discoverable by pytest but not yet functional (stubs)
- CI and publish pipelines are in place from day one

---

## v0.1.0 — Container Lifecycle + Account Creation (Complete)

**Theme:** A running PDS you can create accounts on.

- [x] `PDSContainer` subclasses `DockerContainer` with auto-generated secrets
- [x] Container environment: `PDS_HOSTNAME`, `PDS_PORT`, `PDS_ADMIN_PASSWORD`, `PDS_JWT_SECRET`, `PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX`, and friends
- [x] Health-check wait in `__enter__` (poll `GET /xrpc/_health` until HTTP 200)
- [x] Container teardown in `__exit__`
- [x] `host`, `port`, `base_url`, and `admin_password` properties
- [x] `create_account(handle)` — invite code generation + account creation via XRPC
- [x] `Account.access_jwt` and `Account.refresh_jwt` public properties
- [x] Handle-domain resolution: `PDS_SERVICE_HANDLE_DOMAINS=".test"` for test handles
- [x] Docker-gated integration tests (`test_container.py`, `test_create_account.py`)
- [x] Local PLC directory on a shared Docker network — no public internet dependency (pulled forward from v1.0.0)
- [x] `plc_mode` parameter: `"mock"` (default, in-memory PLC) or `"real"` (Postgres-backed PLC)

**Outcomes:**
- `with PDSContainer() as pds:` boots a real PDS and tears it down
- `pds.create_account("alice.test")` returns an `Account` with `did`, `handle`, and `access_jwt`
- Downstream consumers can write integration tests against a live PDS
- Tests that require Docker are skipped gracefully in environments without it
- DID registration is fully local — tests work in firewalled and air-gapped environments

---

## v0.2.0 — XRPC Ergonomics (Complete)

**Theme:** Low-level XRPC access and record operations.

- [x] `PDSContainer.xrpc_get(method, params, auth)` — authenticated GET with JSON response
- [x] `PDSContainer.xrpc_post(method, data, auth, *, content, content_type)` — authenticated POST with JSON and raw byte payloads
- [x] `PDSContainer.health()` — convenience one-liner
- [x] `Account.create_record`, `get_record`, `list_records`, `delete_record`
- [x] `Account.put_record`, `upload_blob`, `strong_ref`, `refresh_session`
- [x] Typed `XrpcError` with `method`, `status_code`, `error`, `message` attributes
- [x] `create_account` refactored to use `xrpc_post` — failures now raise `XrpcError`
- [x] Integration tests for XRPC methods (`test_xrpc.py`) and record operations (`test_records.py`)

**Outcomes:**
- Downstream SDKs can delegate raw XRPC calls to testcontainers-atproto
- Full CRUD lifecycle on ATP records available from `Account`
- Error responses are structured and pattern-matchable
- Blob upload supported via keyword-only `content`/`content_type` parameters on `xrpc_post`

---

## v0.3.0 — Firehose Subscription (Complete)

**Theme:** Observe repository events in real time.

- [x] `FirehoseSubscription` — WebSocket client for `com.atproto.sync.subscribeRepos` with CBOR frame decoding via `cbor2`
- [x] `events(timeout)` — async generator yielding decoded `{"header": {...}, "body": {...}}` events
- [x] `collect(count, timeout)` — synchronous helper bridging async-to-sync via `asyncio.run()` for standard pytest tests
- [x] `close()` — graceful WebSocket teardown
- [x] `FirehoseSubscription` context manager support (sync and async)
- [x] `PDSContainer.subscribe(cursor)` — factory method returning a `FirehoseSubscription`
- [x] Guarded import: `websockets` and `cbor2` checked at module level; actionable `ImportError` when the `firehose` extra isn't installed
- [x] `FirehoseSubscription` added to top-level package exports
- [x] Integration tests: publish a record, assert the firehose emits a matching commit (`test_firehose.py`)

**Outcomes:**
- Indexer and feed-generator tests can verify event streams end-to-end
- Synchronous `collect()` keeps test code simple — no async boilerplate needed
- Optional dependency boundary cleanly enforced at both the factory and method level

---

## v0.4.0 — Email Verification + Password Reset (Planned)

**Theme:** Hermetic email capture for account lifecycle flows.

Today, `PDS_DEV_MODE=true` silently bypasses email verification. Production PDS instances require verified email for account activation and use email for password reset. This release adds a local SMTP server so tests can exercise these flows end-to-end without touching real email infrastructure.

- [ ] Mailpit companion container on the shared Docker network — lightweight SMTP server with an HTTP API for querying captured messages
- [ ] `email_mode` parameter on `PDSContainer`: `"none"` (default, current behavior) or `"capture"` (starts Mailpit, configures `PDS_EMAIL_SMTP_URL` and `PDS_EMAIL_FROM_ADDRESS`)
- [ ] PDS configured with `PDS_DEV_MODE=false` when `email_mode="capture"` — email verification enforced, matching production behavior
- [ ] `PDSContainer.mailbox(address=)` — query captured emails, optionally filtered by recipient address
- [ ] `PDSContainer.await_email(address, timeout)` — poll for an email matching the given address, returning the message when it arrives
- [ ] Email-verified account activation flow: `create_account` → capture verification email → extract token → confirm email via XRPC
- [ ] `Account.request_password_reset()` — trigger `com.atproto.server.requestPasswordReset`
- [ ] Password reset flow: request reset → capture email → extract token → complete reset via `com.atproto.server.resetPassword`
- [ ] Mailpit container health-check wait strategy
- [ ] Mailpit teardown in `PDSContainer.stop()`
- [ ] Integration tests: full activation flow, full password reset flow, mailbox filtering, timeout behavior

**Outcomes:**
- Account onboarding tests can verify the complete activation path — from sign-up through email verification to authenticated session
- Password reset tests can exercise the full security-critical flow without mocking
- `email_mode="none"` preserves the current fast path for tests that don't need email
- The hermeticity pattern established by the local PLC directory extends to email — no external SMTP dependency

---

## v0.5.0 — Account Lifecycle + Admin Operations (Planned)

**Theme:** Account state changes and moderation primitives.

Production apps must handle accounts that are deactivated, deleted, or taken down by moderators. Today there's no ergonomic way to test what happens when an account disappears or changes state. This release adds account lifecycle methods and admin API access.

- [ ] `Account.deactivate()` — call `com.atproto.server.deactivateAccount`
- [ ] `Account.delete(password)` — call `com.atproto.server.deleteAccount` (requires email token when `email_mode="capture"`)
- [ ] `PDSContainer.admin_get(method, params)` — authenticated admin XRPC query using HTTP Basic auth
- [ ] `PDSContainer.admin_post(method, data)` — authenticated admin XRPC procedure using HTTP Basic auth
- [ ] Admin takedown: disable an account via `com.atproto.admin.updateSubjectStatus`
- [ ] Admin account status query: `com.atproto.admin.getSubjectStatus`
- [ ] Admin invite code management: create and revoke invite codes programmatically
- [ ] Integration tests: deactivate → verify inaccessible, delete → verify gone, takedown → verify blocked, lifecycle round-trips

**Outcomes:**
- Feed generators and indexers can test their behavior when accounts are removed from the network
- Moderation tool developers can test admin actions against a real PDS
- Client apps can verify graceful degradation for deactivated and deleted profiles

---

## v0.6.0 — Repo Sync (Planned)

**Theme:** Repository export and blob retrieval for data consumption pipelines.

The firehose (v0.3.0) provides incremental event notification. Repo sync provides the complementary full-state retrieval path that relays and indexers use for initial backfill and recovery. Together they cover both data consumption patterns in AT Protocol.

- [ ] `Account.export_repo()` — call `com.atproto.sync.getRepo`, return raw CAR bytes
- [ ] `Account.get_blob(cid)` — call `com.atproto.sync.getBlob`, return raw blob bytes
- [ ] Optional CAR parsing utility: decode CAR bytes into blocks and root CID (guarded behind an extra or lightweight built-in)
- [ ] `PDSContainer.sync_get(method, params)` — low-level sync endpoint access for methods not covered by helpers
- [ ] Integration tests: create records → export repo → verify CAR contains expected blocks; upload blob → retrieve blob → verify round-trip; sync endpoint coverage

**Outcomes:**
- Relay and indexer developers can test full backfill pipelines: `getRepo` → parse CAR → verify records
- Blob storage integrations can verify round-trip fidelity
- The two data consumption patterns (firehose for incremental, sync for full-state) are both testable in isolation

---

## v0.7.0 — Declarative Seeding (Planned)

**Theme:** Reduce boilerplate by describing test state declaratively.

Integration tests that need a populated PDS — multiple accounts, posts, follows, likes, blobs — repeat dozens of imperative API calls before the first assertion. This release introduces a seeding API that lets test authors describe the desired world state and materialize it in one call.

- [ ] `Seed` builder class — fluent API for declaring accounts, records, social graph edges (follows, likes, reposts), and blobs
- [ ] `Seed.apply()` — materialize the declared state against a running `PDSContainer`, returning a `World` object
- [ ] `World` result object — maps handles to `Account` instances and ordered lists of `RecordRef`s for cross-account assertions
- [ ] Dependency-ordered creation: accounts first, then records, then interactions that reference other accounts' records
- [ ] Cross-account references: `like("alice.test", 0)` resolves to Alice's first record URI automatically
- [ ] Dict-based alternative: `pds.seed({...})` accepting a plain dict/JSON description for data-driven and YAML-loaded fixtures
- [ ] Support for custom Lexicon collections — not limited to `app.bsky.*`
- [ ] Integration tests: seed a multi-account social graph, verify record counts, verify cross-account references resolve correctly

**Outcomes:**
- Test setup for feed generators drops from 50+ lines of imperative calls to a single declarative block
- Indexer and relay tests can spin up reproducible, complex PDS states without fragile setup code
- SDK authors can define reusable seed fixtures across their test suites
- CI pipelines benefit from deterministic, self-documenting test data

---

## v1.0.0 — Hermeticity + Federation (Planned)

**Theme:** Fully isolated test environments.

- [x] ~~Mock PLC directory~~ — delivered in v0.1.0 (`plc_mode="mock"` and `plc_mode="real"`)
- [ ] `did:web` account support — skip PLC round-trip for faster container boot
- [ ] `pds_pair` federation validation — two containers resolving each other's records via shared PLC
- [ ] API audit and stability commitment

**Outcomes:**
- Federation scenarios testable with the `pds_pair` fixture
- Stable API surface with semantic versioning commitment

---

## Post-1.0 Vision

| Feature | Notes |
|---------|-------|
| Labeler testing | Ephemeral labeler service alongside PDS |
| Feed generator harness | Test custom feed algorithms against a seeded PDS |
| Relay / BGS container | Multi-relay topologies for indexer stress tests |
| Lexicon scaffolding | Generate test fixtures from Lexicon schema definitions |
| Performance profiling | Container boot benchmarks across PDS versions |

---

## Guiding Principle

> "If it runs in production, it should be testable in isolation."
