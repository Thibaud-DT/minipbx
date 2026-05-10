from app.config import Settings
from app.services.ami import AMIEventHub, _login_payload, parse_ami_messages


def test_parse_ami_messages_keeps_partial_buffer():
    messages, remaining = parse_ami_messages(
        "Event: ContactStatus\r\nEndpointName: 100\r\n\r\nEvent: Hangup\r\n"
    )

    assert messages == [{"Event": "ContactStatus", "EndpointName": "100"}]
    assert remaining == "Event: Hangup\r\n"


def test_login_payload_uses_configured_credentials():
    settings = Settings(secret_key="test", ami_username="user", ami_password="secret")

    payload = _login_payload(settings)

    assert "Action: Login\r\n" in payload
    assert "Username: user\r\n" in payload
    assert "Secret: secret\r\n" in payload
    assert "Events: on\r\n" in payload


def test_ami_event_hub_maintains_contacts_and_channels():
    hub = AMIEventHub()
    hub.set_connected(True)

    hub.publish(
        "ContactStatus",
        {
            "EndpointName": "100",
            "URI": "sip:100@192.168.1.20:5060",
            "ContactStatus": "Reachable",
            "RoundtripUsec": "12345",
        },
    )
    hub.publish(
        "Newchannel",
        {
            "Channel": "PJSIP/100-00000001",
            "ChannelStateDesc": "Ring",
            "CallerIDNum": "100",
            "Context": "minipbx-internal",
            "Exten": "101",
            "Application": "Dial",
            "AppData": "PJSIP/101",
        },
    )
    snapshot = hub.snapshot()

    assert snapshot.contacts["100"]["status"] == "enregistre"
    assert snapshot.contacts["100"]["latency"] == "12.3"
    assert snapshot.channels["PJSIP/100-00000001"]["state"] == "Ring"

    hub.publish("Hangup", {"Channel": "PJSIP/100-00000001"})
    assert "PJSIP/100-00000001" not in hub.snapshot().channels
