"""
Channel abstraction layer.

Each channel has a prompt addendum (injected into the system turn so Alex
knows what medium it is on), a max_tokens cap, and optional response
post-processing.

Production wiring (not yet implemented — requires external credentials):
  SMS   → Twilio Messaging API   webhook: POST /inbound/sms
  Email → SendGrid Inbound Parse webhook: POST /inbound/email
  Voice → Twilio Voice + TTS     webhook: POST /inbound/voice
  Chat  → SSE over HTTP          endpoint: POST /chat
"""
from dataclasses import dataclass


@dataclass
class ChannelConfig:
    name: str
    prompt_addendum: str
    max_tokens: int
    icon: str          # displayed in UI
    color: str         # hex, used for channel badge

    def format_response(self, text: str) -> str:
        return text


@dataclass
class _SMSConfig(ChannelConfig):
    def format_response(self, text: str) -> str:
        if len(text) <= 160:
            return text
        truncated = text[:157]
        cut = truncated.rfind(" ")
        return (truncated[:cut] if cut > 100 else truncated) + "…"


CHANNELS: dict[str, ChannelConfig] = {
    "chat": ChannelConfig(
        name="Web Chat",
        prompt_addendum=(
            "CHANNEL: Web chat. Conversational, can use line breaks. "
            "Streaming response — write continuously."
        ),
        max_tokens=1024,
        icon="chat",
        color="#1e40af",
    ),
    "sms": _SMSConfig(
        name="SMS",
        prompt_addendum=(
            "CHANNEL: SMS text message. "
            "CRITICAL — your entire reply must be 160 characters or fewer. "
            "No greetings, no pleasantries, no bullet points. "
            "Ultra-concise. Fit the FDCPA disclosure in the 160 chars."
        ),
        max_tokens=80,
        icon="sms",
        color="#065f46",
    ),
    "email": ChannelConfig(
        name="Email",
        prompt_addendum=(
            "CHANNEL: Email. Write a complete email: start with 'Subject: ...' "
            "on the first line, then a blank line, then a warm greeting, body, "
            "and a sign-off from Alex at Premier Bank. Can be detailed."
        ),
        max_tokens=1024,
        icon="email",
        color="#6d28d9",
    ),
    "voice": ChannelConfig(
        name="Voice",
        prompt_addendum=(
            "CHANNEL: Phone call (IVR / live agent handoff). "
            "Speak in short natural sentences — no bullet points, no markdown. "
            "Max 60 words. Punctuation implies pauses."
        ),
        max_tokens=200,
        icon="voice",
        color="#b45309",
    ),
}


def get_config(channel: str) -> ChannelConfig:
    return CHANNELS.get(channel, CHANNELS["chat"])
