from django.db import models


class EmailEvent(models.TextChoices):
    REGISTRATION_OTP = "registration_otp", "Registration verification OTP"
    PASSWORD_RESET_OTP = "password_reset_otp", "Password reset OTP"
    WELCOME = "welcome", "Welcome email"
    LOGIN_VERIFICATION = "login_verification", "Login verification"
    EMAIL_CHANGE = "email_change", "Email change verification"
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed", "Subscription payment confirmed"
    SUBSCRIPTION_FAILED = "subscription_failed", "Subscription payment failed"
    MATCH_NOTIFICATION = "match_notification", "New match notification"
    ADMIN_ANNOUNCEMENT = "admin_announcement", "Admin announcement"
    CONTACT_FORM = "contact_form", "Contact form"
    ACCOUNT_STATUS = "account_status", "Account status change"
    GENERIC = "generic", "Generic transactional"


class EmailStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    RETRIED = "retried", "Retried"


class EmailProvider(models.TextChoices):
    SMTP = "smtp", "SMTP"
    BREVO_API = "brevo_api", "Brevo API"
    RESEND_API = "resend_api", "Resend API"
