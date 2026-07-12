from django.db.models.signals import post_migrate


def seed_after_migrate(sender, **kwargs):
    if sender.name != "update":
        return
    from update.services.bootstrap import seed_initial_versions

    seed_initial_versions()


def connect_signals():
    post_migrate.connect(seed_after_migrate, dispatch_uid="update_seed_after_migrate")
