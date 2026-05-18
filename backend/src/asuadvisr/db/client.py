"""Supabase client wrapper with upsert helpers for the scraper."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, cast

from supabase import Client, create_client

from asuadvisr.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ─── Upsert helpers ───────────────────────────────────────────────────────────


def upsert_course(client: Client, course: dict[str, Any]) -> None:
    client.table("courses").upsert(course, on_conflict="id").execute()


def upsert_section_group(client: Client, group: dict[str, Any]) -> int:
    """Upsert and return the section_group id."""
    res = (
        client.table("section_groups")
        .upsert(group, on_conflict="term_id,course_id,assoc_class_label")
        .execute()
    )
    row = cast(dict[str, Any], res.data[0])
    return int(row["id"])


def upsert_section(client: Client, section: dict[str, Any]) -> None:
    client.table("sections").upsert(section, on_conflict="id").execute()


def replace_meeting_times(client: Client, section_id: int, rows: list[dict[str, Any]]) -> None:
    """Delete existing meeting_times for section and insert fresh rows."""
    client.table("meeting_times").delete().eq("section_id", section_id).execute()
    if rows:
        # Convert time/date objects to ISO strings for JSON serialisation.
        serialised = []
        for r in rows:
            row = dict(r)
            for field in ("start_time", "end_time"):
                if row.get(field) is not None:
                    row[field] = row[field].isoformat()
            for field in ("meeting_start_date", "meeting_end_date"):
                if row.get(field) is not None:
                    row[field] = row[field].isoformat()
            serialised.append(row)
        client.table("meeting_times").insert(serialised).execute()


def upsert_instructor(client: Client, instructor: dict[str, Any]) -> None:
    client.table("instructors").upsert(instructor, on_conflict="emplid").execute()


def replace_section_instructors(
    client: Client, section_id: int, instructors: list[dict[str, Any]]
) -> None:
    """Delete existing section_instructor rows and insert fresh ones."""
    client.table("section_instructors").delete().eq("section_id", section_id).execute()
    if instructors:
        rows = [{"section_id": section_id, "emplid": i["emplid"]} for i in instructors]
        client.table("section_instructors").insert(rows).execute()


def upsert_all(
    client: Client,
    parsed: dict[str, Any],
) -> None:
    """Write one parsed record to the database in dependency order."""
    upsert_course(client, parsed["course"])
    group_id = upsert_section_group(client, parsed["section_group"])

    section = dict(parsed["section"])
    section["section_group_id"] = group_id
    upsert_section(client, section)

    section_id = section["id"]
    replace_meeting_times(client, section_id, parsed["meeting_times"])

    for instr in parsed["instructors"]:
        upsert_instructor(client, instr)
    replace_section_instructors(client, section_id, parsed["instructors"])

    logger.debug("upserted section %s", section_id)
