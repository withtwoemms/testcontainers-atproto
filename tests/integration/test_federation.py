"""Integration tests: pds_pair federation — cross-PDS DID resolution."""

import pytest

from testcontainers_atproto import PDSContainer, Seed

pytestmark = pytest.mark.requires_docker


# --- pds_pair fixture basics ---


class TestPdsPairFixture:
    """The pds_pair fixture boots two federated PDS instances."""

    def test_both_containers_are_healthy(self, pds_pair):
        pds_a, pds_b = pds_pair
        assert "version" in pds_a.health()
        assert "version" in pds_b.health()

    def test_different_ports(self, pds_pair):
        pds_a, pds_b = pds_pair
        assert pds_a.port != pds_b.port

    def test_create_accounts_on_both(self, pds_pair):
        pds_a, pds_b = pds_pair
        alice = pds_a.create_account("alice.test")
        bob = pds_b.create_account("bob.test")
        assert alice.did.startswith("did:plc:")
        assert bob.did.startswith("did:plc:")
        assert alice.did != bob.did


# --- Cross-PDS DID resolution ---


class TestCrossPdsResolution:
    """DIDs registered on one PDS are resolvable via the shared PLC.

    Handle resolution (``resolveHandle``) is a local-database + DNS
    operation — each PDS can only resolve handles it hosts.  Cross-PDS
    discovery goes through the shared PLC directory, which resolves a
    DID to its DID document (containing the hosting PDS endpoint and
    the handle in ``alsoKnownAs``).
    """

    def test_each_pds_resolves_own_handles(self, pds_pair):
        """Each PDS resolves handles registered in its local database."""
        pds_a, pds_b = pds_pair
        alice = pds_a.create_account("alice.test")
        bob = pds_b.create_account("bob.test")

        result_a = pds_a.xrpc_get(
            "com.atproto.identity.resolveHandle",
            params={"handle": "alice.test"},
        )
        assert result_a["did"] == alice.did

        result_b = pds_b.xrpc_get(
            "com.atproto.identity.resolveHandle",
            params={"handle": "bob.test"},
        )
        assert result_b["did"] == bob.did

    def test_shared_plc_resolves_did_from_either_pds(self, pds_pair):
        """The shared PLC directory resolves DIDs created on either PDS."""
        import httpx
        from testcontainers_atproto.container import _PLC_PORT

        pds_a, pds_b = pds_pair
        alice = pds_a.create_account("alice.test")
        bob = pds_b.create_account("bob.test")

        # Both PDS instances share the same PLC — query it via the
        # internal PLC URL exposed through the PDS environment.
        # The PLC container is on the same Docker network; from the
        # host we reach it through PDS-A's network (same network).
        plc = pds_a._shared_plc
        plc_host = plc.get_container_host_ip()
        plc_port = plc.get_exposed_port(_PLC_PORT)
        plc_url = f"http://{plc_host}:{plc_port}"

        # Resolve alice's DID from PLC
        resp_a = httpx.get(f"{plc_url}/{alice.did}", timeout=10.0)
        resp_a.raise_for_status()
        doc_a = resp_a.json()
        assert doc_a["id"] == alice.did
        assert any("alice.test" in aka for aka in doc_a.get("alsoKnownAs", []))

        # Resolve bob's DID from PLC
        resp_b = httpx.get(f"{plc_url}/{bob.did}", timeout=10.0)
        resp_b.raise_for_status()
        doc_b = resp_b.json()
        assert doc_b["id"] == bob.did
        assert any("bob.test" in aka for aka in doc_b.get("alsoKnownAs", []))

    def test_did_documents_point_to_correct_pds(self, pds_pair):
        """DID documents registered via different PDS instances contain
        service endpoints pointing back to their respective PDS."""
        import httpx
        from testcontainers_atproto.container import _PLC_PORT

        pds_a, pds_b = pds_pair
        alice = pds_a.create_account("alice.test")
        bob = pds_b.create_account("bob.test")

        plc = pds_a._shared_plc
        plc_host = plc.get_container_host_ip()
        plc_port = plc.get_exposed_port(_PLC_PORT)
        plc_url = f"http://{plc_host}:{plc_port}"

        doc_a = httpx.get(f"{plc_url}/{alice.did}", timeout=10.0).json()
        doc_b = httpx.get(f"{plc_url}/{bob.did}", timeout=10.0).json()

        # Each DID document should have a service entry for atproto_pds
        svc_a = {s["id"]: s for s in doc_a.get("service", [])}
        svc_b = {s["id"]: s for s in doc_b.get("service", [])}

        assert "#atproto_pds" in svc_a
        assert "#atproto_pds" in svc_b

        # The service endpoints should point to different PDS hostnames
        assert svc_a["#atproto_pds"]["serviceEndpoint"] != svc_b["#atproto_pds"]["serviceEndpoint"]

    def test_cross_pds_record_fetch_via_did(self, pds_pair):
        """Records created on PDS-A are fetchable using the DID
        (the canonical cross-PDS identifier)."""
        pds_a, pds_b = pds_pair
        alice = pds_a.create_account("alice.test")

        ref = alice.create_record("app.bsky.feed.post", {
            "$type": "app.bsky.feed.post",
            "text": "visible across PDS boundary",
            "createdAt": "2026-01-01T00:00:00Z",
        })

        # In AT Protocol, cross-PDS discovery uses DIDs — not handles.
        # A client resolves the DID via PLC to find the hosting PDS,
        # then fetches the record from that PDS.
        record = pds_a.xrpc_get(
            "com.atproto.repo.getRecord",
            params={
                "repo": alice.did,
                "collection": "app.bsky.feed.post",
                "rkey": ref.rkey,
            },
        )
        assert record["value"]["text"] == "visible across PDS boundary"


# --- Seeding on federated pairs ---


class TestPdsPairWithSeed:
    """Declarative seeding works with individual PDS instances from pds_pair."""

    def test_seed_on_each_pds(self, pds_pair):
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
