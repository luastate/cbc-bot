import os
from dotenv import load_dotenv
load_dotenv()

DATA_FILE = os.getenv("CBC_BOT_DATA_FILE", "data.json")
DEFAULT_CURRENCY = os.getenv("CBC_BOT_CURRENCY", "silver")
DEFAULT_ADMIN_ROLE_IDS = os.getenv("CBC_BOT_ADMIN_ROLE_ID").split(",")
TRANSACTION_HISTORY_DEFAULT_LIMIT = 10
MAX_TRANSACTION_HISTORY_LIMIT = 20
SPLIT_HISTORY_DEFAULT_LIMIT = 10
MAX_SPLIT_HISTORY_LIMIT = 20
ALBION_MARKET_SETUP_FEE_RATE = 0.025
ALBION_MARKET_SALE_PREMIUM_TAX_RATE = 0.04
ALBION_MARKET_SALE_NONPREMIUM_TAX_RATE = 0.08

CONTENT_TYPES = {
    "roads": {
        "label": "Roads",
    },
    "bz_roam": {
        "label": "BZ Roam",
    },
    "yz_faction": {
        "label": "YZ Faction",
    },
    "rz_faction": {
        "label": "RZ Faction",
    }
}

GEAR_REACTIONS = {
    "tank": "🛡️",
    "dps": "⚔️",
    "healer": "💚",
}

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
