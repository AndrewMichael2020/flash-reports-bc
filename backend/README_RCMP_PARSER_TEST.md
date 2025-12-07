# RCMP News Parser - Standalone Test

## Overview

This is a standalone test file (`test_rcmp_news_parsing.py`) designed to parse RCMP detachment news pages and extract news articles with their full text and links using **Playwright browser automation**.

## Purpose

The parser was created to troubleshoot and test web parsing for RCMP news pages like https://rcmp.ca/en/bc/langley/news, extracting structured data including:
- Article title
- Full URL
- Publication date
- Complete article body text

## Why Playwright?

Playwright was chosen as the optimal solution because:
- RCMP websites use JavaScript rendering
- Handles dynamic content reliably
- Explicitly allowed per RCMP's robots.txt
- Most robust solution for modern web scraping
- Works consistently across different RCMP detachment sites

## Dependencies

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

## Installation

```bash
# Install dependencies
pip install playwright beautifulsoup4

# Install Chromium browser
playwright install chromium
```

## Usage

### Basic Usage
```bash
python test_rcmp_news_parsing.py
```

### Custom URL
```bash
python test_rcmp_news_parsing.py --url "https://rcmp.ca/en/bc/surrey/news"
```

### Customize Output and Limit
```bash
python test_rcmp_news_parsing.py \
  --url "https://rcmp.ca/en/bc/langley/news" \
  --max 5 \
  --output my_output.json
```

## Command Line Arguments

- `--url`: URL of the RCMP news listing page (default: `https://rcmp.ca/en/bc/langley/news`)
- `--max`: Maximum number of articles to fetch (default: `10`)
- `--output`: Output JSON file path (default: `rcmp_news_output.json`)

## Output Format

The script generates a JSON file with the following structure:

```json
{
  "source": "https://rcmp.ca/en/bc/langley/news",
  "fetched_at": "2025-12-07T21:39:56.050061",
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
2. Searches for links containing "/news/" with numeric IDs in the href
3. Extracts dates from `<time>` tags or date patterns in text
4. Filters out navigation and non-article links
5. Removes duplicate URLs

### For Article Pages:
1. Tries `<article>` tag first
2. Falls back to `<main>` or content area
3. Searches for divs with "content" or "article" classes
4. Ultimate fallback to `<body>` tag
5. Cleans excessive whitespace and formatting
6. Removes script, style, nav, header, footer elements

## Features

- **Optimal Solution**: Uses Playwright for best reliability
- **Robust Parsing**: Multiple fallback strategies
- **Clean Output**: Properly formatted JSON with all required fields
- **Error Handling**: Graceful handling of network issues and parsing failures
- **Rate Limiting**: 1-second delay between requests to respect server
- **Fully Standalone**: No dependencies on existing codebase

## Robots.txt Compliance

The script respects robots.txt. According to RCMP's robots.txt, Playwright usage is allowed.

## Notes

- The parser includes a 1-second delay between requests to be respectful to the server
- Runs in headless mode by default for efficiency
- Waits for network idle to ensure JavaScript content is loaded
- User agent is set to avoid bot detection
- The script is fully self-contained and doesn't depend on the existing codebase

## Troubleshooting

### Network Issues
If you encounter network/DNS issues:
1. Check your internet connection
2. Verify the URL is accessible from your location
3. Try a different RCMP detachment URL

### No Articles Found
If the parser returns 0 articles:
1. Check the URL is correct and accessible
2. Verify the page structure hasn't changed
3. Inspect the HTML structure manually

### Playwright Installation Issues
If Playwright fails to install:
```bash
# Explicitly install chromium
python -m playwright install chromium

# Or install all browsers
python -m playwright install
```

### Permission Errors
If you get permission errors:
```bash
# On Linux/Mac, you may need to install system dependencies
sudo playwright install-deps chromium
```

## Author

Created: 2025-12-07  
Purpose: Standalone test for troubleshooting RCMP news parsing  
Method: Playwright browser automation (optimal solution)
