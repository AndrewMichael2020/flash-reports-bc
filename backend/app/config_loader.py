"""
Configuration loader for Crimewatch Intel backend.

Loads sources from YAML configuration file and syncs them to the database.
"""
import os
import yaml
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session

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
    
    Args:
        db: Database session
        force_update: If True, update existing sources with config values.
                     If False (default), only insert new sources.
    
    Returns:
        Number of sources synced (inserted or updated)
    """
    sources_config = load_sources_config()
    synced_count = 0
    
    for source_data in sources_config:
        # Check if source already exists (by base_url)
        existing = db.query(Source).filter(
            Source.base_url == source_data['base_url']
        ).first()
        
        if existing:
            if force_update:
                # Update existing source
                existing.agency_name = source_data['agency_name']
                existing.jurisdiction = source_data['jurisdiction']
                existing.region_label = source_data['region_label']
                existing.source_type = source_data['source_type']
                existing.parser_id = source_data['parser_id']
                existing.active = source_data['active']
                synced_count += 1
        else:
            # Insert new source
            new_source = Source(
                agency_name=source_data['agency_name'],
                jurisdiction=source_data['jurisdiction'],
                region_label=source_data['region_label'],
                source_type=source_data['source_type'],
                base_url=source_data['base_url'],
                parser_id=source_data['parser_id'],
                active=source_data['active']
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
