from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        from .db_security import lock_down_supabase_data_api

        post_migrate.connect(lock_down_supabase_data_api, dispatch_uid='accounts.lock_down_supabase_data_api')
