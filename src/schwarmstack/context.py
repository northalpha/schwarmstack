from django.conf import settings


def site(request):
    """Werte für alle Seiten (Hinweis auf das Testsystem)."""
    return {"test_system": settings.TEST_SYSTEM}
