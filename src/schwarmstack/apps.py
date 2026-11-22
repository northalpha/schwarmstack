from django.contrib.admin.apps import AdminConfig


class OTPAdminConfig(AdminConfig):
    """Ersetzt django.contrib.admin: der Admin verlangt ein bestätigtes Zweitfaktor-Gerät."""

    default_site = "schwarmstack.otpadmin.SchwarmstackAdminSite"
