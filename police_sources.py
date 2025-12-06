#!/usr/bin/env python3
"""
Police News Source Tree Builder

Discovers and tests police/law enforcement news sources for BC, AB, and WA.
Outputs a tree graph in Markdown format with verified working links.
"""

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import List, Literal, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Type definitions
SourceType = Literal[
    "RSS_NATIVE", "HTML_PAGER", "JSON_API", "SOCIAL_PRIMARY", "PDF_RELEASES", "UNKNOWN"
]


@dataclass
class SourceEndpoint:
    """Represents a single news/media endpoint for an agency."""
    kind: SourceType
    label: str  # e.g. "Newsroom", "Media Releases (RSS)"
    url: str
    http_status: Optional[int] = None  # last tested status code
    is_working: bool = False  # True if 200-399


@dataclass
class Agency:
    """Represents a law enforcement agency with its news endpoints."""
    name: str
    jurisdiction: str  # "BC", "AB", "WA"
    category: str  # "Municipal Police", "RCMP", "Sheriff", "Oversight", etc.
    base_url: str
    endpoints: List[SourceEndpoint] = field(default_factory=list)


# ============================================================================
# CONFIGURATION: Seed URLs by Region
# ============================================================================

BC_SEEDS = {
    # RCMP BC
    "rcmp": [
        {
            "name": "BC RCMP",
            "base_url": "https://rcmp.ca/en/bc",
            "category": "RCMP",
            "override_endpoints": [
                {"label": "BC RCMP News", "url": "https://rcmp.ca/en/bc/news", "kind": "HTML_PAGER"},
            ]
        },
    ],
    # Municipal and special police services
    "municipal": [
        {
            "name": "Surrey Police Service",
            "base_url": "https://www.surreypolice.ca",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "News Releases", "url": "https://www.surreypolice.ca/news-releases", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Vancouver Police Department",
            "base_url": "https://vpd.ca",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "News", "url": "https://vpd.ca/news/", "kind": "HTML_PAGER"},
                {"label": "News RSS", "url": "https://vpd.ca/news/rss.xml", "kind": "RSS_NATIVE"},
            ]
        },
        {
            "name": "West Vancouver Police Department",
            "base_url": "https://westvanpolice.ca",
            "category": "Municipal Police",
        },
        {
            "name": "Delta Police Department",
            "base_url": "https://deltapolice.ca",
            "category": "Municipal Police",
        },
        {
            "name": "New Westminster Police Department",
            "base_url": "https://nwpolice.org",
            "category": "Municipal Police",
        },
        {
            "name": "Abbotsford Police Department",
            "base_url": "https://abbypd.ca",
            "category": "Municipal Police",
        },
        {
            "name": "Metro Vancouver Transit Police",
            "base_url": "https://transitpolice.ca",
            "category": "Transit Police",
        },
    ],
    # Oversight bodies
    "oversight": [
        {
            "name": "Independent Investigations Office of BC",
            "base_url": "https://iiobc.ca",
            "category": "Oversight",
            "override_endpoints": [
                {"label": "Media Releases", "url": "https://iiobc.ca/media-releases/", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Office of the Police Complaint Commissioner",
            "base_url": "https://opcc.bc.ca",
            "category": "Oversight",
            "override_endpoints": [
                {"label": "News & Media", "url": "https://opcc.bc.ca/news-media/", "kind": "HTML_PAGER"},
            ]
        },
    ],
}

AB_SEEDS = {
    # RCMP Alberta
    "rcmp": [
        {
            "name": "Alberta RCMP",
            "base_url": "https://rcmp.ca/en/alberta",
            "category": "RCMP",
            "override_endpoints": [
                {"label": "Alberta RCMP News", "url": "https://rcmp.ca/en/alberta/news", "kind": "HTML_PAGER"},
            ]
        },
    ],
    # Municipal police services
    "municipal": [
        {
            "name": "Edmonton Police Service",
            "base_url": "https://www.edmontonpolice.ca",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "Media Releases", "url": "https://www.edmontonpolice.ca/News/MediaReleases", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Calgary Police Service",
            "base_url": "https://www.calgary.ca/cps.html",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "Police News Releases", "url": "https://www.calgary.ca/cps/public-services/news.html", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Lethbridge Police Service",
            "base_url": "https://www.lethbridgepolice.ca",
            "category": "Municipal Police",
        },
        {
            "name": "Medicine Hat Police Service",
            "base_url": "https://www.mhps.ca",
            "category": "Municipal Police",
        },
    ],
    # Oversight and multi-agency
    "oversight": [
        {
            "name": "Alberta Serious Incident Response Team",
            "base_url": "https://www.solgps.alberta.ca/asirt/",
            "category": "Oversight",
            "override_endpoints": [
                {"label": "Media Releases", "url": "https://www.solgps.alberta.ca/asirt/news-media/Pages/default.aspx", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Alberta Law Enforcement Response Teams",
            "base_url": "https://www.alertalberta.ca",
            "category": "Multi-Agency",
        },
    ],
}

WA_SEEDS = {
    # State level
    "state": [
        {
            "name": "Washington State Patrol",
            "base_url": "https://wsp.wa.gov",
            "category": "State Police",
            "override_endpoints": [
                {"label": "Media Releases", "url": "https://wsp.wa.gov/media/media-releases/", "kind": "HTML_PAGER"},
            ]
        },
    ],
    # High-yield city police departments
    "municipal": [
        {
            "name": "Seattle Police Department",
            "base_url": "https://spdblotter.seattle.gov",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "SPD Blotter", "url": "https://spdblotter.seattle.gov/", "kind": "HTML_PAGER"},
                {"label": "SPD Blotter RSS", "url": "https://spdblotter.seattle.gov/feed/", "kind": "RSS_NATIVE"},
            ]
        },
        {
            "name": "Spokane Police Department",
            "base_url": "https://my.spokanecity.org/police/",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "Police News This Year", "url": "https://my.spokanecity.org/police/news/this-year/", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Tacoma Police Department",
            "base_url": "https://tacoma.gov/government/departments/police/",
            "category": "Municipal Police",
            "override_endpoints": [
                {"label": "Tacoma Newsroom", "url": "https://tacoma.gov/tacoma-newsroom/news-list/", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "Yakima Police Department",
            "base_url": "https://www.yakimawa.gov/services/police/",
            "category": "Municipal Police",
        },
    ],
    # High-yield county sheriffs
    "sheriff": [
        {
            "name": "Spokane County Sheriff's Office",
            "base_url": "https://www.spokanecounty.org/1316/Sheriffs-Office",
            "category": "Sheriff",
            "override_endpoints": [
                {"label": "Media Release Information", "url": "https://www.spokanecounty.gov/3954/Media-Release-Information", "kind": "HTML_PAGER"},
                {"label": "Press Releases (alternate)", "url": "https://www.spokanecounty.org/1622/Press-Releases", "kind": "HTML_PAGER"},
            ]
        },
        {
            "name": "King County Sheriff's Office",
            "base_url": "https://kingcounty.gov/depts/sheriff.aspx",
            "category": "Sheriff",
        },
    ],
}


# ============================================================================
# HTTP Testing Logic
# ============================================================================

def test_endpoint(url: str, timeout: int = 5) -> Tuple[bool, Optional[int]]:
    """
    Test if an endpoint is working.
    
    Returns:
        (is_working, http_status)
    """
    try:
        # Try HEAD first
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        
        # If HEAD fails with 405 or 403, try GET
        if response.status_code in [405, 403]:
            response = requests.get(url, timeout=timeout, stream=True, allow_redirects=True)
        
        is_working = 200 <= response.status_code < 400
        return is_working, response.status_code
    except Exception:
        return False, None


# ============================================================================
# Endpoint Discovery Logic
# ============================================================================

def normalize_url(base_url: str, href: str) -> str:
    """Normalize a relative or absolute URL against a base URL."""
    return urljoin(base_url, href)


def classify_url(url: str, content_type: Optional[str] = None) -> SourceType:
    """Classify a URL based on its characteristics."""
    url_lower = url.lower()
    
    # Social media
    social_domains = ['facebook.com', 'twitter.com', 'x.com', 'instagram.com']
    if any(domain in url_lower for domain in social_domains):
        return "SOCIAL_PRIMARY"
    
    # RSS/Feed
    if any(indicator in url_lower for indicator in ['.xml', '.rss', 'feed=rss', '/feed/', '/rss']):
        return "RSS_NATIVE"
    
    # JSON API
    if content_type and 'application/json' in content_type:
        return "JSON_API"
    if '.json' in url_lower or '/api/' in url_lower:
        return "JSON_API"
    
    # PDF releases
    if '.pdf' in url_lower:
        return "PDF_RELEASES"
    
    # Default to HTML pager
    return "HTML_PAGER"


def discover_endpoints(agency_config: dict, timeout: int = 5) -> List[SourceEndpoint]:
    """
    Discover news/media endpoints for an agency.
    
    Args:
        agency_config: Configuration dict with base_url and optional override_endpoints
        timeout: HTTP request timeout in seconds
    
    Returns:
        List of discovered SourceEndpoint objects
    """
    endpoints = []
    base_url = agency_config["base_url"]
    
    # Use override endpoints if provided
    if "override_endpoints" in agency_config:
        for override in agency_config["override_endpoints"]:
            endpoint = SourceEndpoint(
                kind=override["kind"],
                label=override["label"],
                url=override["url"]
            )
            endpoints.append(endpoint)
        return endpoints
    
    # Otherwise, try to discover automatically
    try:
        response = requests.get(base_url, timeout=timeout, allow_redirects=True)
        if response.status_code != 200:
            return endpoints
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for news-related links
        news_keywords = [
            'news', 'newsroom', 'media', 'media-releases', 'press',
            'blotter', 'alerts', 'incident', 'public-information'
        ]
        
        seen_urls = set()
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True).lower()
            
            # Check if link text or href contains news keywords
            if any(keyword in text for keyword in news_keywords) or \
               any(keyword in href.lower() for keyword in news_keywords):
                
                full_url = normalize_url(base_url, href)
                
                # Deduplicate
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                
                # Classify the URL
                kind = classify_url(full_url)
                
                # Create label from link text or last path segment
                label = text if text else urlparse(full_url).path.split('/')[-1]
                label = label[:50]  # Truncate long labels
                
                endpoint = SourceEndpoint(
                    kind=kind,
                    label=label or "News",
                    url=full_url
                )
                endpoints.append(endpoint)
        
        # Also look for RSS/Atom feeds in <link> tags
        for link_tag in soup.find_all('link', type=True):
            link_type = link_tag.get('type', '').lower()
            if 'rss' in link_type or 'atom' in link_type or 'xml' in link_type:
                href = link_tag.get('href')
                if href:
                    full_url = normalize_url(base_url, href)
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        title = link_tag.get('title', 'RSS Feed')
                        endpoint = SourceEndpoint(
                            kind="RSS_NATIVE",
                            label=title,
                            url=full_url
                        )
                        endpoints.append(endpoint)
    
    except Exception:
        # If discovery fails, return empty list
        pass
    
    return endpoints


# ============================================================================
# Data Collection
# ============================================================================

def collect_agencies(region: str, timeout: int = 5) -> List[Agency]:
    """
    Collect and test all agencies for a given region.
    
    Args:
        region: "BC", "AB", "WA", or "ALL"
        timeout: HTTP request timeout in seconds
    
    Returns:
        List of Agency objects with tested endpoints
    """
    agencies = []
    
    # Determine which seed configs to use
    seed_configs = []
    if region == "BC" or region == "ALL":
        for category_key, category_seeds in BC_SEEDS.items():
            seed_configs.extend([(seed, "BC") for seed in category_seeds])
    
    if region == "AB" or region == "ALL":
        for category_key, category_seeds in AB_SEEDS.items():
            seed_configs.extend([(seed, "AB") for seed in category_seeds])
    
    if region == "WA" or region == "ALL":
        for category_key, category_seeds in WA_SEEDS.items():
            seed_configs.extend([(seed, "WA") for seed in category_seeds])
    
    # Process each seed
    for seed_config, jurisdiction in seed_configs:
        agency = Agency(
            name=seed_config["name"],
            jurisdiction=jurisdiction,
            category=seed_config["category"],
            base_url=seed_config["base_url"]
        )
        
        # Discover endpoints
        print(f"Discovering endpoints for {agency.name}...", file=sys.stderr)
        endpoints = discover_endpoints(seed_config, timeout)
        
        # Test each endpoint
        for endpoint in endpoints:
            print(f"  Testing {endpoint.url}...", file=sys.stderr)
            is_working, status = test_endpoint(endpoint.url, timeout)
            endpoint.is_working = is_working
            endpoint.http_status = status
            agency.endpoints.append(endpoint)
            
            # Small delay to be respectful
            time.sleep(0.1)
        
        agencies.append(agency)
    
    return agencies


# ============================================================================
# Output Generation
# ============================================================================

def generate_markdown_tree(agencies: List[Agency], include_broken: bool = False) -> str:
    """
    Generate a Markdown tree representation of agencies and their endpoints.
    
    Args:
        agencies: List of Agency objects
        include_broken: Whether to include broken endpoints
    
    Returns:
        Markdown-formatted string
    """
    # Group by jurisdiction
    by_jurisdiction = {}
    for agency in agencies:
        if agency.jurisdiction not in by_jurisdiction:
            by_jurisdiction[agency.jurisdiction] = []
        by_jurisdiction[agency.jurisdiction].append(agency)
    
    # Build output
    lines = ["# Police News Source Tree (BC, AB, WA)\n"]
    
    for jurisdiction in ["BC", "AB", "WA"]:
        if jurisdiction not in by_jurisdiction:
            continue
        
        lines.append(f"\n## {jurisdiction}\n")
        
        # Group by category within jurisdiction
        by_category = {}
        for agency in by_jurisdiction[jurisdiction]:
            if agency.category not in by_category:
                by_category[agency.category] = []
            by_category[agency.category].append(agency)
        
        for category in sorted(by_category.keys()):
            lines.append(f"\n### {category}\n")
            
            for agency in by_category[category]:
                lines.append(f"\n- **{agency.name}** ({agency.base_url})")
                
                # Filter endpoints
                endpoints_to_show = agency.endpoints
                if not include_broken:
                    endpoints_to_show = [ep for ep in endpoints_to_show if ep.is_working]
                
                if not endpoints_to_show:
                    lines.append("  - _(No working endpoints found)_")
                else:
                    for endpoint in endpoints_to_show:
                        status_str = f"{endpoint.http_status}" if endpoint.http_status else "N/A"
                        if endpoint.is_working:
                            lines.append(f"  - [{endpoint.label}]({endpoint.url}) — {endpoint.kind} ({status_str})")
                        else:
                            lines.append(f"  - [{endpoint.label}]({endpoint.url}) — {endpoint.kind} (BROKEN, status={status_str})")
    
    return "\n".join(lines)


def generate_mermaid_graph(agencies: List[Agency]) -> str:
    """
    Generate a Mermaid mindmap representation.
    
    Args:
        agencies: List of Agency objects
    
    Returns:
        Mermaid-formatted string
    """
    lines = ["```mermaid", "mindmap", "  root((Police News Sources))"]
    
    # Group by jurisdiction
    by_jurisdiction = {}
    for agency in agencies:
        if agency.jurisdiction not in by_jurisdiction:
            by_jurisdiction[agency.jurisdiction] = []
        by_jurisdiction[agency.jurisdiction].append(agency)
    
    for jurisdiction in ["BC", "AB", "WA"]:
        if jurisdiction not in by_jurisdiction:
            continue
        
        lines.append(f"    {jurisdiction}")
        
        for agency in by_jurisdiction[jurisdiction]:
            # Only include agencies with working endpoints
            working_endpoints = [ep for ep in agency.endpoints if ep.is_working]
            if working_endpoints:
                # Escape special characters and limit length
                safe_name = agency.name.replace('"', "'")[:40]
                lines.append(f'      "{safe_name}"')
    
    lines.append("```")
    return "\n".join(lines)


def save_json(agencies: List[Agency], filename: str):
    """Save agencies to a JSON file."""
    data = [asdict(agency) for agency in agencies]
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"JSON output saved to {filename}", file=sys.stderr)


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Discover and test police news sources for BC, AB, and WA"
    )
    parser.add_argument(
        "--region",
        choices=["BC", "AB", "WA", "ALL"],
        default="ALL",
        help="Region to scan (default: ALL)"
    )
    parser.add_argument(
        "--include-broken",
        action="store_true",
        help="Include broken endpoints in output"
    )
    parser.add_argument(
        "--output-json",
        metavar="FILE",
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="HTTP request timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--mermaid",
        action="store_true",
        help="Include Mermaid graph in output"
    )
    
    args = parser.parse_args()
    
    # Collect agencies
    print(f"Scanning region(s): {args.region}", file=sys.stderr)
    agencies = collect_agencies(args.region, args.timeout)
    
    # Generate and output Markdown tree
    markdown = generate_markdown_tree(agencies, args.include_broken)
    print(markdown)
    
    # Optionally add Mermaid graph
    if args.mermaid:
        print("\n## Mermaid Graph\n")
        mermaid = generate_mermaid_graph(agencies)
        print(mermaid)
    
    # Optionally save JSON
    if args.output_json:
        save_json(agencies, args.output_json)


if __name__ == "__main__":
    main()
