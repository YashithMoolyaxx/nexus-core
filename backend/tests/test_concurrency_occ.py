import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_creation_and_version_increment(client: AsyncClient, auth_headers):
    create_payload = {
        "title": "Distributed Consensus Architecture",
        "content": "Raft protocol spec v1",
    }
    create_res = await client.post(
        "/api/v1/documents/",
        json=create_payload,
        headers=auth_headers["developer"],
    )
    assert create_res.status_code == 201
    doc_data = create_res.json()
    assert doc_data["version"] == 1
    doc_id = doc_data["id"]

    update_payload = {
        "title": "Distributed Consensus Architecture (Revised)",
        "content": "Raft protocol spec v2 with snapshotting",
        "version": 1,
    }
    update_res = await client.put(
        f"/api/v1/documents/{doc_id}",
        json=update_payload,
        headers=auth_headers["developer"],
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["version"] == 2
    assert updated_data["content"] == "Raft protocol spec v2 with snapshotting"


@pytest.mark.asyncio
async def test_occ_race_condition_generates_409_conflict(client: AsyncClient, auth_headers):
    create_res = await client.post(
        "/api/v1/documents/",
        json={
            "title": "High Frequency Trading Order Engine",
            "content": "Initial specification",
        },
        headers=auth_headers["developer"],
    )
    assert create_res.status_code == 201
    doc = create_res.json()
    doc_id = doc["id"]
    base_version = doc["version"]

    mutation_a = {
        "title": "High Frequency Trading Order Engine",
        "content": "Operator A committed order queue optimizations",
        "version": base_version,
    }
    res_a = await client.put(
        f"/api/v1/documents/{doc_id}",
        json=mutation_a,
        headers=auth_headers["developer"],
    )
    assert res_a.status_code == 200
    assert res_a.json()["version"] == 2

    mutation_b = {
        "title": "High Frequency Trading Order Engine",
        "content": "Operator B concurrently committed matching engine fixes",
        "version": base_version,
    }
    res_b = await client.put(
        f"/api/v1/documents/{doc_id}",
        json=mutation_b,
        headers=auth_headers["admin"],
    )

    assert res_b.status_code == 409
    error_detail = res_b.json()["detail"]
    assert "Optimistic Concurrency Conflict" in error_detail["message"]
    assert error_detail["current_version"] == 2
    assert error_detail["submitted_version"] == 1