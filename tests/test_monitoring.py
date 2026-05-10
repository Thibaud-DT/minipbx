from unittest.mock import patch

from app.config import Settings
from app.database import SessionLocal
from app.models import Extension, SipTrunk
from app.services.ami import ami_event_hub
from app.services.monitoring import collect_monitoring_snapshot, parse_channels, parse_contacts, parse_registrations
from tests.test_auth_flow import create_logged_client


def test_parse_contacts_and_channels():
    contacts = parse_contacts(
        """
  Contact:  100/sip:100@192.168.1.20:5060;ob           3f891 Avail        12.345
  Contact:  101/sip:101@192.168.1.21:5060              7a221 Unavail      nan
"""
    )
    channels = parse_channels(
        "PJSIP/100-00000001!minipbx-internal!101!1!Up!Dial!PJSIP/101,20!100!account!3!1!42!PJSIP/101-00000002\n"
    )

    assert contacts["100"]["status"] == "enregistre"
    assert contacts["100"]["latency"] == "12.345"
    assert contacts["101"]["status"] == "injoignable"
    assert channels[0].channel == "PJSIP/100-00000001"
    assert channels[0].state == "Up"
    assert channels[0].duration == "42"


def test_parse_registrations():
    registrations = parse_registrations(
        """
 <Registration/ServerURI..............................>  <Auth....................>  <Status.......>
==========================================================================================
 trunk-main-registration/sip:sip.example.test           trunk-main-auth              Registered        (exp. 3588s)
 other-registration/sip:other.example.test              other-auth                   Unregistered
"""
    )

    assert registrations["trunk-main-registration"]["registered"] is True
    assert registrations["trunk-main-registration"]["status"] == "enregistre"
    assert registrations["other-registration"]["registered"] is False
    assert registrations["other-registration"]["status"] == "non enregistre"


def test_monitoring_page_and_live_fragment_disabled_mode():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Bureau",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
    )

    page = client.get("/monitoring")
    assert page.status_code == 200
    assert "/monitoring/ws" in page.text

    live = client.get("/monitoring/live")
    assert live.status_code == 200
    assert "Bureau" in live.text
    assert "Supervision Asterisk desactivee" in live.text

    with client.websocket_connect("/monitoring/ws") as websocket:
        snapshot = websocket.receive_json()

    assert snapshot["enabled"] is False
    assert snapshot["extensions"][0]["number"] == "100"
    assert snapshot["extensions"][0]["display_name"] == "Bureau"
    assert "ami" in snapshot
    assert snapshot["ami"]["connected"] is False


def test_monitoring_snapshot_prefers_ami_state_when_connected():
    with SessionLocal() as db:
        extension = Extension(
            number="100",
            display_name="Bureau",
            sip_username="100",
            sip_secret="secret",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
        trunk = SipTrunk(
            name="Operateur",
            host="sip.example.test",
            username="account",
            password_secret="secret",
            transport="udp",
            enabled=True,
        )
        db.add_all([extension, trunk])
        db.commit()

        ami_event_hub.set_connected(True)
        ami_event_hub.publish(
            "ContactStatus",
            {
                "EndpointName": "100",
                "URI": "sip:100@192.168.1.20:5060",
                "ContactStatus": "Reachable",
                "RoundtripUsec": "12000",
            },
        )
        ami_event_hub.publish(
            "Newchannel",
            {
                "Channel": "PJSIP/100-00000001",
                "ChannelStateDesc": "Up",
                "CallerIDNum": "100",
                "Context": "minipbx-internal",
                "Exten": "101",
                "Application": "Dial",
                "AppData": "PJSIP/101",
            },
        )

        def fake_asterisk(command: str) -> str:
            if command == "pjsip show contacts":
                return ""
            if command == "pjsip show registrations":
                return ""
            raise AssertionError(command)

        with patch("app.services.monitoring._asterisk_rx", side_effect=fake_asterisk):
            snapshot = collect_monitoring_snapshot(db, Settings(secret_key="test", asterisk_apply_enabled=True))

    assert snapshot.message == "Supervision active via PJSIP et evenements AMI."
    assert snapshot.extensions[0].registered is True
    assert snapshot.extensions[0].active_channels == 1
    assert snapshot.trunks[0].status == "non surveille"
    assert snapshot.active_calls[0].channel == "PJSIP/100-00000001"
    ami_event_hub.set_connected(False)


def test_monitoring_snapshot_uses_pjsip_cli_contact_with_sip_username():
    with SessionLocal() as db:
        extension = Extension(
            number="100",
            display_name="Bureau",
            sip_username="user-100",
            sip_secret="secret",
            voicemail_enabled=True,
            voicemail_pin="0100",
            outbound_enabled=True,
            inbound_enabled=True,
            enabled=True,
        )
        db.add(extension)
        db.commit()

        ami_event_hub.set_connected(True)

        def fake_asterisk(command: str) -> str:
            if command == "pjsip show contacts":
                return "Contact:  user-100/sip:user-100@192.168.1.20:5060  3f891 Avail  12.345"
            if command == "pjsip show registrations":
                return ""
            raise AssertionError(command)

        with patch("app.services.monitoring._asterisk_rx", side_effect=fake_asterisk):
            snapshot = collect_monitoring_snapshot(db, Settings(secret_key="test", asterisk_apply_enabled=True))

    assert snapshot.extensions[0].registered is True
    assert snapshot.extensions[0].contact_uri == "sip:user-100@192.168.1.20:5060"
    assert snapshot.extensions[0].status == "enregistre"
    ami_event_hub.set_connected(False)


def test_monitoring_snapshot_collects_trunk_registration_from_cli():
    with SessionLocal() as db:
        trunk = SipTrunk(
            name="Operateur",
            host="sip.example.test",
            username="account",
            password_secret="secret",
            transport="udp",
            enabled=True,
        )
        db.add(trunk)
        db.commit()

        def fake_asterisk(command: str) -> str:
            if command == "pjsip show contacts":
                return ""
            if command == "core show channels concise":
                return ""
            if command == "pjsip show registrations":
                return "trunk-main-registration/sip:sip.example.test trunk-main-auth Registered (exp. 3588s)"
            raise AssertionError(command)

        with patch("app.services.monitoring._asterisk_rx", side_effect=fake_asterisk):
            snapshot = collect_monitoring_snapshot(db, Settings(secret_key="test", asterisk_apply_enabled=True))

    assert snapshot.trunks[0].name == "Operateur"
    assert snapshot.trunks[0].registered is True
    assert snapshot.trunks[0].status == "enregistre"
