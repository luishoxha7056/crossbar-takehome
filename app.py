import os
from collections import Counter
from typing import Any, Dict, Optional, List

import requests
from fastapi import FastAPI, HTTPException, Query

# Default RPC (can be overridden with env var)
DEFAULT_RPC_URL = "https://ethereum.publicnode.com"
RPC_URL = os.environ.get("RPC_URL", DEFAULT_RPC_URL)


class RpcError(Exception):
    """Custom exception for RPC errors."""
    pass


def hex_block_number(block_number: Optional[int]) -> str:
    """
    Convert an integer block number to a hex string (0x...), or 'latest' if None.
    """
    if block_number is None:
        return "latest"
    if block_number < 0:
        raise ValueError("Block number cannot be negative")
    return hex(block_number)


def call_rpc(method: str, params: List[Any]) -> Any:
    """
    Make a JSON-RPC call to the configured RPC_URL.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    try:
        response = requests.post(RPC_URL, json=payload, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RpcError(f"Network or HTTP error while calling RPC: {e}") from e

    data = response.json()

    if "error" in data:
        raise RpcError(f"RPC error: {data['error']}")

    return data.get("result")


def fetch_block(block_number: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch a block (with full transaction objects) from the chain.
    If block_number is None, fetch the latest block.
    """
    block_id = hex_block_number(block_number)
    result = call_rpc("eth_getBlockByNumber", [block_id, True])

    if result is None:
        raise RpcError(f"No block found for {block_id}")

    return result


def process_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process block data:
      - count total transactions
      - group by sender ('from') and receiver ('to')
    """
    txs = block.get("transactions", [])
    total_txs = len(txs)

    senders = Counter()
    receivers = Counter()

    for tx in txs:
        sender = tx.get("from")
        receiver = tx.get("to")

        if sender:
            senders[sender] += 1

        # 'to' can be None for contract creation transactions
        receiver_key = "null" if receiver is None else receiver
        receivers[receiver_key] += 1

    summary = {
        "block_number": int(block["number"], 16) if block.get("number") else None,
        "block_hash": block.get("hash"),
        "total_transactions": total_txs,
        "by_sender": dict(senders),
        "by_receiver": dict(receivers),
    }

    return summary


# ------------- FastAPI app -------------

app = FastAPI(title="Ethereum Block Summary API")


@app.get("/")
def root():
    return {
        "message": "Ethereum block summary API",
        "endpoints": {
            "/block": {
                "method": "GET",
                "query_params": {
                    "number": "optional integer block number; if omitted, uses 'latest'"
                },
                "examples": [
                    "/block",
                    "/block?number=21000000",
                ],
            }
        },
    }


@app.get("/block")
def get_block(
    number: Optional[int] = Query(
        default=None,
        description="Block number (integer). If omitted, latest block is used.",
    )
):
    """
    GET /block?number=21000000
    - number missing => latest block
    """
    try:
        block = fetch_block(number)
        summary = process_block(block)
        return summary
    except RpcError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        # e.g. negative block number
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected error
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")
