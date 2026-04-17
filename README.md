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

## License

Apache-2.0. See [LICENSE](./LICENSE).
