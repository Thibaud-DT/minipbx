import asyncio
from dataclasses import dataclass
from typing import Any

from app.config import Settings


EVENTS_THAT_REFRESH_MONITORING = {
    "ContactStatus",
    "DeviceStateChange",
    "Newchannel",
    "Newstate",
    "Hangup",
    "BridgeEnter",
    "BridgeLeave",
    "DialBegin",
    "DialEnd",
}


@dataclass(frozen=True)
class AMIState:
    connected: bool
    last_event: str
    event_count: int
    contacts: dict[str, dict[str, str]]
    channels: dict[str, dict[str, str]]


class AMIEventHub:
    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._connected = False
        self._last_event = ""
        self._event_count = 0
        self._contacts: dict[str, dict[str, str]] = {}
        self._channels: dict[str, dict[str, str]] = {}

    def snapshot(self) -> AMIState:
        return AMIState(
            connected=self._connected,
            last_event=self._last_event,
            event_count=self._event_count,
            contacts={key: value.copy() for key, value in self._contacts.items()},
            channels={key: value.copy() for key, value in self._channels.items()},
        )

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._contacts = {}
            self._channels = {}
        self._event.set()

    def publish(self, event_name: str, message: dict[str, str] | None = None) -> None:
        if message:
            self._apply_event(event_name, message)
        self._last_event = event_name
        self._event_count += 1
        self._event.set()

    def _apply_event(self, event_name: str, message: dict[str, str]) -> None:
        if event_name == "ContactStatus":
            endpoint = message.get("EndpointName") or message.get("AOR")
            if not endpoint:
                return
            status = message.get("ContactStatus", "")
            if status.lower() in {"removed", "unavailable", "unreachable"}:
                self._contacts.pop(endpoint, None)
                return
            self._contacts[endpoint] = {
                "uri": message.get("URI", ""),
                "status": _normalize_contact_status(status),
                "latency": _roundtrip_to_ms(message.get("RoundtripUsec", "")),
            }
            return

        if event_name in {"Newchannel", "Newstate"}:
            channel = message.get("Channel", "")
            if not channel:
                return
            current = self._channels.get(channel, {})
            current.update(
                {
                    "channel": channel,
                    "state": message.get("ChannelStateDesc", current.get("state", "")),
                    "caller_id": message.get("CallerIDNum", current.get("caller_id", "")),
                    "context": message.get("Context", current.get("context", "")),
                    "extension": message.get("Exten", current.get("extension", "")),
                    "application": message.get("Application", current.get("application", "")),
                    "data": message.get("AppData", current.get("data", "")),
                    "duration": current.get("duration", ""),
                    "bridged_channel": message.get("BridgedChannel", current.get("bridged_channel", "")),
                }
            )
            self._channels[channel] = current
            return

        if event_name == "BridgeEnter":
            channel = message.get("Channel", "")
            if not channel:
                return
            current = self._channels.get(channel, {"channel": channel})
            current["bridged_channel"] = message.get("BridgeUniqueid", current.get("bridged_channel", ""))
            self._channels[channel] = current
            return

        if event_name in {"Hangup", "BridgeLeave"}:
            channel = message.get("Channel", "")
            if channel and event_name == "Hangup":
                self._channels.pop(channel, None)

    async def wait_for_update(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self._event.wait(), timeout)
        except TimeoutError:
            return False
        self._event.clear()
        return True


ami_event_hub = AMIEventHub()


def parse_ami_messages(buffer: str) -> tuple[list[dict[str, str]], str]:
    messages = []
    while "\r\n\r\n" in buffer:
        raw, buffer = buffer.split("\r\n\r\n", 1)
        fields: dict[str, str] = {}
        for line in raw.split("\r\n"):
            if ": " not in line:
                continue
            key, value = line.split(": ", 1)
            fields[key] = value
        if fields:
            messages.append(fields)
    return messages, buffer


def start_ami_client(settings: Settings) -> asyncio.Task[Any] | None:
    if not settings.asterisk_apply_enabled or not settings.ami_enabled:
        ami_event_hub.set_connected(False)
        return None
    return asyncio.create_task(_ami_loop(settings))


async def _ami_loop(settings: Settings) -> None:
    while True:
        try:
            await _run_ami_session(settings)
        except asyncio.CancelledError:
            ami_event_hub.set_connected(False)
            raise
        except OSError:
            ami_event_hub.set_connected(False)
            await asyncio.sleep(3)


async def _run_ami_session(settings: Settings) -> None:
    reader, writer = await asyncio.open_connection(settings.ami_bind_address, settings.ami_port)
    ami_event_hub.set_connected(True)
    try:
        await _read_until_message_boundary(reader)
        writer.write(_login_payload(settings).encode("utf-8"))
        await writer.drain()

        buffer = ""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                ami_event_hub.set_connected(False)
                return
            buffer += chunk.decode("utf-8", errors="replace")
            messages, buffer = parse_ami_messages(buffer)
            for message in messages:
                event_name = message.get("Event", "")
                if event_name in EVENTS_THAT_REFRESH_MONITORING:
                    ami_event_hub.publish(event_name, message)
    finally:
        writer.close()
        await writer.wait_closed()
        ami_event_hub.set_connected(False)


async def _read_until_message_boundary(reader: asyncio.StreamReader) -> None:
    buffer = ""
    while "\r\n\r\n" not in buffer:
        chunk = await reader.read(4096)
        if not chunk:
            return
        buffer += chunk.decode("utf-8", errors="replace")


def _login_payload(settings: Settings) -> str:
    return (
        "Action: Login\r\n"
        f"Username: {settings.ami_username}\r\n"
        f"Secret: {settings.ami_password}\r\n"
        "Events: on\r\n"
        "\r\n"
    )


def _normalize_contact_status(value: str) -> str:
    return {
        "Reachable": "enregistre",
        "Created": "enregistre",
        "Available": "enregistre",
        "Removed": "non enregistre",
        "Unreachable": "injoignable",
        "Unavailable": "injoignable",
        "Unknown": "inconnu",
    }.get(value, value or "inconnu")


def _roundtrip_to_ms(value: str) -> str:
    try:
        return f"{int(value) / 1000:.1f}"
    except (TypeError, ValueError):
        return "-"
