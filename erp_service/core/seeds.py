"""Bootstrap data for empty databases (CoA + optional cold-start tagging examples)."""

DEFAULT_COA = [
    {"code": "6100", "name": "SaaS tools & Software", "type": "Expense"},
    {"code": "6200", "name": "Marketing", "type": "Expense"},
    {"code": "7000", "name": "Suspense Account", "type": "Expense"},
]

DEFAULT_TENANT_ID = "123"

# Seeded once per fresh DB so tenant 123 has few-shot context before first live post.
DEFAULT_TAGGING_EXAMPLES = [
    {
        "merchant": "Amazon Web Services",
        "amount": 150.0,
        "account_code": "6100",
        "account_name": "SaaS tools & Software",
        "source": "bootstrap",
    },
    {
        "merchant": "Google Ads",
        "amount": 500.0,
        "account_code": "6200",
        "account_name": "Marketing",
        "source": "bootstrap",
    },
]
