# Nexus Core — Distributed Multi-Tenant State & Collaboration Engine

[![CI](https://github.com/your-username/nexus-core/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/nexus-core/actions)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16--Alpine-316192.svg?style=flat&logo=PostgreSQL&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7--Alpine-DC382D.svg?style=flat&logo=Redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.3.6-37814A.svg?style=flat&logo=Celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=Docker&logoColor=white)

Nexus Core is an asynchronous, multi-tenant collaboration engine built with FastAPI, PostgreSQL, Redis, and Celery. It addresses distributed state synchronization, database-level tenant isolation, concurrent collision handling, and non-blocking statistical batch compute.

---

## 🏛 System Architecture

```mermaid
flowchart TD
    subgraph Client Layer
        WebUser[React Client A\nTenant: Core Eng]
        WebUser2[React Client B\nTenant: FinTech Labs]
    end

    subgraph Edge & Ingestion Layer
        Nginx[Nginx Reverse Proxy\nRate Limiter & WS Terminator]
    end

    subgraph API Cluster
        API1[FastAPI Node 01\nUvicorn Asynchronous Loop]
        API2[FastAPI Node 02\nUvicorn Asynchronous Loop]
    end

    subgraph Data & Synchronization Plane
        RedisBroker[Redis Cluster\n• Pub/Sub WebSocket Mesh\n• Ephemeral Presence Keys\n• IP Rate Limiting Counters]
        Postgres[PostgreSQL 16\n• Row-Level Security (RLS)\n• OCC Atomic Version Checks\n• ACID Transactions]
    end

    subgraph Asynchronous Compute Plane
        Worker[Celery Worker Pool\nVectorized NumPy / Pandas Engine]
    end

    WebUser -->|HTTP / WSS| Nginx
    WebUser2 -->|HTTP / WSS| Nginx
    Nginx -->|Proxy| API1
    Nginx -->|Proxy| API2

    API1 <-->|Pub/Sub & Presence| RedisBroker
    API2 <-->|Pub/Sub & Presence| RedisBroker

    API1 <-->|AsyncPG Session| Postgres
    API2 <-->|AsyncPG Session| Postgres

    API1 -->|Dispatch Batch Job| RedisBroker
    RedisBroker -->|Task Queue| Worker