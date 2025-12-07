# RCMP News Parser - Standalone Test

## Overview

This is a standalone test file (`test_rcmp_news_parsing.py`) designed to parse RCMP detachment news pages and extract news articles with their full text and links.

## Purpose

The parser was created to troubleshoot and test web parsing for RCMP news pages like https://rcmp.ca/en/bc/langley/news, extracting structured data including:
- Article title
- Full URL
- Publication date
- Complete article body text

## Dependencies

The parser supports three different methods with different dependency requirements:

### Method 1: Mock (No dependencies)
For testing the parser logic with sample data:
```bash
# No additional dependencies needed
```

### Method 2: HTTPX (Lightweight)
For simple HTTP requests (faster, but may miss JavaScript-rendered content):
```bash
pip install httpx beautifulsoup4
```

### Method 3: Playwright (Recommended)
For full browser automation (handles JavaScript-rendered content):
```bash
pip install playwright beautifulsoup4
playwright install chromium
```

## Installation

```bash
# Install dependencies based on your chosen method
# For HTTPX:
pip install httpx beautifulsoup4

# For Playwright (recommended):
pip install playwright beautifulsoup4
playwright install chromium
```

## Usage

### Basic Usage (Mock Data)
```bash
python test_rcmp_news_parsing.py --method mock
```

### With HTTPX (Fast, Simple)
```bash
python test_rcmp_news_parsing.py --method httpx
```

### With Playwright (Robust, Handles JS)
```bash
python test_rcmp_news_parsing.py --method playwright
```

### Custom Parameters
```bash
python test_rcmp_news_parsing.py \
  --method playwright \
  --url "https://rcmp.ca/en/bc/langley/news" \
  --max 10 \
  --output my_output.json
```

## Command Line Arguments

- `--method`: Fetching method - `playwright`, `httpx`, or `mock` (default: `mock`)
- `--url`: URL of the RCMP news listing page (default: `https://rcmp.ca/en/bc/langley/news`)
- `--max`: Maximum number of articles to fetch (default: `10`)
- `--output`: Output JSON file path (default: `rcmp_news_output.json`)

## Output Format

The script generates a JSON file with the following structure:

```json
{
  "source": "https://rcmp.ca/en/bc/langley/news",
  "method": "mock",
  "fetched_at": "2025-12-07T21:38:31.568350",
  "article_count": 2,
  "articles": [
    {
      "title": "Article Title",
      "url": "https://rcmp.ca/en/bc/langley/news/2025/11/4348078",
      "published_date": "November 29, 2025",
      "body": "Full article text content..."
    }
  ]
}
```

## Example Output

Based on the example URL https://rcmp.ca/en/bc/langley/news/2025/11/4348078, the parser extracts:

```
News release

Langley RCMP investigating pedestrian involved collision
November 29, 2025 - Langley, British Columbia
From: Langley RCMP

On this page
Content
Contacts

Content
File Number # 2025-38981

On November 28, 2025, at approximately 4:37 p.m. Langley RCMP responded to a report of a collision between a vehicle and a pedestrian in the 3700 block of 224 Street, Langley.

Officers, along with first responders from the BC Ambulance Service and Township of Langley Fire Department, attended the area and located the pedestrian who had sustained serious injuries. The pedestrian was promptly transported to a local area hospital.

The driver of the vehicle remained on scene and is cooperating with police. "Speed and impairment are not believed to be factors that contributed to this collision," said Sergeant Zynal Sharoom of the Langley RCMP.

Anyone who was in the area at the time that witnessed this collision or has dash camera footage is asked to contact the Langley RCMP at 604-532-3200 and quote file number 2025-38981.
```

## Parsing Strategies

The parser uses multiple strategies for robustness:

### For Listing Pages:
1. Looks for `<article>`, `<li>`, or `<div>` elements with news-related classes
2. Searches for links containing "/news/" in the href
3. Extracts dates from `<time>` tags or date patterns in text
4. Filters out navigation and non-article links

### For Article Pages:
1. Tries `<article>` tag first
2. Falls back to `<main>` or content area
3. Searches for divs with "content" or "article" classes
4. Ultimate fallback to `<body>` tag
5. Cleans excessive whitespace and formatting

## Method Comparison

| Method | Speed | Robustness | Use Case |
|--------|-------|------------|----------|
| Mock | Instant | N/A | Testing parser logic |
| HTTPX | Fast | Good | Static HTML sites |
| Playwright | Slower | Excellent | JavaScript-heavy sites |

## Robots.txt Compliance

The script respects robots.txt. According to RCMP's robots.txt, Playwright usage is allowed.

## Notes

- The parser includes a 1-second delay between requests to be respectful to the server
- All methods use the same extraction logic for consistency
- The script is fully self-contained and doesn't depend on the existing codebase
- Error handling is built-in for network issues and parsing failures

## Troubleshooting

### Network Issues
If you encounter network/DNS issues:
1. Try the `--method mock` option to test with sample data
2. Check your internet connection
3. Verify the URL is accessible from your location

### No Articles Found
If the parser returns 0 articles:
1. Check the URL is correct and accessible
2. Try using Playwright method as it handles JavaScript better
3. Inspect the HTML structure manually to verify the parsing logic

### Playwright Installation Issues
If Playwright fails to install:
```bash
# Explicitly install chromium
python -m playwright install chromium

# Or install all browsers
python -m playwright install
```

## Author

Created: 2025-12-07  
Purpose: Standalone test for troubleshooting RCMP news parsing
