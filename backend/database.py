"""Supabase client setup with automatic local DevStore fallback."""

from functools import lru_cache
from typing import Union
from supabase import Client, create_client

from backend.config import get_settings
from backend.dev_store import DevSupabaseClient, get_dev_store


@lru_cache
def _create_supabase_client(url: str, key: str) -> Client:
    """Create and cache a live Supabase client instance."""
    return create_client(url, key)


def get_supabase_client() -> Union[Client, DevSupabaseClient]:
    """FastAPI dependency returning live Supabase client or seeded DevStore."""
    settings = get_settings()
    if settings.use_dev_store:
        return get_dev_store()
    return _create_supabase_client(settings.supabase_url, settings.supabase_key)
