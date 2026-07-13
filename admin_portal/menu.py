"""Logical sidebar groups for the enterprise admin portal."""

PORTAL_MENU_GROUPS = [
    {
        "id": "dashboard",
        "label": "Dashboard",
        "icon": "fas fa-gauge-high",
        "items": [
            {"label": "Overview", "url_name": "admin:index", "icon": "fas fa-house"},
            {"label": "Analytics", "url": "/admin/analytics/dashboard/", "icon": "fas fa-chart-pie"},
        ],
    },
    {
        "id": "system",
        "label": "System",
        "icon": "fas fa-server",
        "apps": ["site_config", "update"],
    },
    {
        "id": "accounts",
        "label": "Accounts",
        "icon": "fas fa-users",
        "apps": ["accounts", "auth"],
    },
    {
        "id": "matching",
        "label": "Matching",
        "icon": "fas fa-heart",
        "apps": ["matching"],
    },
    {
        "id": "chat",
        "label": "Chat",
        "icon": "fas fa-comments",
        "apps": ["chat"],
    },
    {
        "id": "wallet",
        "label": "Wallet",
        "icon": "fas fa-wallet",
        "models": [
            "subscriptions.Wallet",
            "subscriptions.WalletTransaction",
            "subscriptions.WalletTopUp",
        ],
    },
    {
        "id": "subscriptions",
        "label": "Subscriptions",
        "icon": "fas fa-crown",
        "models": [
            "subscriptions.SubscriptionPlan",
            "subscriptions.SubscriptionPayment",
        ],
    },
    {
        "id": "verification",
        "label": "Verification",
        "icon": "fas fa-shield-check",
        "apps": ["photo_verification"],
    },
    {
        "id": "notifications",
        "label": "Notifications",
        "icon": "fas fa-bell",
        "apps": ["notifications", "email_service"],
    },
    {
        "id": "analytics",
        "label": "Analytics",
        "icon": "fas fa-chart-line",
        "apps": ["analytics"],
    },
    {
        "id": "security",
        "label": "Security",
        "icon": "fas fa-shield-alt",
        "apps": ["security"],
    },
    {
        "id": "activity",
        "label": "Activity",
        "icon": "fas fa-map",
        "apps": ["activity"],
    },
]

QUICK_ACTIONS = [
    {"label": "Add User", "url": "/admin/auth/user/add/", "icon": "fas fa-user-plus", "color": "primary"},
    {"label": "Verify Queue", "url": "/admin/photo_verification/userverification/", "icon": "fas fa-certificate", "color": "accent"},
    {"label": "Send Email", "url": "/admin/email_service/emaillog/", "icon": "fas fa-envelope", "color": "info"},
    {"label": "App Version", "url": "/admin/update/appversion/add/", "icon": "fas fa-mobile-alt", "color": "success"},
    {"label": "View Reports", "url": "/api/analytics/exports/?type=executive&format=pdf", "icon": "fas fa-file-export", "color": "warning"},
    {"label": "Site Settings", "url": "/admin/site_config/sitesettings/", "icon": "fas fa-cog", "color": "muted"},
]
