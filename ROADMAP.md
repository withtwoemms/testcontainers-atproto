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
| v0.1.0 | Container Lifecycle + Account Creation | Up Next |
| v0.2.0 | XRPC Ergonomics | Planned |
| v0.3.0 | Firehose Subscription | Planned |
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

## v0.1.0 — Container Lifecycle + Account Creation (Up Next)

**Theme:** A running PDS you can create accounts on.

- [ ] `PDSContainer` subclasses `DockerContainer` with auto-generated secrets
- [ ] Container environment: `PDS_HOSTNAME`, `PDS_PORT`, `PDS_ADMIN_PASSWORD`, `PDS_JWT_SECRET`, `PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX`, and friends
- [ ] Health-check wait in `__enter__` (poll `GET /xrpc/_health` until HTTP 200)
- [ ] Container teardown in `__exit__`
- [ ] `host`, `port`, `base_url`, and `admin_password` properties
- [ ] `create_account(handle)` — invite code generation + account creation via XRPC
- [ ] `Account.access_jwt` and `Account.refresh_jwt` public properties
- [ ] Handle-domain resolution: determine the right `PDS_SERVICE_HANDLE_DOMAINS` for test handles
- [ ] Docker-gated integration tests (`test_container.py`, `test_create_account.py`)

**Outcomes:**
- `with PDSContainer() as pds:` boots a real PDS and tears it down
- `pds.create_account("alice.test")` returns an `Account` with `did`, `handle`, and `access_jwt`
- Downstream consumers can write integration tests against a live PDS
- Tests that require Docker are skipped gracefully in environments without it

---

## v0.2.0 — XRPC Ergonomics (Planned)

**Theme:** Low-level XRPC access and record operations.

- [ ] `PDSContainer.xrpc_get(method, params, auth)` — authenticated GET with JSON response
- [ ] `PDSContainer.xrpc_post(method, body, auth)` — authenticated POST with JSON response
- [ ] `PDSContainer.health()` — convenience one-liner
- [ ] `Account.create_record`, `get_record`, `list_records`, `delete_record`
- [ ] `Account.put_record`, `upload_blob`, `strong_ref`, `refresh_session`
- [ ] Typed `XrpcError` hierarchy for structured error handling

**Outcomes:**
- Downstream SDKs can delegate raw XRPC calls to testcontainers-atproto
- Full CRUD lifecycle on ATP records available from `Account`
- Error responses are structured and pattern-matchable

---

## v0.3.0 — Firehose Subscription (Planned)

**Theme:** Observe repository events in real time.

- [ ] `FirehoseSubscription` — WebSocket client for `com.atproto.sync.subscribeRepos`
- [ ] `events(timeout)` — async generator yielding CBOR-decoded commit events
- [ ] `collect(count, timeout)` — synchronous helper for test assertions
- [ ] `close()` — graceful WebSocket teardown
- [ ] `PDSContainer.subscribe(cursor)` — factory method returning a `FirehoseSubscription`
- [ ] Guarded import: actionable `ImportError` if the `firehose` extra isn't installed
- [ ] Integration tests: publish a record, assert the firehose emits a matching commit

**Outcomes:**
- Indexer and feed-generator tests can verify event streams end-to-end
- Synchronous `collect()` keeps test code simple
- Optional dependency boundary cleanly enforced

---

## v1.0.0 — Hermeticity + Federation (Planned)

**Theme:** Fully isolated test environments.

- [ ] Mock PLC directory — local PLC-compatible service replacing `https://plc.directory`
- [ ] `did:web` account support — skip PLC round-trip for faster container boot
- [ ] `pds_pair` federation validation — two containers resolving each other's records
- [ ] API audit and stability commitment

**Outcomes:**
- Zero external network dependencies during test runs
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
