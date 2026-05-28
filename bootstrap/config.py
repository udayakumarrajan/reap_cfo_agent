import os
from dotenv import load_dotenv

# Load environment variables (force override)
load_dotenv(override=True)

# ERP settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ledger.db")
ERP_HOST = os.getenv("ERP_HOST", "0.0.0.0")
ERP_PORT = int(os.getenv("ERP_PORT", "8000"))

# Temporal settings
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "transaction-tagging-queue")
