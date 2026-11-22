import pytest

from submissions.netutil import client_ip


@pytest.fixture
def req(rf):
    def make(forwarded=None, remote="127.0.0.1"):
        extra = {"REMOTE_ADDR": remote}
        if forwarded is not None:
            extra["HTTP_X_FORWARDED_FOR"] = forwarded
        return rf.get("/", **extra)

    return make


def test_ohne_proxy_zaehlt_remote_addr(req, settings):
    settings.CLIENT_IP_SKIP = 0
    assert client_ip(req("1.2.3.4", remote="198.51.100.9")) == "198.51.100.9"


def test_hinter_tailscale_und_caddy(req, settings):
    settings.CLIENT_IP_SKIP = 1
    # Tailscale schreibt den Client, Caddy hängt 127.0.0.1 an
    assert client_ip(req("203.0.113.7, 127.0.0.1")) == "203.0.113.7"


def test_vom_client_mitgeschickter_wert_wird_ignoriert(req, settings):
    settings.CLIENT_IP_SKIP = 1
    assert client_ip(req("6.6.6.6, 203.0.113.7, 127.0.0.1")) == "203.0.113.7"


def test_zu_kurze_kette_faellt_auf_remote_addr_zurueck(req, settings):
    settings.CLIENT_IP_SKIP = 1
    assert client_ip(req("127.0.0.1")) == "127.0.0.1"
    assert client_ip(req()) == "127.0.0.1"


def test_ungueltiger_eintrag(req, settings):
    settings.CLIENT_IP_SKIP = 1
    assert client_ip(req("kein-ip, 127.0.0.1", remote="127.0.0.1")) == "127.0.0.1"


def test_ipv6(req, settings):
    settings.CLIENT_IP_SKIP = 1
    assert client_ip(req("2001:db8::1, 127.0.0.1")) == "2001:db8::1"
