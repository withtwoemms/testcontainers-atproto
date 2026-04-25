# Glossary

Terms and initialisms from the [AT Protocol](https://atproto.com) ecosystem, referenced throughout this project.

---

| Term | Expansion | Definition |
|------|-----------|------------|
| ATP | AT Protocol | The decentralized social networking protocol developed by Bluesky. Specifies identity, data, and communication layers. |
| BGS | Big Graph Service | Former name for the relay component that aggregates repository events from multiple PDS instances. Replaced by `relay` in early 2026. |
| CBOR | Concise Binary Object Representation | Binary data serialization format ([RFC 8949](https://www.rfc-editor.org/rfc/rfc8949.html)) used to encode firehose frames and repository blocks. |
| CID | Content Identifier | A self-describing hash used to address immutable content in repositories. Based on the [multiformats](https://multiformats.io) specification. |
| DAG-CBOR | Directed Acyclic Graph CBOR | A deterministic CBOR encoding used by the Merkle Search Tree (MST) that backs AT Protocol repositories. |
| DID | Decentralized Identifier | A globally unique, self-sovereign identifier ([W3C spec](https://www.w3.org/TR/did-core/)). AT Protocol supports `did:plc` and `did:web` methods. |
| DPoP | Demonstration of Proof-of-Possession | An OAuth extension ([RFC 9449](https://www.rfc-editor.org/rfc/rfc9449)) that binds access tokens to a client's key pair. AT Protocol uses DPoP with ES256 (P-256) keys to prevent token theft and replay. |
| JWT | JSON Web Token | A compact, signed token ([RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)) used for session authentication. The PDS issues access and refresh JWTs on account creation and login. |
| Lexicon | — | AT Protocol's schema language for defining XRPC methods and record types. Identified by reverse-DNS NSIDs (e.g. `app.bsky.feed.post`). |
| MST | Merkle Search Tree | The authenticated data structure backing each account's repository. Allows efficient sync and verification of record sets. |
| NSID | Namespaced Identifier | A reverse-DNS string (e.g. `com.atproto.server.createAccount`) that uniquely identifies a Lexicon schema or XRPC method. |
| PAR | Pushed Authorization Request | An OAuth mechanism ([RFC 9126](https://www.rfc-editor.org/rfc/rfc9126)) where the client sends authorization parameters directly to the server and receives a `request_uri` to use in the authorization step. |
| PDS | Personal Data Server | A server that hosts user repositories, issues auth tokens, and exposes XRPC endpoints. Each user's data lives on exactly one PDS. |
| PLC | Public Ledger of Credentials | A DID method (`did:plc`) purpose-built for AT Protocol. Provides a strongly consistent, recoverable identity layer backed by a public directory. |
| PKCE | Proof Key for Code Exchange | An OAuth extension ([RFC 7636](https://www.rfc-editor.org/rfc/rfc7636)) that prevents authorization code interception. AT Protocol requires the S256 challenge method. |
| Relay | — | The network component (formerly BGS) that crawls PDS instances, aggregates repository events, and exposes a combined firehose for downstream consumers like AppViews. |
| XRPC | Cross-system Remote Procedure Call | AT Protocol's HTTP-based RPC framework. Methods are identified by NSIDs and classified as queries (GET) or procedures (POST). |

---

See also: [AT Protocol Specifications](https://atproto.com/specs)
