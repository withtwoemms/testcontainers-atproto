# testcontainers-atproto User's Guide

Spin up ephemeral [PDS](./glossary.md) instances in your Python test suite. [Lexicon](./glossary.md)-agnostic — works with any application built on [AT Protocol](./glossary.md), not just Bluesky.

---

## Table of Contents

1. [Installation](#installation)
2. [Architecture](#architecture)
3. [Container Lifecycle](#container-lifecycle)
4. [Account Management](#account-management)
5. [Record Operations](#record-operations)
6. [Raw XRPC Access](#raw-xrpc-access)
7. [Declarative Seeding](#declarative-seeding)
8. [Firehose Subscription](#firehose-subscription)
9. [Email Verification and Password Reset](#email-verification-and-password-reset)
10. [Pytest Fixtures](#pytest-fixtures)
11. [Error Handling](#error-handling)
12. [API Reference](#api-reference)

---

## Installation

```bash
pip install testcontainers-atproto
```

Requires Python 3.10+ and a running Docker daemon.

### Extras

| Extra | What it adds |
|-------|-------------|
| `testcontainers-atproto[firehose]` | `websockets`, `cbor2` for firehose subscription |
| `testcontainers-atproto[sdk]` | `atproto` (MarshalX SDK) for high-level record ops |
| `testcontainers-atproto[all]` | Both of the above |

---

## Architecture

All containers run on a shared Docker network. The [PDS](./glossary.md) registers [DIDs](./glossary.md) with a local [PLC](./glossary.md) directory — no public internet required. Optional companion containers (Postgres, Mailpit) are added based on constructor parameters.

```
                        ┌─────────────────────────────────────────────────┐
                        │            Docker Network (plc_network)         │
                        │                                                 │
                        │  ┌─────────────┐       ┌─────────────────────┐  │
                        │  │  Postgres   │       │   PLC Directory     │  │
                        │  │  (plcdb)    │       │   (plc)             │  │
                        │  │  :5432      │◄──────│   :2582             │  │
                        │  │             │  DB   │                     │  │
                        │  │  real mode  │       │  DID registration   │  │
                        │  │  only       │       │                     │  │
                        │  └─────────────┘       └────────▲────────────┘  │
                        │                                 │               │
                        │                          DID resolve            │
                        │                                 │               │
                        │  ┌─────────────┐       ┌────────┴────────────┐  │
                        │  │  Mailpit    │       │   PDS               │  │
                        │  │  (mailpit)  │       │   :3000             │  │
                        │  │             │◄──────│                     │  │
                        │  │  SMTP :1025 │ SMTP  │  XRPC endpoints     │  │
                        │  │  API  :8025 │       │  /xrpc/_health      │  │
                        │  │             │       │  /xrpc/com.atproto  │  │
                        │  │  capture    │       │                     │  │
                        │  │  mode only  │       │  tmpfs /pds         │  │
                        │  └──────┬──────┘       └────────┬────────────┘  │
                        │         │                       │               │
                        └─────────┼───────────────────────┼───────────────┘
                                  │                       │
                          mapped  │               mapped  │
                          port    │               port    │
                                  │                       │
                     ┌────────────▼───────────────────────▼────────────┐
                     │                  Host Machine                   │
                     │                                                 │
                     │   pds.mailbox()  ──►  GET /api/v1/messages      │
                     │   pds.await_email()   GET /api/v1/search        │
                     │                                                 │
                     │   pds.base_url   ──►  http://localhost:<port>   │
                     │   pds.create_account()                          │
                     │   account.request_email_confirmation()          │
                     │   account.confirm_email(token)                  │
                     │   account.request_password_reset()              │
                     │   account.reset_password(token, new_password)   │
                     └─────────────────────────────────────────────────┘
```

### Container Modes

```
PDSContainer()                          PLC ──► PDS
                                        (2 containers)

PDSContainer(plc_mode="real")           Postgres ──► PLC ──► PDS
                                        (3 containers)

PDSContainer(email_mode="capture")      PLC ──► PDS ──► Mailpit
                                        (3 containers)

PDSContainer(plc_mode="real",           Postgres ──► PLC ──► PDS ──► Mailpit
             email_mode="capture")      (4 containers)
```

---

## Container Lifecycle

`PDSContainer` wraps `ghcr.io/bluesky-social/pds` with auto-generated secrets and a health check against `GET /xrpc/_health`.

### Basic usage

```python
from testcontainers_atproto import PDSContainer

with PDSContainer() as pds:
    print(pds.base_url)        # http://localhost:<port>
    print(pds.admin_password)  # auto-generated hex string
    print(pds.health())        # {"version": "..."}
```

### Constructor parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `image` | `"ghcr.io/bluesky-social/pds:0.4"` | Docker image for the [PDS](./glossary.md) |
| `hostname` | `"localhost"` | PDS hostname |
| `admin_password` | auto-generated | Admin password for the PDS |
| `plc_mode` | `"mock"` | `"mock"` for in-memory [PLC](./glossary.md), `"real"` for Postgres-backed |
| `email_mode` | `"none"` | `"none"` bypasses email, `"capture"` starts Mailpit |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `base_url` | `str` | [XRPC](./glossary.md) base URL (e.g. `http://localhost:53421`) |
| `admin_password` | `str` | Admin password for this instance |
| `host` | `str` | Container hostname as seen from the host machine |
| `port` | `int` | Mapped port (3000 inside, dynamic outside) |
| `email_mode` | `str` | `"none"` or `"capture"` |

### PLC modes

The default `"mock"` mode uses an in-memory [PLC](./glossary.md) directory — fast, no Postgres. For production parity, `"real"` adds a Postgres-backed PLC:

```python
with PDSContainer(plc_mode="real") as pds:
    account = pds.create_account("alice.test")
```

---

## Account Management

### Creating accounts

Handles must end in `.test` (matching `PDS_SERVICE_HANDLE_DOMAINS`):

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")
    print(alice.did)     # did:plc:...
    print(alice.handle)  # alice.test
    print(alice.email)   # alice-test@test.invalid

    # With explicit email and password
    bob = pds.create_account(
        "bob.test",
        email="bob@example.test",
        password="s3cret",
    )
```

`create_account` generates an invite code via the admin API, then calls `com.atproto.server.createAccount`. The returned `Account` holds [JWTs](./glossary.md) for authenticated requests.

### Account properties

| Property | Type | Description |
|----------|------|-------------|
| `did` | `str` | [DID](./glossary.md) (e.g. `did:plc:abc123`) |
| `handle` | `str` | Handle (e.g. `alice.test`) |
| `access_jwt` | `str` | Access [JWT](./glossary.md) for authenticated requests |
| `refresh_jwt` | `str` | Refresh [JWT](./glossary.md) for token rotation |
| `email` | `str` | Email address used during creation |

All properties are read-only.

### Session refresh

```python
alice.refresh_session()
# alice.access_jwt and alice.refresh_jwt are now updated
```

---

## Record Operations

All record methods operate on the account's repository via [XRPC](./glossary.md) procedures.

### Create

```python
ref = alice.create_record("app.bsky.feed.post", {
    "$type": "app.bsky.feed.post",
    "text": "hello from testcontainers",
    "createdAt": "2026-01-01T00:00:00Z",
})
print(ref.uri)   # at://did:plc:.../app.bsky.feed.post/...
print(ref.cid)   # content hash
print(ref.rkey)  # record key extracted from URI
```

Returns a `RecordRef` with `uri`, `cid`, `did`, `collection`, and `rkey` properties plus an `as_strong_ref()` method.

### Read

```python
record = alice.get_record("app.bsky.feed.post", ref.rkey)
```

### List

```python
records = alice.list_records("app.bsky.feed.post", limit=50)
```

### Update (upsert)

```python
new_ref = alice.put_record("app.bsky.feed.post", ref.rkey, {
    "$type": "app.bsky.feed.post",
    "text": "updated text",
    "createdAt": "2026-01-01T00:00:00Z",
})
```

### Delete

```python
alice.delete_record("app.bsky.feed.post", ref.rkey)
```

### Blob upload

```python
blob = alice.upload_blob(b"\x89PNG...", "image/png")
```

### Strong reference

```python
strong = alice.strong_ref("app.bsky.feed.post", ref.rkey)
# {"uri": "at://...", "cid": "baf..."}
```

---

## Raw XRPC Access

For [XRPC](./glossary.md) methods not covered by helpers, use `xrpc_get` and `xrpc_post` directly. Methods are identified by [NSIDs](./glossary.md).

### Query (GET)

```python
session = pds.xrpc_get(
    "com.atproto.server.getSession",
    auth=alice.access_jwt,
)
```

### Procedure (POST)

```python
# JSON payload
resp = pds.xrpc_post(
    "com.atproto.repo.createRecord",
    data={"repo": alice.did, "collection": "app.bsky.feed.post", ...},
    auth=alice.access_jwt,
)

# Raw byte payload (e.g. blob upload)
resp = pds.xrpc_post(
    "com.atproto.repo.uploadBlob",
    auth=alice.access_jwt,
    content=image_bytes,
    content_type="image/png",
)
```

### Health check

```python
pds.health()  # {"version": "..."}
```

---

## Declarative Seeding

Describe the world, materialize it in one call — no boilerplate account/record setup.

### Fluent API

```python
from testcontainers_atproto import PDSContainer, Seed

with PDSContainer() as pds:
    world = (
        Seed(pds)
        .account("alice.test")
            .post("Hello from Alice")
            .post("Another post")
        .account("bob.test")
            .post("Bob's first post")
            .follow("alice.test")
            .like("alice.test", 0)   # like Alice's first post
        .apply()
    )

    alice = world.accounts["alice.test"]
    bob = world.accounts["bob.test"]
    assert len(world.records["alice.test"]) == 2
```

### Builder methods

| Method | Description |
|--------|-------------|
| `.account(handle)` | Declare an account (or switch context to an existing one) |
| `.post(text)` | Add a `app.bsky.feed.post` record |
| `.record(collection, record, rkey=)` | Add an arbitrary record with any [Lexicon](./glossary.md) collection |
| `.follow(target_handle)` | Current account follows target |
| `.like(target_handle, record_index)` | Current account likes target's record |
| `.repost(target_handle, record_index)` | Current account reposts target's record |
| `.blob(data, mime_type=)` | Upload a blob under the current account |
| `.apply()` | Materialize all declarations, return a `World` |

Execution order: accounts first, then blobs and records, then interactions (follows, likes, reposts).

### World object

`World` is a frozen dataclass returned by `.apply()`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `accounts` | `dict[str, Account]` | Handle to `Account` mapping |
| `records` | `dict[str, list[RecordRef]]` | Handle to ordered `RecordRef` list |
| `blobs` | `dict[str, list[dict]]` | Handle to ordered blob reference list |

### Placeholders

Embed cross-account references that resolve at `apply()` time:

```python
world = (
    Seed(pds)
    .account("alice.test")
        .record("com.example.project", {
            "$type": "com.example.project",
            "name": "My Project",
        })
    .account("bob.test")
        .record("com.example.review", {
            "$type": "com.example.review",
            "reviewer": Seed.did("bob.test"),       # resolves to bob's DID
            "project": Seed.ref("alice.test", 0),   # resolves to alice's first record
        })
    .apply()
)
```

| Placeholder | Resolves to |
|-------------|-------------|
| `Seed.did(handle)` | The account's [DID](./glossary.md) string |
| `Seed.ref(handle, index)` | A `{uri, cid}` strong ref for the account's Nth record |

Placeholders work at any nesting depth in record dicts and lists.

### Account revisiting

Call `.account(handle)` again to switch back to an already-declared account. No duplicate is created — records are appended under the existing account:

```python
world = (
    Seed(pds)
    .account("alice.test")
        .post("alice first")
    .account("bob.test")
        .post("bob replies")
    .account("alice.test")    # switches back, doesn't duplicate
        .post("alice continues")
    .apply()
)
```

### Dict-based seeding

For data-driven or YAML-loaded fixtures:

```python
world = pds.seed({
    "accounts": [
        {"handle": "alice.test", "posts": ["Hello from Alice"]},
        {"handle": "bob.test", "follows": ["alice.test"]},
    ],
})
```

---

## Firehose Subscription

Observe real-time repository events via `com.atproto.sync.subscribeRepos`. Events are [CBOR](./glossary.md)-encoded frames decoded into Python dicts.

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")
    alice.create_record("app.bsky.feed.post", {
        "$type": "app.bsky.feed.post",
        "text": "hello firehose",
        "createdAt": "2026-01-01T00:00:00Z",
    })

    sub = pds.subscribe()
    events = sub.collect(count=10, timeout=5.0)

    commits = [e for e in events if e["header"].get("t") == "#commit"]
    print(commits[-1]["body"]["ops"])  # [{"action": "create", ...}]
```

Requires the firehose extra: `pip install testcontainers-atproto[firehose]`

### FirehoseSubscription methods

| Method | Description |
|--------|-------------|
| `collect(count, timeout)` | Synchronous — collect up to `count` events or until `timeout` |
| `events(timeout)` | Async generator yielding decoded events |
| `close()` | Close the WebSocket connection |

Supports both sync (`with sub:`) and async (`async with sub:`) context managers.

---

## Email Verification and Password Reset

Test email verification and password reset flows with a local Mailpit SMTP server. When `email_mode="capture"`, the [PDS](./glossary.md) sends real emails through Mailpit, and test code retrieves them via Mailpit's HTTP API.

### Enabling capture mode

```python
with PDSContainer(email_mode="capture") as pds:
    alice = pds.create_account("alice.test")
    assert pds.email_mode == "capture"
```

When `email_mode="none"` (the default), no Mailpit container is started and email verification is bypassed.

### Retrieving emails

```python
# All messages
messages = pds.mailbox()

# Filtered by recipient
messages = pds.mailbox("alice-test@test.invalid")

# Poll until an email arrives (with timeout)
message = pds.await_email("alice-test@test.invalid", timeout=10.0)
```

| Method | Description |
|--------|-------------|
| `mailbox(address=)` | Query captured emails, optionally filtered by recipient |
| `await_email(address, timeout=, poll_interval=)` | Poll until an email arrives, raise `TimeoutError` if not |

### Email verification flow

```python
with PDSContainer(email_mode="capture") as pds:
    alice = pds.create_account("alice.test")

    # 1. Request verification email
    alice.request_email_confirmation()

    # 2. Retrieve it from Mailpit
    message = pds.await_email(alice.email)

    # 3. Extract the token from the email body (PDS-version-dependent format)
    token = extract_token(message)  # your extraction logic

    # 4. Confirm
    alice.confirm_email(token)

    # 5. Verify
    session = pds.xrpc_get("com.atproto.server.getSession", auth=alice.access_jwt)
    assert session["emailConfirmed"] is True
```

### Password reset flow

```python
with PDSContainer(email_mode="capture") as pds:
    alice = pds.create_account("alice.test", password="original")

    # (email must be confirmed first)
    # ... confirm email as above ...

    # 1. Request reset
    alice.request_password_reset()

    # 2. Retrieve reset email
    message = pds.await_email(alice.email)

    # 3. Extract token and reset
    token = extract_token(message)
    alice.reset_password(token, "new-password")

    # 4. Login with new password
    resp = pds.xrpc_post("com.atproto.server.createSession", data={
        "identifier": alice.handle,
        "password": "new-password",
    })
    assert resp["did"] == alice.did
```

### Account email methods

| Method | Auth required | Description |
|--------|---------------|-------------|
| `request_email_confirmation()` | Yes | Send verification email |
| `confirm_email(token)` | Yes | Confirm email with token from the email |
| `request_password_reset()` | No | Send password reset email |
| `reset_password(token, new_password)` | No | Complete reset with token from the email |

Token extraction is the test author's responsibility. The PDS email format is version-dependent — tokens typically appear as `XXXXX-XXXXX` codes in the email body or as `?code=...` in URLs.

---

## Pytest Fixtures

After installing the package, these fixtures are available automatically via the `pytest11` entry point — no imports needed:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `pds` | function | Fresh [PDS](./glossary.md) instance per test |
| `pds_module` | module | Shared PDS instance within a test module |
| `pds_pair` | function | Two PDS instances for federation testing |
| `pds_image` | session | PDS image tag (override via `ATP_PDS_IMAGE` env var) |

```python
def test_create_account(pds):
    account = pds.create_account("bob.test")
    assert account.did.startswith("did:plc:")
```

Override the PDS image:

```bash
ATP_PDS_IMAGE=ghcr.io/bluesky-social/pds:0.5 pytest
```

---

## Error Handling

[XRPC](./glossary.md) failures raise `XrpcError` with structured fields:

```python
from testcontainers_atproto import PDSContainer, XrpcError

with PDSContainer() as pds:
    try:
        pds.create_account("alice.invalid")
    except XrpcError as e:
        print(e.method)       # "com.atproto.server.createAccount"
        print(e.status_code)  # 400
        print(e.error)        # "InvalidHandle"
        print(e.message)      # human-readable detail
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `method` | `str` | The [NSID](./glossary.md) that failed |
| `status_code` | `int` | HTTP status code |
| `error` | `str` | XRPC error name |
| `message` | `str` | Human-readable error detail |

---

## API Reference

### Classes

| Class | Module | Description |
|-------|--------|-------------|
| `PDSContainer` | `container` | Ephemeral [PDS](./glossary.md) with companion containers |
| `Account` | `account` | Authenticated [ATP](./glossary.md) account with record and email operations |
| `RecordRef` | `ref` | Frozen dataclass referencing a created/updated record (AT URI + [CID](./glossary.md)) |
| `Seed` | `seed` | Fluent builder for declarative PDS state |
| `World` | `world` | Frozen dataclass of materialized seed state |
| `FirehoseSubscription` | `firehose` | WebSocket client for `subscribeRepos` with [CBOR](./glossary.md) decoding |
| `XrpcError` | `errors` | Structured exception for [XRPC](./glossary.md) failures |

All classes are exported from `testcontainers_atproto`:

```python
from testcontainers_atproto import (
    PDSContainer,
    Account,
    RecordRef,
    Seed,
    World,
    FirehoseSubscription,
    XrpcError,
)
```

### RecordRef

Frozen dataclass returned by `create_record` and `put_record`:

| Member | Type | Description |
|--------|------|-------------|
| `uri` | `str` | AT URI (e.g. `at://did:plc:abc/app.bsky.feed.post/rkey`) |
| `cid` | `str` | [Content identifier](./glossary.md) (hash) |
| `did` | `str` (property) | [DID](./glossary.md) extracted from URI |
| `collection` | `str` (property) | Collection [NSID](./glossary.md) extracted from URI |
| `rkey` | `str` (property) | Record key extracted from URI |
| `as_strong_ref()` | `dict` | Returns `{"uri": ..., "cid": ...}` |

---

## Glossary

See [glossary.md](./glossary.md) for definitions of PDS, DID, PLC, XRPC, Lexicon, NSID, JWT, CID, CBOR, MST, and other AT Protocol terms used throughout this guide.
