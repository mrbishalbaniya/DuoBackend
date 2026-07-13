"""Global admin search across key models."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q

from accounts.models import Profile
from chat.models import Conversation, Message
from subscriptions.models import SubscriptionPayment, Wallet

User = get_user_model()

SEARCH_LIMIT = 8


def global_search(query: str) -> dict:
    q = (query or "").strip()
    if len(q) < 2:
        return {"query": q, "results": []}

    results = []
    results.extend(_search_users(q))
    results.extend(_search_profiles(q))
    results.extend(_search_payments(q))
    results.extend(_search_conversations(q))
    results.extend(_search_messages(q))
    results.extend(_search_wallets(q))
    return {"query": q, "results": results[:30]}


def _item(category, title, subtitle, url, icon="fas fa-circle"):
    return {"category": category, "title": title, "subtitle": subtitle, "url": url, "icon": icon}


def _search_users(q):
    users = User.objects.filter(Q(username__icontains=q) | Q(email__icontains=q))[:SEARCH_LIMIT]
    return [
        _item("Users", u.username, u.email, f"/admin/auth/user/{u.pk}/change/", "fas fa-user")
        for u in users
    ]


def _search_profiles(q):
    profiles = Profile.objects.filter(Q(full_name__icontains=q) | Q(location__icontains=q))[:SEARCH_LIMIT]
    return [
        _item("Profiles", p.full_name or f"User {p.user_id}", p.location, f"/admin/accounts/profile/{p.pk}/change/", "fas fa-id-card")
        for p in profiles
    ]


def _search_payments(q):
    payments = SubscriptionPayment.objects.filter(
        Q(transaction_uuid__icontains=q) | Q(plan_id__icontains=q)
    )[:SEARCH_LIMIT]
    return [
        _item("Payments", p.transaction_uuid, p.plan_id, f"/admin/subscriptions/subscriptionpayment/{p.pk}/change/", "fas fa-credit-card")
        for p in payments
    ]


def _search_conversations(q):
    if not q.isdigit():
        return []
    convos = Conversation.objects.filter(public_id__icontains=q)[:SEARCH_LIMIT]
    return [
        _item("Chats", f"Conversation {c.public_id}", "", f"/admin/chat/conversation/{c.pk}/change/", "fas fa-comments")
        for c in convos
    ]


def _search_messages(q):
    messages = Message.objects.filter(content__icontains=q)[:SEARCH_LIMIT]
    return [
        _item("Messages", (m.content or "")[:60], f"Conv {m.conversation_id}", f"/admin/chat/message/{m.pk}/change/", "fas fa-envelope")
        for m in messages
    ]


def _search_wallets(q):
    wallets = Wallet.objects.filter(user__username__icontains=q).select_related("user")[:SEARCH_LIMIT]
    return [
        _item("Wallet", w.user.username, f"{w.currency} {w.balance}", f"/admin/subscriptions/wallet/{w.pk}/change/", "fas fa-wallet")
        for w in wallets
    ]
