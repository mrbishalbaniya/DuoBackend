from django.contrib import admin

from .models import (
    BackupCode,
    BiometricCredential,
    LoginHistory,
    SecurityEvent,
    TwoFactorSettings,
    UserDevice,
    UserSession,
)

admin.site.register(TwoFactorSettings)
admin.site.register(BackupCode)
admin.site.register(UserDevice)
admin.site.register(UserSession)
admin.site.register(LoginHistory)
admin.site.register(SecurityEvent)
admin.site.register(BiometricCredential)
