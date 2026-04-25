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
9. [Repo Sync](#repo-sync)
10. [OAuth DPoP Authentication](#oauth-dpop-authentication)
11. [Email Verification and Password Reset](#email-verification-and-password-reset)
12. [Account Lifecycle and Admin Operations](#account-lifecycle-and-admin-operations)
13. [Federation Testing](#federation-testing)
14. [Rate Limit Simulation](#rate-limit-simulation)
15. [Pytest Fixtures](#pytest-fixtures)
16. [Error Handling](#error-handling)
17. [API Reference](#api-reference)

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
| `testcontainers-atproto[sync]` | `cbor2` for CAR file parsing |
| `testcontainers-atproto[sdk]` | `atproto` (MarshalX SDK) for high-level record ops |
| `testcontainers-atproto[oauth]` | `cryptography`, `PyJWT` for OAuth DPoP flow testing |
| `testcontainers-atproto[all]` | All of the above |

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

PDSContainer(rate_limits=True)          PLC ──► PDS (rate limiting enabled)
                                        (2 containers)
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
| `rate_limits` | `False` | `True` enables PDS rate limiting with bypass key for internal calls |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `base_url` | `str` | [XRPC](./glossary.md) base URL (e.g. `http://localhost:53421`) |
| `admin_password` | `str` | Admin password for this instance |
| `host` | `str` | Container hostname as seen from the host machine |
| `port` | `int` | Mapped port (3000 inside, dynamic outside) |
| `email_mode` | `str` | `"none"` or `"capture"` |
| `bypass_key` | `str \| None` | Rate limit bypass key (set when `rate_limits=True`) |

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
| `password` | `str` | Password used during creation (empty if auto-generated without explicit `password=`) |

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

## Repo Sync

Export repositories and retrieve blobs for relay and indexer testing. The firehose (see above) provides incremental event notification; repo sync provides the complementary full-state retrieval path used for initial backfill and recovery.

### Exporting a repository

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")
    alice.create_record("app.bsky.feed.post", {
        "$type": "app.bsky.feed.post",
        "text": "sync test",
        "createdAt": "2026-01-01T00:00:00Z",
    })

    # Export full repository as CAR bytes
    car_bytes = alice.export_repo()
```

Returns the raw binary CAR (Content Addressable aRchive) response from `com.atproto.sync.getRepo`.

### Retrieving blobs

```python
    blob_ref = alice.upload_blob(b"test data", "image/png")
    cid = blob_ref["ref"]["$link"]

    # Retrieve by CID
    blob_data = alice.get_blob(cid)
    assert blob_data == b"test data"
```

### Parsing CAR files

The optional `parse_car` utility decodes CAR v1 archives into structured Python objects. Requires `cbor2` (available via the `sync` or `firehose` extra).

```python
from testcontainers_atproto import parse_car

car = parse_car(car_bytes)
print(car.version)       # 1
print(len(car.roots))    # number of root CIDs
print(len(car.blocks))   # number of blocks
```

Install with: `pip install testcontainers-atproto[sync]`

### Low-level sync access

For sync endpoints not covered by helpers, use `sync_get` directly. It returns raw bytes instead of JSON.

```python
car_bytes = pds.sync_get(
    "com.atproto.sync.getRepo",
    params={"did": alice.did},
)
```

### Account sync methods

| Method | Description |
|--------|-------------|
| `export_repo()` | Export repository as raw CAR bytes |
| `get_blob(cid)` | Retrieve a blob by CID |

### Container sync methods

| Method | Description |
|--------|-------------|
| `sync_get(method, params=, auth=)` | Raw sync endpoint query returning bytes |

### CAR parsing types

| Type | Description |
|------|-------------|
| `CarFile` | Frozen dataclass: `version`, `roots`, `blocks` |
| `CarBlock` | Frozen dataclass: `cid` (bytes), `data` (bytes) |
| `parse_car(data)` | Parse CAR v1 bytes into a `CarFile` |

---

## OAuth DPoP Authentication

Test OAuth client implementations end-to-end with [DPoP](./glossary.md) (Demonstration of Proof-of-Possession) bound tokens. This is the modern AT Protocol authentication flow, replacing legacy Bearer [JWT](./glossary.md) sessions.

Requires the oauth extra: `pip install testcontainers-atproto[oauth]`

### Quick start

```python
from testcontainers_atproto import PDSContainer

with PDSContainer() as pds:
    alice = pds.create_account("alice.test", password="hunter2")
    client, tokens = pds.oauth_authenticate(alice)

    # DPoP-authenticated XRPC calls
    resp = client.xrpc_get(
        "com.atproto.repo.describeRepo",
        tokens.access_token,
        params={"repo": alice.did},
    )
    assert resp["handle"] == "alice.test"
```

`oauth_authenticate` runs the full OAuth flow: Pushed Authorization Request (PAR), programmatic sign-in, consent, and token exchange. It returns an `OAuthClient` (for making DPoP-authenticated requests) and `OAuthTokens` (the token response).

### How the flow works

The AT Protocol OAuth flow with DPoP has these steps:

1. **PAR** — Push an authorization request to the PDS, receiving a `request_uri`
2. **Authorization page** — Load the page to get session cookies (CSRF token, device ID)
3. **Sign-in** — POST credentials to the PDS authorization API
4. **Consent** — POST consent approval, receiving a redirect URL with an authorization code
5. **Token exchange** — Exchange the code + PKCE verifier for DPoP-bound tokens
6. **Authenticated requests** — Use `Authorization: DPoP <token>` + `DPoP: <proof>` headers

All steps are handled automatically by `OAuthClient`. The DPoP proof includes the HTTP method and target URL, binding each token to a specific key pair.

### Step-by-step flow

For testing individual phases or error conditions at each step:

```python
from testcontainers_atproto import DPoPKey, OAuthClient, PKCEChallenge, PDSContainer

with PDSContainer() as pds:
    alice = pds.create_account("alice.test", password="hunter2")

    # Create client with explicit key
    dpop_key = DPoPKey.generate()
    client = pds.oauth_client(dpop_key=dpop_key)

    # 1. PAR
    pkce = PKCEChallenge.generate()
    request_uri = client.pushed_authorization_request(
        pkce, state="my-state", login_hint="alice.test",
    )

    # 2-4. Sign-in + consent → authorization code
    code = client.authorize(request_uri, "alice.test", "hunter2")

    # 5. Token exchange
    tokens = client.token_exchange(code, pkce)
    assert tokens.token_type == "DPoP"
    assert tokens.sub == alice.did
```

### DPoP-authenticated XRPC calls

After obtaining tokens, use the client for authenticated requests:

```python
    # Read
    repo = client.xrpc_get(
        "com.atproto.repo.describeRepo",
        tokens.access_token,
        params={"repo": alice.did},
    )

    # Write
    result = client.xrpc_post(
        "com.atproto.repo.createRecord",
        tokens.access_token,
        data={
            "repo": alice.did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": "posted via OAuth DPoP",
                "createdAt": "2026-01-01T00:00:00Z",
            },
        },
    )
```

DPoP nonce negotiation and proof generation are handled automatically. Each request includes a fresh DPoP proof JWT signed with the client's key pair.

### Token refresh

```python
    new_tokens = client.refresh_tokens(tokens.refresh_token)
    assert new_tokens.access_token != tokens.access_token
    assert new_tokens.sub == alice.did

    # The new token works
    client.xrpc_get(
        "com.atproto.repo.describeRepo",
        new_tokens.access_token,
        params={"repo": alice.did},
    )
```

### Token revocation

```python
    client.revoke_token(tokens.access_token)
```

### Scopes

The default scope is `atproto transition:generic`, which grants both read and write access. You can customize the scope:

```python
    client = pds.oauth_client(scope="atproto")  # read-only
```

The `transition:generic` scope is required for write operations (record creation, updates, deletes). Without it, writes return a 403 `ScopeMissingError`.

### OAuthClient methods

| Method | Description |
|--------|-------------|
| `discover()` | Fetch OAuth authorization server metadata |
| `pushed_authorization_request(pkce, state=, login_hint=)` | Submit a PAR, return `request_uri` |
| `authorize(request_uri, username, password)` | Programmatic sign-in + consent, return authorization code |
| `token_exchange(code, pkce)` | Exchange code for tokens |
| `authenticate(username, password, state=)` | Full flow in one call (PAR + authorize + token exchange) |
| `refresh_tokens(refresh_token)` | Refresh tokens |
| `revoke_token(token)` | Revoke an access or refresh token |
| `xrpc_get(method, access_token, params=)` | DPoP-authenticated XRPC query |
| `xrpc_post(method, access_token, data=, content=, content_type=)` | DPoP-authenticated XRPC procedure |
| `dpop_get(url, access_token, params=)` | Low-level DPoP GET (takes full URL) |
| `dpop_post(url, access_token, json=, content=, content_type=)` | Low-level DPoP POST (takes full URL) |

### PDSContainer convenience methods

| Method | Description |
|--------|-------------|
| `oauth_client(dpop_key=, client_id=, scope=)` | Create an `OAuthClient` for this PDS |
| `oauth_authenticate(account, dpop_key=, scope=)` | Full OAuth flow, returns `(OAuthClient, OAuthTokens)` |

### OAuth classes

| Class | Module | Description |
|-------|--------|-------------|
| `OAuthClient` | `oauth` | OAuth DPoP flow client with XRPC helpers |
| `OAuthTokens` | `oauth` | Frozen dataclass: `access_token`, `token_type`, `refresh_token`, `scope`, `expires_in`, `sub` |
| `DPoPKey` | `oauth` | ES256 key pair with DPoP proof generation |
| `PKCEChallenge` | `oauth` | Frozen dataclass: `verifier`, `challenge` (S256) |

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

## Account Lifecycle and Admin Operations

Test what happens when accounts are deactivated, deleted, or taken down by moderators. Account lifecycle methods use Bearer JWT auth (user-level actions), while admin operations use HTTP Basic auth (server-level actions).

### Deactivate and activate

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")

    # Deactivate — account becomes inaccessible
    alice.deactivate()

    # Re-activate — access restored
    alice.activate()

    # Deactivate with a scheduled deletion date
    alice.deactivate(delete_after="2099-01-01T00:00:00Z")
    alice.activate()
```

### Check account status

```python
status = alice.check_account_status()
assert status["activated"] is True
assert status["validDid"] is True
```

The response includes: `activated`, `validDid`, `repoCommit`, `repoRev`, `repoBlocks`, `indexedRecords`, `privateStateValues`, `expectedBlobs`, `importedBlobs`.

### Delete account

Account deletion follows the same two-step pattern as password reset: request a token via email, then complete the deletion.

```python
with PDSContainer(email_mode="capture") as pds:
    alice = pds.create_account("alice.test", password="s3cret")

    # ... confirm email first ...

    # 1. Request deletion token
    alice.request_account_delete()

    # 2. Retrieve the email and extract the token
    message = pds.await_email(alice.email)
    token = extract_token(message)  # your extraction logic

    # 3. Delete permanently
    alice.delete_account("s3cret", token)
```

### Account lifecycle methods

| Method | Auth | Description |
|--------|------|-------------|
| `deactivate(delete_after=)` | Bearer JWT | Deactivate the account |
| `activate()` | Bearer JWT | Re-activate a deactivated account |
| `check_account_status()` | Bearer JWT | Query account status and repo stats |
| `request_account_delete()` | Bearer JWT | Send deletion token email |
| `delete_account(password, token)` | None | Permanently delete the account |

### Admin raw XRPC

For admin [XRPC](./glossary.md) methods not covered by helpers, use `admin_get` and `admin_post`. These work like `xrpc_get`/`xrpc_post` but use HTTP Basic auth with the admin password instead of Bearer JWT.

```python
# Query
status = pds.admin_get(
    "com.atproto.admin.getSubjectStatus",
    params={"did": alice.did},
)

# Procedure
invite = pds.admin_post(
    "com.atproto.server.createInviteCode",
    data={"useCount": 1},
)
```

### Takedown and restore

Admin moderation actions — take down an account to block access, restore to unblock:

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")

    # Takedown — blocks all access
    pds.takedown(alice)

    # Restore — unblocks access
    pds.restore(alice)

    # Query current status
    status = pds.get_subject_status(alice)
```

### Invite code management

```python
pds.disable_invite_codes(accounts=[alice.did])
pds.disable_invite_codes(codes=["invite-code-1"], accounts=[])
```

### Admin operations summary

| Method | Description |
|--------|-------------|
| `admin_get(method, params=)` | Raw admin XRPC query (HTTP Basic auth) |
| `admin_post(method, data=)` | Raw admin XRPC procedure (HTTP Basic auth) |
| `takedown(account)` | Take down an account |
| `restore(account)` | Restore a taken-down account |
| `get_subject_status(account)` | Query admin status for an account |
| `disable_invite_codes(codes=, accounts=)` | Disable invite codes |

---

## Federation Testing

The `pds_pair` fixture boots two [PDS](./glossary.md) instances sharing a single [PLC](./glossary.md) directory and Docker network. This mirrors a real federation topology where multiple PDS servers register [DIDs](./glossary.md) in a common directory.

### Architecture

```
                    ┌─────────────────────────────────────────┐
                    │        Shared Docker Network            │
                    │                                         │
                    │  ┌───────────┐    ┌───────────────────┐ │
                    │  │  PDS-A    │    │  PLC Directory    │ │
                    │  │  :3000    │───►│  :2582            │ │
                    │  │           │    │                   │ │
                    │  └───────────┘    │  DID registration │ │
                    │                   │                   │ │
                    │  ┌───────────┐    │                   │ │
                    │  │  PDS-B    │───►│                   │ │
                    │  │  :3000    │    └───────────────────┘ │
                    │  │           │                          │
                    │  └───────────┘                          │
                    └─────────────────────────────────────────┘
```

### Handle resolution vs. DID resolution

In AT Protocol, handle resolution (`resolveHandle`) is a local operation — each PDS resolves handles from its own database. Cross-PDS discovery works through DIDs:

1. Account creation registers the DID in the shared PLC directory
2. The DID document contains the `alsoKnownAs` handle and the `atproto_pds` service endpoint
3. Any participant can resolve a DID via PLC to discover which PDS hosts the account

```python
def test_federation(pds_pair):
    pds_a, pds_b = pds_pair
    alice = pds_a.create_account("alice.test")
    bob = pds_b.create_account("bob.test")

    # Each PDS resolves its own handles
    result = pds_a.xrpc_get(
        "com.atproto.identity.resolveHandle",
        params={"handle": "alice.test"},
    )
    assert result["did"] == alice.did

    # Cross-PDS discovery uses DIDs (the canonical identifier)
    # DIDs from both PDS instances are in the shared PLC
    assert alice.did != bob.did
```

### Seeding on federated pairs

Declarative seeding works independently on each PDS in a federated pair:

```python
from testcontainers_atproto import Seed

def test_federated_seeding(pds_pair):
    pds_a, pds_b = pds_pair
    world_a = (
        Seed(pds_a)
        .account("alice.test")
            .post("Hello from PDS-A")
        .apply()
    )
    world_b = (
        Seed(pds_b)
        .account("bob.test")
            .post("Hello from PDS-B")
        .apply()
    )
    assert len(world_a.records["alice.test"]) == 1
    assert len(world_b.records["bob.test"]) == 1
```

---

## Rate Limit Simulation

Test your client's 429-handling and backoff logic against real PDS rate limiting. When `rate_limits=True`, the PDS enforces its built-in rate limits. Internal library calls (account creation, seeding, admin operations) use a bypass header so they never consume rate limit budget — only your test code's direct HTTP calls count.

### Enabling rate limits

```python
with PDSContainer(rate_limits=True) as pds:
    alice = pds.create_account("alice.test", password="s3cret")
    # Account creation used the bypass header — budget is untouched
```

When `rate_limits=False` (the default), the PDS does not enforce rate limits and no bypass key is generated.

### Exhausting the rate limit budget

Use `exhaust_rate_limit_budget` to consume an endpoint's entire budget. The next unprotected call triggers a 429:

```python
from testcontainers_atproto import CreateSession, PDSContainer

with PDSContainer(rate_limits=True) as pds:
    alice = pds.create_account("alice.test", password="s3cret")
    target = CreateSession(alice.handle, "s3cret")

    # Burns 30 calls (the createSession threshold)
    pds.exhaust_rate_limit_budget(target)

    # Your client's next call gets rate-limited
    import httpx
    resp = httpx.post(
        f"{pds.base_url}/xrpc/com.atproto.server.createSession",
        json={"identifier": alice.handle, "password": "s3cret"},
        timeout=10.0,
    )
    assert resp.status_code == 429
    assert resp.json()["error"] == "RateLimitExceeded"
```

The 429 response includes standard rate limit headers:

| Header | Description |
|--------|-------------|
| `RateLimit-Limit` | Maximum requests allowed in the window |
| `RateLimit-Remaining` | Requests remaining (0 after exhaustion) |
| `RateLimit-Reset` | Unix timestamp when the window resets |

### Built-in rate limit mapping

The library maintains a mapping of [XRPC](./glossary.md) endpoints to their tightest rate limit window. For endpoints with multiple windows (e.g. `createSession` has both 30/5min and 300/day), the tightest window is used — that's what triggers first.

| Endpoint | Max calls | Window |
|----------|-----------|--------|
| `com.atproto.server.createSession` | 30 | 5 min |
| `com.atproto.server.createAccount` | 100 | 5 min |
| `com.atproto.server.resetPassword` | 50 | 5 min |
| `com.atproto.server.requestPasswordReset` | 15 | 1 hr |
| `com.atproto.server.deleteAccount` | 5 | 1 hr |
| `com.atproto.server.requestAccountDelete` | 5 | 1 hr |
| `com.atproto.server.requestEmailConfirmation` | 5 | 1 hr |
| `com.atproto.server.requestEmailUpdate` | 5 | 1 hr |
| `com.atproto.identity.updateHandle` | 10 | 5 min |
| `com.atproto.repo.uploadBlob` | 1000 | 24 hr |

### Custom endpoints

For endpoints not in the built-in mapping — including custom [Lexicon](./glossary.md) endpoints — subclass `RateLimitTarget` and pass `threshold` explicitly:

```python
from testcontainers_atproto import RateLimitTarget

class MyEndpoint(RateLimitTarget):
    nsid = "com.example.heavyEndpoint"

    def __init__(self, auth: str) -> None:
        self.auth = auth

    def __call__(self, base_url):
        return httpx.post(
            f"{base_url}/xrpc/{self.nsid}",
            json={...},
            headers={"Authorization": f"Bearer {self.auth}"},
            timeout=10.0,
        )

pds.exhaust_rate_limit_budget(MyEndpoint(alice.access_jwt), threshold=50)
```

The `threshold` parameter overrides the built-in mapping. It's also useful when PDS version differences change the limits.

### Bypass key

The bypass key is exposed via `pds.bypass_key` for cases where test code needs selective bypass access:

```python
resp = httpx.post(
    f"{pds.base_url}/xrpc/com.atproto.server.createSession",
    json={"identifier": alice.handle, "password": "s3cret"},
    headers={"x-ratelimit-bypass": pds.bypass_key},
    timeout=10.0,
)
assert resp.status_code == 200  # bypassed, not rate-limited
```

### Rate limit methods

| Method | Description |
|--------|-------------|
| `exhaust_rate_limit_budget(target, threshold=)` | Fire `threshold` requests to consume the budget |

| Property | Type | Description |
|----------|------|-------------|
| `bypass_key` | `str \| None` | The bypass key (`None` when `rate_limits=False`) |

### Rate limit classes

| Class | Description |
|-------|-------------|
| `RateLimitTarget` | Base class — subclass and implement `__call__(base_url)` |
| `CreateSession` | Concrete target for `com.atproto.server.createSession` |

---

## Pytest Fixtures

After installing the package, these fixtures are available automatically via the `pytest11` entry point — no imports needed:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `pds` | function | Fresh [PDS](./glossary.md) instance per test |
| `pds_module` | module | Shared PDS instance within a test module |
| `pds_pair` | function | Two federated PDS instances sharing a [PLC](./glossary.md) directory |
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
| `Account` | `account` | Authenticated [ATP](./glossary.md) account with record, email, and sync operations |
| `RecordRef` | `ref` | Frozen dataclass referencing a created/updated record (AT URI + [CID](./glossary.md)) |
| `CarFile` | `car` | Frozen dataclass representing a parsed CAR v1 archive |
| `CarBlock` | `car` | Frozen dataclass representing a single block in a CAR file |
| `Seed` | `seed` | Fluent builder for declarative PDS state |
| `World` | `world` | Frozen dataclass of materialized seed state |
| `FirehoseSubscription` | `firehose` | WebSocket client for `subscribeRepos` with [CBOR](./glossary.md) decoding |
| `OAuthClient` | `oauth` | OAuth [DPoP](./glossary.md) flow client with XRPC helpers |
| `OAuthTokens` | `oauth` | Frozen dataclass for OAuth token responses |
| `DPoPKey` | `oauth` | ES256 key pair for [DPoP](./glossary.md) proof generation |
| `PKCEChallenge` | `oauth` | Frozen dataclass for PKCE S256 verifier/challenge pairs |
| `RateLimitTarget` | `rate_limit` | Base class for rate limit exhaustion targets |
| `CreateSession` | `rate_limit` | Concrete target for `createSession` rate limit |
| `XrpcError` | `errors` | Structured exception for [XRPC](./glossary.md) failures |

### Functions

| Function | Module | Description |
|----------|--------|-------------|
| `parse_car` | `car` | Parse CAR v1 bytes into a `CarFile` (requires `cbor2`) |

All classes and functions are exported from `testcontainers_atproto`:

```python
from testcontainers_atproto import (
    PDSContainer,
    Account,
    RecordRef,
    CarFile,
    CarBlock,
    parse_car,
    Seed,
    World,
    FirehoseSubscription,
    OAuthClient,
    OAuthTokens,
    DPoPKey,
    PKCEChallenge,
    RateLimitTarget,
    CreateSession,
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

See [glossary.md](./glossary.md) for definitions of PDS, DID, PLC, XRPC, Lexicon, NSID, JWT, DPoP, PKCE, PAR, CID, CBOR, MST, and other AT Protocol terms used throughout this guide.
