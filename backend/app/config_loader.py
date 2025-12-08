"""
Configuration loader for Crimewatch Intel backend.

Loads sources from YAML configuration file and syncs them to the database.
"""
import os
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
            "Please ensure config/sources.yaml exists in the backend directory."
        )
    
    return config_path


def load_sources_config() -> List[Dict[str, Any]]:
    """
    Load sources from the YAML configuration file.
    
    Returns:
        List of source dictionaries with keys:
        - agency_name
        - jurisdiction
        - region_label
        - source_type
        - base_url
        - parser_id
        - active
        - notes (optional)
    """
    config_path = get_config_path()
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config or 'sources' not in config:
        raise ValueError("Invalid configuration file: missing 'sources' key")
    
    sources = config['sources']
    
    # Validate required fields
    required_fields = [
        'agency_name', 'jurisdiction', 'region_label',
        'source_type', 'base_url', 'parser_id', 'active'
    ]
    
    for i, source in enumerate(sources):
        for field in required_fields:
            if field not in source:
                raise ValueError(
                    f"Source at index {i} missing required field: {field}"
                )
    
    return sources


def sync_sources_to_db(db: Session, force_update: bool = False) -> int:
    """
    Sync sources from config file to database.

    This function is schema-aware: it only reads/writes columns that are known
    to exist in the initial Alembic migration. Optional columns like
    `use_playwright` are left to their DB default.
    """
    sources_config = load_sources_config()
    synced_count = 0

    for source_data in sources_config:
        # Query only columns that we know exist in the current schema
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
            if force_update:
                existing.agency_name = source_data["agency_name"]
                existing.jurisdiction = source_data["jurisdiction"]
                existing.region_label = source_data["region_label"]
                existing.source_type = source_data["source_type"]
                existing.parser_id = source_data["parser_id"]
                existing.active = source_data["active"]
                synced_count += 1
        else:
            # Insert new source; do not touch optional/use_playwright column
            new_source = Source(
                agency_name=source_data["agency_name"],
                jurisdiction=source_data["jurisdiction"],
                region_label=source_data["region_label"],
                source_type=source_data["source_type"],
                base_url=source_data["base_url"],
                parser_id=source_data["parser_id"],
                active=source_data["active"],
            )
            db.add(new_source)
            synced_count += 1

    db.commit()
    return synced_count


def get_available_regions() -> List[str]:
    """
    Get list of all unique regions from the configuration.
    
    Returns:
        Sorted list of unique region labels
    """
    sources_config = load_sources_config()
    regions = set(source['region_label'] for source in sources_config)
    return sorted(regions)


def get_active_parsers() -> List[str]:
    """
    Get list of all unique parser IDs used by active sources.
    
    Returns:
        Sorted list of unique parser IDs
    """
    sources_config = load_sources_config()
    parsers = set(
        source['parser_id'] 
        for source in sources_config 
        if source.get('active', False)
    )
    return sorted(parsers)
