# Source Configuration

This directory contains configuration for police newsroom sources that the Crimewatch Intel backend monitors.

## sources.yaml

The `sources.yaml` file defines all available data sources. Each source entry includes:

- **agency_name**: Official name of the police agency
- **jurisdiction**: Province/State code (BC, AB, WA, etc.)
- **region_label**: Human-readable region used for filtering in the UI
- **source_type**: Category of source (RCMP_NEWSROOM, MUNICIPAL_PD_NEWS, STATE_POLICE, etc.)
- **base_url**: Root URL of the newsroom page
- **parser_id**: Which parser to use (`rcmp`, `wordpress`, `municipal_list`)
- **active**: Boolean flag to enable/disable monitoring
- **notes**: (Optional) Additional context about the source

## Adding New Sources

To add a new police newsroom:

1. Open `sources.yaml`
2. Add a new entry under the appropriate regional section:

```yaml
- agency_name: "New Police Department"
  jurisdiction: "BC"
  region_label: "Fraser Valley, BC"
  source_type: "MUNICIPAL_PD_NEWS"
  base_url: "https://example.com/news"
  parser_id: "municipal_list"  # or 'rcmp' or 'wordpress'
  active: true
  notes: "Optional description"
```

3. Restart the backend - sources will be automatically synced to the database

## Available Parsers

- **rcmp**: For RCMP detachment newsrooms (rcmp.ca structure)
- **wordpress**: For WordPress-based newsrooms (e.g., VPD)
- **municipal_list**: For generic list/card-based municipal police newsrooms

## Regions

Currently configured regions:
- Fraser Valley, BC
- Metro Vancouver, BC
- Victoria, BC
- BC Interior
- Calgary, AB (inactive - needs parser customization)
- Edmonton, AB (inactive - needs parser customization)
- Seattle Metro, WA (inactive - needs parser customization)

## Troubleshooting

If a source is not working:

1. Check that `active: true` is set
2. Verify the `base_url` is accessible
3. Check backend logs for parsing errors
4. The parser may need customization for that specific newsroom layout
