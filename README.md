# testcontainers-atproto

[![tests](https://github.com/withtwoemms/testcontainers-atproto/workflows/tests/badge.svg)](https://github.com/withtwoemms/testcontainers-atproto/actions?query=workflow%3Atests)
[![codecov](https://codecov.io/gh/withtwoemms/testcontainers-atproto/graph/badge.svg)](https://codecov.io/gh/withtwoemms/testcontainers-atproto)
[![publish](https://github.com/withtwoemms/testcontainers-atproto/workflows/publish/badge.svg)](https://github.com/withtwoemms/testcontainers-atproto/actions?query=workflow%3Apublish)

> Spin up ephemeral PDS instances in your Python test suite. Lexicon-agnostic — works with any application built on [AT Protocol](https://atproto.com), not just Bluesky.

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

## Quick start

```python
from testcontainers_atproto import PDSContainer

with PDSContainer() as pds:
    account = pds.create_account("alice.test")
    print(pds.base_url)       # http://localhost:<port>
    print(account.did)         # did:plc:...
    print(account.handle)      # alice.test
```

A local PLC directory runs alongside the PDS on a shared Docker network — no public internet required. For Postgres-backed PLC parity with production, pass `plc_mode="real"`:

```python
with PDSContainer(plc_mode="real") as pds:
    account = pds.create_account("alice.test")
```

### Record operations

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")

    # Create
    ref = alice.create_record("app.bsky.feed.post", {
        "$type": "app.bsky.feed.post",
        "text": "hello from testcontainers",
        "createdAt": "2026-01-01T00:00:00Z",
    })

    # Read
    record = alice.get_record("app.bsky.feed.post", ref.rkey)

    # Update
    alice.put_record("app.bsky.feed.post", ref.rkey, {
        "$type": "app.bsky.feed.post",
        "text": "updated text",
        "createdAt": "2026-01-01T00:00:00Z",
    })

    # List & delete
    records = alice.list_records("app.bsky.feed.post")
    alice.delete_record("app.bsky.feed.post", ref.rkey)
```

### Firehose subscription

Observe real-time repository events via the AT Protocol firehose:

```python
from testcontainers_atproto import PDSContainer

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

### Repo sync

Export repositories and retrieve blobs for relay and indexer testing:

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

    # Parse the CAR to inspect blocks
    from testcontainers_atproto import parse_car
    car = parse_car(car_bytes)
    print(f"{len(car.blocks)} blocks, {len(car.roots)} roots")

    # Retrieve a specific blob
    blob_ref = alice.upload_blob(b"test data", "image/png")
    blob_data = alice.get_blob(blob_ref["ref"]["$link"])
    assert blob_data == b"test data"
```

CAR parsing requires the sync extra: `pip install testcontainers-atproto[sync]`

### Declarative seeding

Describe the world, materialize it in one call — no boilerplate account/record setup:

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

Placeholders let custom records reference other accounts' DIDs and records — resolved at `apply()` time:

```python
with PDSContainer() as pds:
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
                "reviewer": Seed.did("bob.test"),
                "project": Seed.ref("alice.test", 0),
            })
        .apply()
    )
```

Accounts can be revisited to interleave records (e.g. conversation threads):

```python
world = (
    Seed(pds)
    .account("alice.test")
        .post("alice first")
    .account("bob.test")
        .post("bob replies")
    .account("alice.test")
        .post("alice continues")
    .apply()
)
```

Also available as a dict-based API for data-driven fixtures:

```python
world = pds.seed({
    "accounts": [
        {"handle": "alice.test", "posts": ["Hello from Alice"]},
        {"handle": "bob.test", "follows": ["alice.test"]},
    ],
})
```

### Federation testing

Test cross-PDS scenarios with two PDS instances sharing a PLC directory:

```python
def test_cross_pds_resolution(pds_pair):
    pds_a, pds_b = pds_pair
    alice = pds_a.create_account("alice.test")
    bob = pds_b.create_account("bob.test")

    # Each PDS resolves its own handles
    assert pds_a.xrpc_get(
        "com.atproto.identity.resolveHandle",
        params={"handle": "alice.test"},
    )["did"] == alice.did

    # DIDs from both PDS instances are registered in the shared PLC
    assert alice.did != bob.did
    assert alice.did.startswith("did:plc:")
    assert bob.did.startswith("did:plc:")
```

The `pds_pair` fixture creates a shared Docker network and PLC directory. Handle resolution is local to each PDS; cross-PDS discovery uses DIDs resolved through the shared PLC.

### Rate limit simulation

Test your client's 429-handling and backoff logic against real PDS rate limiting:

```python
from testcontainers_atproto import CreateSession, PDSContainer

with PDSContainer(rate_limits=True) as pds:
    alice = pds.create_account("alice.test", password="s3cret")
    target = CreateSession(alice.handle, "s3cret")

    # Burn through the rate limit budget (30 calls for createSession)
    pds.exhaust_rate_limit_budget(target)

    # The next call triggers a 429
    import httpx
    resp = httpx.post(
        f"{pds.base_url}/xrpc/com.atproto.server.createSession",
        json={"identifier": alice.handle, "password": "s3cret"},
        timeout=10.0,
    )
    assert resp.status_code == 429
    assert resp.json()["error"] == "RateLimitExceeded"
```

When `rate_limits=False` (the default), rate limiting is disabled and no bypass key is generated. Internal library calls (account creation, seeding, etc.) always use a bypass header so they never consume rate limit budget.

For custom endpoints, subclass `RateLimitTarget`:

```python
from testcontainers_atproto import RateLimitTarget

class MyEndpoint(RateLimitTarget):
    nsid = "com.example.heavyEndpoint"

    def __call__(self, base_url):
        return httpx.post(f"{base_url}/xrpc/{self.nsid}", ...)

pds.exhaust_rate_limit_budget(MyEndpoint(), threshold=50)
```

### OAuth DPoP authentication

Test OAuth client implementations end-to-end with DPoP (Demonstration of Proof-of-Possession) bound tokens:

```python
from testcontainers_atproto import PDSContainer

with PDSContainer() as pds:
    alice = pds.create_account("alice.test", password="hunter2")

    # Full flow in one call — returns an OAuthClient + tokens
    client, tokens = pds.oauth_authenticate(alice)

    # Use DPoP-authenticated XRPC calls
    resp = client.xrpc_get(
        "com.atproto.repo.describeRepo",
        tokens.access_token,
        params={"repo": alice.did},
    )
    assert resp["handle"] == "alice.test"

    # Create records via OAuth
    client.xrpc_post(
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

    # Token refresh
    new_tokens = client.refresh_tokens(tokens.refresh_token)

    # Token revocation
    client.revoke_token(new_tokens.access_token)
```

For step-by-step control over each phase of the flow:

```python
from testcontainers_atproto import DPoPKey, PKCEChallenge, PDSContainer

with PDSContainer() as pds:
    alice = pds.create_account("alice.test", password="hunter2")
    client = pds.oauth_client()

    pkce = PKCEChallenge.generate()
    request_uri = client.pushed_authorization_request(pkce, login_hint="alice.test")
    code = client.authorize(request_uri, "alice.test", "hunter2")
    tokens = client.token_exchange(code, pkce)
```

Requires the oauth extra: `pip install testcontainers-atproto[oauth]`

### Email verification

Test email verification and password reset flows with a local Mailpit SMTP server:

```python
with PDSContainer(email_mode="capture") as pds:
    alice = pds.create_account("alice.test")

    # Request verification email
    alice.request_email_confirmation()

    # Retrieve it from Mailpit
    message = pds.await_email(alice.email)

    # Extract token and confirm (token format is PDS-version-dependent)
    token = extract_token(message)  # your extraction logic
    alice.confirm_email(token)
```

Password reset follows the same pattern:

```python
    alice.request_password_reset()
    message = pds.await_email(alice.email)
    token = extract_token(message)
    alice.reset_password(token, "new-password")
```

When `email_mode="none"` (the default), email verification is bypassed and no Mailpit container is started.

### Account lifecycle

Deactivate, reactivate, and delete accounts to test how your app handles state changes:

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")

    # Deactivate — account becomes inaccessible
    alice.deactivate()

    # Re-activate — access restored
    alice.activate()

    # Check status
    status = alice.check_account_status()
    assert status["activated"] is True
```

Admin operations let you test moderation flows:

```python
with PDSContainer() as pds:
    alice = pds.create_account("alice.test")

    # Takedown — blocks access
    pds.takedown(alice)

    # Restore — unblocks access
    pds.restore(alice)

    # Query status
    status = pds.get_subject_status(alice)
```

Account deletion requires `email_mode="capture"` to retrieve the deletion token:

```python
with PDSContainer(email_mode="capture") as pds:
    alice = pds.create_account("alice.test", password="s3cret")

    # ... confirm email first ...

    alice.request_account_delete()
    message = pds.await_email(alice.email)
    token = extract_token(message)  # your extraction logic
    alice.delete_account("s3cret", token)
```

### Error handling

XRPC failures raise `XrpcError` with structured fields:

```python
from testcontainers_atproto import PDSContainer, XrpcError

with PDSContainer() as pds:
    try:
        pds.create_account("alice.invalid")
    except XrpcError as e:
        print(e.status_code)  # 400
        print(e.error)        # "InvalidHandle"
        print(e.message)      # human-readable detail
```

---

## Pytest fixtures

After installing the package, these fixtures are available automatically via the `pytest11` entry point:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `pds` | function | Fresh PDS instance per test |
| `pds_module` | module | Shared PDS instance within a test module |
| `pds_pair` | function | Two PDS instances for federation testing |
| `pds_image` | session | PDS image tag (override via `ATP_PDS_IMAGE` env var) |

```python
def test_create_account(pds):
    account = pds.create_account("bob.test")
    assert account.did.startswith("did:plc:")
```

---

## Development

```bash
make venv                                       # Create virtual environment
source .testcontainers-atproto-3.12/bin/activate # Activate
make test                                        # Run tests
make test-all                                    # Run across all supported Python versions
```

---

## Glossary

AT Protocol introduces many domain-specific terms. See [docs/glossary.md](./docs/glossary.md) for definitions of PDS, DID, PLC, XRPC, and other initialisms used in this project.

---

## License

Apache-2.0. See [LICENSE](./LICENSE).
