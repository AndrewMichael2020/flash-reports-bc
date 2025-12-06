# Police News Source Tree

A Python CLI tool that discovers, tests, and maps police/law enforcement news sources across British Columbia (BC), Alberta (AB), and Washington State (WA).

## Features

- 🔍 **Automatic Discovery**: Finds news/media endpoints from agency websites
- ✅ **Link Testing**: Verifies all discovered URLs are working (HTTP 200-399)
- 📊 **Format Classification**: Identifies RSS feeds, HTML pages, JSON APIs, and social media links
- 📝 **Markdown Output**: Generates a clean tree structure with clickable, verified links
- 🎨 **Mermaid Graphs**: Optional visual representation of the source tree
- 💾 **JSON Export**: Save results for programmatic use

## Requirements

- Python 3.11+
- Required packages:
  - `requests`
  - `beautifulsoup4`
  - `lxml`

## Installation

```bash
# Clone the repository
git clone https://github.com/AndrewMichael2020/flash-reports-bc.git
cd flash-reports-bc

# Install dependencies
pip install requests beautifulsoup4 lxml

# Make the script executable (optional)
chmod +x police_sources.py
```

## Usage

### Basic Usage

Scan all regions (BC, AB, WA):
```bash
python police_sources.py --region ALL
```

Scan a specific region:
```bash
python police_sources.py --region BC
python police_sources.py --region AB
python police_sources.py --region WA
```

### Advanced Options

Include broken/non-working endpoints in output:
```bash
python police_sources.py --region ALL --include-broken
```

Save results to JSON file:
```bash
python police_sources.py --region ALL --output-json sources.json
```

Generate Mermaid graph:
```bash
python police_sources.py --region BC --mermaid
```

Adjust HTTP timeout (default 5 seconds):
```bash
python police_sources.py --region ALL --timeout 10
```

### Command Line Options

- `--region {BC,AB,WA,ALL}` - Region to scan (default: ALL)
- `--include-broken` - Include non-working endpoints in the tree
- `--output-json FILE` - Save results to a JSON file
- `--timeout SECONDS` - HTTP request timeout (default: 5)
- `--mermaid` - Include Mermaid graph in output

## Supported Regions

### British Columbia (BC)

**RCMP:**
- BC RCMP

**Municipal Police Services:**
- Surrey Police Service
- Vancouver Police Department
- West Vancouver Police Department
- Delta Police Department
- New Westminster Police Department
- Abbotsford Police Department

**Transit Police:**
- Metro Vancouver Transit Police

**Oversight Bodies:**
- Independent Investigations Office of BC (IIOBC)
- Office of the Police Complaint Commissioner (OPCC)

### Alberta (AB)

**RCMP:**
- Alberta RCMP

**Municipal Police Services:**
- Edmonton Police Service
- Calgary Police Service
- Lethbridge Police Service
- Medicine Hat Police Service

**Oversight & Multi-Agency:**
- Alberta Serious Incident Response Team (ASIRT)
- Alberta Law Enforcement Response Teams (ALERT)

### Washington State (WA)

**State Level:**
- Washington State Patrol

**Municipal Police Departments:**
- Seattle Police Department
- Spokane Police Department
- Tacoma Police Department
- Yakima Police Department

**County Sheriffs:**
- Spokane County Sheriff's Office
- King County Sheriff's Office

## Sample Output

```markdown
# Police News Source Tree (BC, AB, WA)

## BC

### RCMP

- **BC RCMP** (https://rcmp.ca/en/bc)
  - [BC RCMP News](https://rcmp.ca/en/bc/news) — HTML_PAGER (200)

### Municipal Police

- **Surrey Police Service** (https://www.surreypolice.ca)
  - [News Releases](https://www.surreypolice.ca/news-releases) — HTML_PAGER (200)

- **Vancouver Police Department** (https://vpd.ca)
  - [News](https://vpd.ca/news/) — HTML_PAGER (200)
  - [News RSS](https://vpd.ca/news/rss.xml) — RSS_NATIVE (200)

## AB

### RCMP

- **Alberta RCMP** (https://rcmp.ca/en/alberta)
  - [Alberta RCMP News](https://rcmp.ca/en/alberta/news) — HTML_PAGER (200)

### Municipal Police

- **Edmonton Police Service** (https://www.edmontonpolice.ca)
  - [Media Releases](https://www.edmontonpolice.ca/News/MediaReleases) — HTML_PAGER (200)

## WA

### State Police

- **Washington State Patrol** (https://wsp.wa.gov)
  - [Media Releases](https://wsp.wa.gov/media/media-releases/) — HTML_PAGER (200)

### Municipal Police

- **Seattle Police Department** (https://spdblotter.seattle.gov)
  - [SPD Blotter](https://spdblotter.seattle.gov/) — HTML_PAGER (200)
  - [SPD Blotter RSS](https://spdblotter.seattle.gov/feed/) — RSS_NATIVE (200)

- **Spokane Police Department** (https://my.spokanecity.org/police/)
  - [Police News This Year](https://my.spokanecity.org/police/news/this-year/) — HTML_PAGER (200)

### Sheriff

- **Spokane County Sheriff's Office** (https://www.spokanecounty.org/1316/Sheriffs-Office)
  - [Media Release Information](https://www.spokanecounty.gov/3954/Media-Release-Information) — HTML_PAGER (200)
  - [Press Releases (alternate)](https://www.spokanecounty.org/1622/Press-Releases) — HTML_PAGER (200)

...
```

## Testing

Run the basic test suite:

```bash
python tests/test_police_sources.py
```

Tests verify:
- URL classification logic (RSS, JSON, HTML, social media)
- URL normalization
- Markdown tree generation
- Data model functionality

## Extending the Tool

### Adding New Agencies

Edit the seed configuration in `police_sources.py`:

```python
BC_SEEDS = {
    "municipal": [
        {
            "name": "Your Police Department",
            "base_url": "https://yourpd.example.com",
            "category": "Municipal Police",
            "override_endpoints": [  # Optional: specify exact endpoints
                {
                    "label": "News Releases",
                    "url": "https://yourpd.example.com/news",
                    "kind": "HTML_PAGER"
                },
            ]
        },
    ],
}
```

### Endpoint Types

The tool classifies endpoints into these types:

- `RSS_NATIVE` - RSS/Atom feeds (.xml, /feed/, /rss)
- `HTML_PAGER` - HTML news pages (default)
- `JSON_API` - JSON API endpoints
- `SOCIAL_PRIMARY` - Social media links (Facebook, Twitter/X, Instagram)
- `PDF_RELEASES` - Direct PDF documents
- `UNKNOWN` - Unclassified

## Architecture

The tool consists of:

1. **Data Models** (`SourceEndpoint`, `Agency`) - Core data structures
2. **Configuration** (`BC_SEEDS`, `AB_SEEDS`, `WA_SEEDS`) - Curated seed URLs
3. **Discovery Logic** - Parses agency websites for news links
4. **HTTP Testing** - Verifies all discovered URLs are working
5. **Output Generators** - Creates Markdown and optional Mermaid graphs
6. **CLI Interface** - Command-line argument handling

## Non-Goals

This tool is designed for **mapping and planning**, not:

- ❌ Full scraping of article content
- ❌ Pagination handling or historical archives
- ❌ Rate-limited bulk downloads
- ❌ ML/NLP classification of article content

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:

1. Add new agencies to the appropriate seed configuration
2. Test your changes with `python tests/test_police_sources.py`
3. Update this README if adding new features
4. Submit a pull request

## Support

For issues or questions, please open an issue on GitHub.
