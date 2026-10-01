"""Train Duo's own match model from real swipes, matches and chats.

    python manage.py train_match_model            # train, evaluate, activate
    python manage.py train_match_model --dry-run  # evaluate only, save nothing

The new version is activated only if it beats the rule-based engine on
cross-validated AUC (or --force is given), so a bad retrain never ships.
"""
from __future__ import annotations

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from matching.ml.dataset import build_dataset, starter_reply_stats
from matching.ml.features import ALL_NAMES
from matching.ml.model import MatchModel, auc, cross_validate

MIN_SAMPLES = 40


class Command(BaseCommand):
    help = "Train and activate Duo's match model (logistic regression) from app data."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Evaluate only; do not save.")
        parser.add_argument("--force", action="store_true", help="Activate even if it doesn't beat the baseline.")
        parser.add_argument("--l2", type=float, default=1.0, help="L2 regularisation strength.")

    def handle(self, *args, **opts):
        from matching.ml.insights import reset_model_cache
        from matching.models import MatchModelArtifact

        X, y, w, kinds, engine_scores = build_dataset()
        n = len(y)
        if n < MIN_SAMPLES or len(np.unique(y)) < 2:
            raise CommandError(f"Need at least {MIN_SAMPLES} labelled pairs with both outcomes; found {n}.")

        pos = int(y.sum())
        self.stdout.write(f"Samples: {n} ({pos} positive, {n - pos} negative; "
                          f"{kinds.count('swipe')} swipes, {kinds.count('match')} matches)")

        cv = cross_validate(X, y, w, l2=opts["l2"])
        # Baseline: the rule-based engine's overall score on the same pairs.
        baseline = auc(y, engine_scores)
        metrics = {**cv, "baseline_auc": baseline, "samples": n, "positives": pos}
        self.stdout.write(
            f"Cross-validated AUC: {cv['cv_auc']:.3f}   accuracy: {cv['cv_accuracy']:.3f}   "
            f"rule-based baseline AUC: {baseline:.3f}"
        )

        model = MatchModel.fit(X, y, w, l2=opts["l2"])
        model.metrics = metrics
        model.starter_stats = starter_reply_stats()

        top = sorted(zip(ALL_NAMES, model.weights), key=lambda t: -abs(t[1]))[:8]
        self.stdout.write("Most influential features:")
        for name, wt in top:
            self.stdout.write(f"  {name:<18} {wt:+.3f}")
        self.stdout.write(f"Starter reply stats: {model.starter_stats}")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing saved."))
            return

        better = cv["cv_auc"] is not None and baseline is not None and cv["cv_auc"] >= baseline
        if not better and not opts["force"]:
            self.stdout.write(self.style.WARNING(
                "Model did not beat the rule-based baseline; not activated (use --force to override)."
            ))
            MatchModelArtifact.objects.create(payload=model.to_payload(), metrics=metrics, samples=n, is_active=False)
            return

        MatchModelArtifact.objects.filter(is_active=True).update(is_active=False)
        art = MatchModelArtifact.objects.create(payload=model.to_payload(), metrics=metrics, samples=n, is_active=True)
        reset_model_cache()
        self.stdout.write(self.style.SUCCESS(f"Activated {art}"))
