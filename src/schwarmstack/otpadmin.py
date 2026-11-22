from django_otp.admin import OTPAdminSite


class SchwarmstackAdminSite(OTPAdminSite):
    """Admin mit 2FA (django-otp): Anmeldung nur mit Passwort UND Einmalcode.

    OTPAdminSite.has_permission verlangt user.is_verified(); ohne eingerichtetes Gerät
    gibt es keinen Zugang (Einrichtung: schwarmstack-manage otp_setup <benutzer>).
    """

    site_header = "Schwarmstack"
    site_title = "Schwarmstack"
    index_title = "Verwaltung"
