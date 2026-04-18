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
| `testcontainers-atproto[sdk]` | `atproto` (MarshalX SDK) for high-level record ops |
| `testcontainers-atproto[all]` | Both of the above |

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

Also available as a dict-based API for data-driven fixtures:

```python
world = pds.seed({
    "accounts": [
        {"handle": "alice.test", "posts": ["Hello from Alice"]},
        {"handle": "bob.test", "follows": ["alice.test"]},
    ],
})
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
