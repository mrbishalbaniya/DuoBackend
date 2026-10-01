"""Training data for Duo's match model, built from real app activity.

Labels
------
* Swipes: LIKE / SUPERLIKE = 1, SKIP = 0 (from-user's reaction to the pair).
* Matches: a conversation where both people wrote at least 3 messages is a
  strong positive (weight 2); a match where nobody replied is a weak negative.

Conversation-starter stats
--------------------------
The first message of each conversation is put in a starter category (see
``matching.ml.starters.categorize``) and marked "replied" if the other person
answered. The trained model stores reply rates per category and uses them to
rank suggestions.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from matching.compatibility import compute_compatibility
from matching.ml.features import pair_features


def build_dataset():
    from chat.models import Conversation, Message
    from matching.models import Match, Swipe

    X, y, w, kinds, engine = [], [], [], [], []

    swipes = Swipe.objects.select_related("from_user__profile", "to_user__profile")
    for s in swipes.iterator(chunk_size=500):
        a = getattr(s.from_user, "profile", None)
        b = getattr(s.to_user, "profile", None)
        if a is None or b is None:
            continue
        X.append(pair_features(a, b).vector())
        engine.append(compute_compatibility(a, b).compatibility_score)
        y.append(0 if s.action == "SKIP" else 1)
        w.append(1.5 if s.action == "SUPERLIKE" else 1.0)
        kinds.append("swipe")

    for m in Match.objects.select_related("user1__profile", "user2__profile"):
        a = getattr(m.user1, "profile", None)
        b = getattr(m.user2, "profile", None)
        if a is None or b is None:
            continue
        convo = Conversation.objects.filter(match=m).first()
        if not convo:
            continue
        counts = defaultdict(int)
        for sender_id in Message.objects.filter(conversation=convo, message_type="text").values_list("sender_id", flat=True):
            counts[sender_id] += 1
        both = counts.get(m.user1_id, 0) >= 3 and counts.get(m.user2_id, 0) >= 3
        silent = sum(counts.values()) == 0
        if both or silent:
            X.append(pair_features(a, b).vector())
            engine.append(compute_compatibility(a, b).compatibility_score)
            y.append(1 if both else 0)
            w.append(2.0 if both else 0.7)
            kinds.append("match")

    return (
        np.asarray(X, dtype=float),
        np.asarray(y, dtype=float),
        np.asarray(w, dtype=float),
        kinds,
        np.asarray(engine, dtype=float),
    )


def starter_reply_stats() -> dict:
    """Reply rate per starter category from real first messages."""
    from chat.models import Conversation, Message
    from matching.ml.starters import categorize

    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"sent": 0, "replied": 0})
    for convo in Conversation.objects.all().only("id"):
        msgs = list(
            Message.objects.filter(conversation=convo, message_type="text")
            .order_by("timestamp")
            .values_list("sender_id", "content")[:20]
        )
        if not msgs:
            continue
        first_sender, first_text = msgs[0]
        cat = categorize(first_text or "")
        stats[cat]["sent"] += 1
        if any(sender != first_sender for sender, _ in msgs[1:]):
            stats[cat]["replied"] += 1
    return dict(stats)
