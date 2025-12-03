# Ethereum Block Summary API

This repository contains a small FastAPI service that connects to an Ethereum RPC node, fetches a block, and returns a summary of its transactions grouped by sender and receiver.

The application is containerized with Docker and deployed with Docker Compose and Traefik.  
Build and deploy pipelines are automated with GitHub Actions, and the live API is available at:

**https://mydevenv.online/**

---

## Features

- HTTP API endpoint to summarize an Ethereum block:
  - `GET /block` – latest block
  - `GET /block?number=<block_number>` – specific block
- Counts total transactions per block
- Groups transactions by:
  - `by_sender`: address → count
  - `by_receiver`: address → count
- Stateless, simple, and easy to deploy
- Automated build and deployment pipeline using:
  - GitHub Actions (build and push image to GHCR)
  - Self-hosted GitHub Actions runner on the target server
  - Docker Compose + Traefik for runtime

---

## Live API

Deployed instance:

- Base URL: **https://mydevenv.online/**

Example usage:

- Latest block:
  - `https://mydevenv.online/block`
- Specific block (e.g. 21000000):
  - `https://mydevenv.online/block?number=21000000`

Typical JSON response:

```json
{
  "block_number": 21000000,
  "block_hash": "0xf5e1d15a3e380006bd271e73c8eeed75fafc3ae6942b16f63c21361079bba709",
  "total_transactions": 181,
  "by_sender": {
    "0x...": 3
  },
  "by_receiver": {
    "0x...": 57
  }
}

```


---
### Application Code (FastAPI)

The core service is intentionally kept minimal:

```python
import os
from typing import Optional
import requests
from fastapi import FastAPI

RPC_URL = os.environ.get("RPC_URL", "https://ethereum.publicnode.com")

app = FastAPI()

def call_rpc(method, params):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return requests.post(RPC_URL, json=payload).json().get("result")

def fetch_block(block_number: Optional[int]):
    block_id = "latest" if block_number is None else hex(block_number)
    return call_rpc("eth_getBlockByNumber", [block_id, True])

def process_block(block):
    txs = block.get("transactions", [])
    senders = {}
    receivers = {}

    for tx in txs:
        s = tx.get("from")
        t = tx.get("to") or "null"
        senders[s] = senders.get(s, 0) + 1
        receivers[t] = receivers.get(t, 0) + 1

    return {
        "block_number": int(block["number"], 16),
        "block_hash": block["hash"],
        "total_transactions": len(txs),
        "by_sender": senders,
        "by_receiver": receivers,
    }

@app.get("/block")
def get_block(number: Optional[int] = None):
    block = fetch_block(number)
    return process_block(block)

```


## Local Development
### Run without Docker

```bash
pip install fastapi uvicorn requests

uvicorn app:app --host 0.0.0.0 --port 8000 --reload

```

Then:

- http://localhost:8000/block

- http://localhost:8000/block?number=21000000


---
### Docker Compose: Web3 API

This compose file runs only the FastAPI application container.


```yml
version: "3.9"

services:
  web3-api:
    image: ghcr.io/luishoxha7056/crossbar-takehome-web:latest
    container_name: web3-api
    environment:
      RPC_URL: "https://ethereum.publicnode.com"
    ports:
      - "8000:8000"
    restart: unless-stopped

```


You can start it with:
```bash
docker compose up -d
```

The API will be available at:

- http://localhost:8000/block

---
### Docker Compose: Traefik Reverse Proxy
This compose file runs Traefik and routes traffic for the domain to the web3-api service.
Both stacks should share a common Docker network (for example, web), which you can create once with:

```bash
docker network create web
```

then:
```yml
version: "3.9"

services:
  traefik:
    image: traefik:v2.11
    container_name: traefik
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - web
    restart: unless-stopped

  web3-api:
    image: ghcr.io/luishoxha7056/crossbar-takehome-web:latest
    container_name: web3-api
    environment:
      RPC_URL: "https://ethereum.publicnode.com"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.web3.rule=Host(`mydevenv.online`)"
      - "traefik.http.routers.web3.entrypoints=web"
      - "traefik.http.services.web3.loadbalancer.server.port=8000"
    networks:
      - web
    restart: unless-stopped

networks:
  web:
    external: true
```


With this setup and DNS pointing mydevenv.online to the server IP, requests to:

- https://mydevenv.online/block

are routed through Traefik to the FastAPI container.

---
### CI/CD and Automation

The build and deploy pipeline is automated:

- On pushes to the main branch:

  - GitHub Actions build a Docker image for the application.

  - The image is pushed to GitHub Container Registry (GHCR).

  - A self-hosted GitHub Actions runner on the server runs docker compose up -d to pull the latest image and restart the services.

- As a result, new changes are automatically deployed, and the updated API is available at https://mydevenv.online/.

This setup provides a simple continuous deployment flow with minimal configuration.


## Reflection & Improvements

### 1. What trade-offs did you make in your design?

I intentionally chose a very simple design. The API logic, Docker setup, and deployment pipeline are straightforward, which makes the project easy to read and reason about. The trade-off is that I sacrificed advanced features such as detailed validation, richer error handling, and more flexible architecture in favor of clarity and speed of development.

### 2. What limitations does your current solution have?
The solution depends on a public Ethereum RPC endpoint, which can be rate-limited or slower at times. There is no retry logic, caching, or robust error reporting. The service exposes only one main endpoint and does not provide more complex analytics or pagination. It is suitable for moderate usage, but it is not tuned for very high throughput or production-grade observability.

### 3. What would you improve if you had additional time?

With more time, I would add proper error handling, logging, and retry behavior around RPC calls. I would introduce caching for recently requested blocks to reduce latency and load on the RPC provider. I would also extend the API surface with additional endpoints, add automated tests, and improve configuration to support multiple chains or RPC backends more cleanly.


### 4. Which part of this assessment challenged you the most?

The most challenging part was working with public Ethereum RPC endpoints and making sure the service behaves consistently when external infrastructure is not always perfect. Setting up the self-hosted GitHub Actions runner, connecting it to Docker Compose on the server, and wiring everything through Traefik to a real domain like mydevenv.online required careful configuration, but once in place it provided a smooth automated deployment pipeline.