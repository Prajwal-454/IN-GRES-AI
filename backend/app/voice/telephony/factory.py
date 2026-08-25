"""Provider factory: selects the telephony provider from settings."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.voice.telephony.base import TelephonyProvider
from app.voice.telephony.exotel import ExotelProvider
from app.voice.telephony.mock import MockProvider
from app.voice.telephony.plivo import PlivoProvider
from app.voice.telephony.twilio import TwilioProvider


@lru_cache
def get_provider() -> TelephonyProvider:
    """Return the configured telephony provider (cached per process)."""
    provider = (get_settings().TELEPHONY_PROVIDER or "mock").lower()
    if provider == "twilio":
        return TwilioProvider()
    if provider == "exotel":
        return ExotelProvider()
    if provider == "plivo":
        return PlivoProvider()
    # "mock" and the legacy "simulation" both use the local simulator.
    return MockProvider()


get_telephony_provider = get_provider