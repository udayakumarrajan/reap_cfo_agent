"""
Manual smoke test for the ERP API. Requires the app to be running:

    python main.py
    python scripts/smoke_erp.py
"""
import os
import requests

ERP_BASE = os.getenv("ERP_BASE_URL", "http://localhost:8000")
TRANSACTIONS_URL = f"{ERP_BASE}/api/transactions"
COA_URL = f"{ERP_BASE}/api/coa/123"


def smoke_fetch_coa() -> None:
    print(f"Fetching CoA from {COA_URL}...")
    try:
        response = requests.get(COA_URL, timeout=10)
        response.raise_for_status()
        print("CoA:", response.json())
    except Exception as e:
        print("Error fetching CoA:", e)


def smoke_create_transaction() -> None:
    payload = {
        "merchant": "Google Cloud Platform",
        "amount": 450.75,
        "tenant_id": "123",
        "external_id": "ref-smoke-demo",
    }
    print(f"Sending POST request to {TRANSACTIONS_URL}...")
    try:
        response = requests.post(TRANSACTIONS_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("Success! Response:", response.json())
    except Exception as e:
        print("Error sending request:", e)
        print("Make sure main.py is running first: python main.py")


if __name__ == "__main__":
    smoke_fetch_coa()
    smoke_create_transaction()
