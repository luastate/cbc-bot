import os

DATA_FILE = os.getenv("CBC_BOT_DATA_FILE", "data.json")
DEFAULT_CURRENCY = os.getenv("CBC_BOT_CURRENCY", "silver")
ADMIN_ROLE_NAMES = ["admin"]
TRANSACTION_HISTORY_DEFAULT_LIMIT = 10
MAX_TRANSACTION_HISTORY_LIMIT = 20
SPLIT_HISTORY_DEFAULT_LIMIT = 10
MAX_SPLIT_HISTORY_LIMIT = 20
ALBION_MARKET_SETUP_FEE_RATE = 0.025
ALBION_MARKET_SALE_PREMIUM_TAX_RATE = 0.04
ALBION_MARKET_SALE_NONPREMIUM_TAX_RATE = 0.08

# Update role names to match server exactly.
CONTENT_TYPES = {
    "roads": {
        "label": "Roads",
        "role_names": ["Roads"],
    },
    "static_dungeon": {
        "label": "Static Dungeon",
        "role_names": ["Static Dungeon"],
    },
    "bz_roam": {
        "label": "BZ Roam",
        "role_names": ["BZ Roam"],
    },
    "yz_faction": {
        "label": "YZ Faction",
        "role_names": ["YZ Faction"],
    },
    "rz_faction": {
        "label": "RZ Faction",
        "role_names": ["RZ Faction"],
    }
}

GEAR_REACTIONS = {
    "tank": "🛡️",
    "dps": "⚔️",
    "healer": "💚",
}

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
