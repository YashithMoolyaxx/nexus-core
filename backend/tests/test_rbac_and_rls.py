import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rbac_write_permissions(client: AsyncClient, auth_headers):
    doc_payload = {
        "title": "Zero Trust Security Blueprint",
        "content": "Confidential security schema",
    }

    viewer_res = await client.post(
        "/api/v1/documents/",
        json=doc_payload,
        headers=auth_headers["viewer"],
    )
    assert viewer_res.status_code == 403
    assert "RBAC Permission Denied" in viewer_res.json()["detail"]

    dev_res = await client.post(
        "/api/v1/documents/",
        json=doc_payload,
        headers=auth_headers["developer"],
    )
    assert dev_res.status_code == 201


@pytest.mark.asyncio
async def test_rbac_celery_compute_permissions(client: AsyncClient, auth_headers):
    task_payload = {"record_count": 5000}

    res_viewer = await client.post(
        "/api/v1/tasks/run-analytics",
        json=task_payload,
        headers=auth_headers["viewer"],
    )
    assert res_viewer.status_code == 403

    res_dev = await client.post(
        "/api/v1/tasks/run-analytics",
        json=task_payload,
        headers=auth_headers["developer"],
    )
    assert res_dev.status_code == 403

    res_admin = await client.post(
        "/api/v1/tasks/run-analytics",
        json=task_payload,
        headers=auth_headers["admin"],
    )
    assert res_admin.status_code == 202
    assert res_admin.json()["status"] == "QUEUED"
    assert "task_id" in res_admin.json()


@pytest.mark.asyncio
async def test_rls_cross_tenant_isolation(client: AsyncClient, auth_headers):
    doc_alpha = await client.post(
        "/api/v1/documents/",
        json={
            "title": "Alpha Proprietary Algorithms",
            "content": "Strictly restricted to Tenant Alpha",
        },
        headers=auth_headers["developer"],
    )
    assert doc_alpha.status_code == 201
    doc_id = doc_alpha.json()["id"]

    beta_get_res = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers["beta_developer"],
    )
    assert beta_get_res.status_code == 404

    beta_put_res = await client.put(
        f"/api/v1/documents/{doc_id}",
        json={
            "title": "Malicious Overwrite",
            "content": "Attempting cross-tenant data corruption",
            "version": 1,
        },
        headers=auth_headers["beta_developer"],
    )
    assert beta_put_res.status_code == 404