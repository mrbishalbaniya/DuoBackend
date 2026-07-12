"""Analytics platform constants."""

ANALYTICS_GROUPS = {
    "analytics_super_admin": "Analytics Super Admin",
    "analytics_admin": "Analytics Admin",
    "analytics_analyst": "Analytics Analyst",
    "analytics_finance": "Analytics Finance",
    "analytics_support": "Analytics Support",
    "analytics_marketing": "Analytics Marketing",
}

REALTIME_GROUP = "analytics_realtime"

CACHE_TTL_SHORT = 30
CACHE_TTL_MEDIUM = 300
CACHE_TTL_LONG = 3600

EVENT_CATEGORIES = [
    ("user", "User"),
    ("revenue", "Revenue"),
    ("matching", "Matching"),
    ("chat", "Chat"),
    ("security", "Security"),
    ("system", "System"),
    ("behavior", "Behavior"),
]
