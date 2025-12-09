"""
Configuration loader for Crimewatch Intel backend.

Loads sources from YAML configuration file and syncs them to the database.
"""
import yaml
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session, load_only

from app.models import Source


def get_config_path() -> Path:
    """Get the path to the sources configuration file."""
    backend_dir = Path(__file__).parent.parent
    config_path = backend_dir / "config" / "sources.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please ensure backend/config/sources.yaml exists."
        )

    return config_path


def load_sources_config() -> List[Dict[str, Any]]:
    """
    Load sources from the YAML configuration file.

    Expected structure:

    sources:
      - agency_name: "Victoria Police Department"
        jurisdiction: "BC"
        region_label: "Victoria, BC"
        source_type: "MUNICIPAL_PD_NEWS"
        base_url: "https://vicpd.ca/about-us/news-releases-dashboard/"
        parser_id: "municipal_list"
        active: true
        notes: "..."
    """
    config_path = get_config_path()

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    if "sources" not in config:
        raise ValueError(f"Invalid config at {config_path}: missing 'sources' key")

    sources = config["sources"] or []

    required_fields = [
        "agency_name",
        "jurisdiction",
        "region_label",
        "source_type",
        "base_url",
        "parser_id",
        "active",
    ]

    for i, source in enumerate(sources):
        missing = [f for f in required_fields if f not in source]
        if missing:
            raise ValueError(
                f"Source entry #{i} missing required fields {missing}: {source}"
            )

    return sources


def sync_sources_to_db(db: Session, force_update: bool = False) -> int:
    """
    Sync sources from config file to database.

    Schema-aware: only reads/writes columns that exist in initial Alembic migration.
    Optional columns like `use_playwright` are left to their DB default.

    Behavior:
    - Match existing rows by base_url.
    - Always sync `active` to match YAML.
    - When force_update=True, also sync agency_name, jurisdiction,
      region_label, source_type, parser_id.
    """
    sources_config = load_sources_config()
    synced_count = 0

    for source_data in sources_config:
        existing = (
            db.query(Source)
            .options(
                load_only(
                    Source.id,
                    Source.agency_name,
                    Source.jurisdiction,
                    Source.region_label,
                    Source.source_type,
                    Source.base_url,
                    Source.parser_id,
                    Source.active,
                    Source.last_checked_at,
                )
            )
            .filter(Source.base_url == source_data["base_url"])
            .first()
        )

        if existing:
            changed = False

            # Always sync `active` so YAML wins for enabling/disabling
            new_active = bool(source_data["active"])
            if existing.active != new_active:
                existing.active = new_active
                changed = True

            if force_update:
                if existing.agency_name != source_data["agency_name"]:
                    existing.agency_name = source_data["agency_name"]
                    changed = True
                if existing.jurisdiction != source_data["jurisdiction"]:
                    existing.jurisdiction = source_data["jurisdiction"]
                    changed = True
                if existing.region_label != source_data["region_label"]:
                    existing.region_label = source_data["region_label"]
                    changed = True
                if existing.source_type != source_data["source_type"]:
                    existing.source_type = source_data["source_type"]
                    changed = True
                if existing.parser_id != source_data["parser_id"]:
                    existing.parser_id = source_data["parser_id"]
                    changed = True

            if changed:
                synced_count += 1

        else:
            # Insert new source
            new_source = Source(
                agency_name=source_data["agency_name"],
                jurisdiction=source_data["jurisdiction"],
                region_label=source_data["region_label"],
                source_type=source_data["source_type"],
                base_url=source_data["base_url"],
                parser_id=source_data["parser_id"],
                active=bool(source_data["active"]),
            )
            db.add(new_source)
            synced_count += 1

    db.commit()
    return synced_count


def get_available_regions() -> List[str]:
    """Return sorted list of unique region labels from config."""
    sources_config = load_sources_config()
    return sorted({s["region_label"] for s in sources_config})


def get_active_parsers() -> List[str]:
    """Return sorted list of parser_ids used by active sources in config."""
    sources_config = load_sources_config()
    return sorted({s["parser_id"] for s in sources_config if s.get("active", False)})