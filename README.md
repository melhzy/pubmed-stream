# pubmed-stream

[![PyPI version](https://badge.fury.io/py/pubmed-stream.svg)](https://pypi.org/project/pubmed-stream/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for downloading PubMed Central (PMC) full-text articles with support for concurrent downloads, automatic rate limiting, metadata extraction, and multiple output formats.

**Built on NCBI E-utilities API** for reliable, standards-compliant access to biomedical literature.

## Overview

`pubmed-stream` simplifies the process of downloading scientific literature from PubMed Central by leveraging the **NCBI E-utilities API** (ESearch and EFetch):
- **Searching PMC directly** for guaranteed full-text availability
- **Extracting structured metadata** from JATS XML (title, authors, abstract, keywords, DOI, etc.)
- **Supporting multiple formats**: plain text, raw XML, or both in a single JSON file
- **Handling concurrent downloads** with configurable thread pools
- **Respecting NCBI rate limits** with automatic detection and retry logic
- **Providing both CLI and Python API** for flexible integration

Built for researchers and data scientists who need efficient, reliable access to biomedical literature.

## Quick Start

```bash
# Install
pip install .

# Download articles (CLI)
pubmed-stream download "gut microbiome" --max-results 50

# Python API
from pubmed_stream import search_and_download
stats = search_and_download(
    keyword="CRISPR gene editing",
    max_results=100,
    fmt="text"
)
print(f"Downloaded {stats.successful} articles in {stats.duration_seconds:.1f}s")
```

## Table of Contents

- [Installation](#installation)
- [How It Works](#how-it-works)
- [Configuration](#configuration-optional)
- [CLI Usage](#cli-usage)
- [Python API](#python-api)
- [Output Format](#output-format)
- [Use Cases](#use-cases)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Installation

### From PyPI (Recommended)

```bash
pip install pubmed-stream
```

### From Source

```bash
# Clone the repository
git clone https://github.com/melhzy/pubmed-stream.git
cd pubmed-stream

# Install in standard mode
pip install .

# Or install in development mode (editable install)
pip install -e ".[dev]"
```

### Requirements

- Python 3.8+
- [requests](https://pypi.org/project/requests/) (only runtime dependency)

Development dependencies (optional):
- pytest (for testing)
- ruff (for linting)

## How It Works

### Architecture

The library follows a modular design with three main components, all built on **NCBI E-utilities**:

1. **Search Module** (`esearch_pmc`)
   - Uses NCBI E-utilities **ESearch** to query PMC database directly
   - Returns PMC IDs for articles with guaranteed full-text availability
   - Handles pagination and result limiting

2. **Download Module** (`efetch_pmc`)
   - Uses NCBI E-utilities **EFetch** to retrieve full XML article data from PMC
   - Extracts structured metadata using JATS XML parsing
   - Converts XML to plain text (optional)
   - Saves in requested format(s)

3. **Orchestration Layer** (`search_and_download`)
   - Combines search and download operations
   - Manages concurrent downloads with thread pools
   - Handles rate limiting, retries, and error recovery
   - Tracks statistics (success/failure/skipped counts)

### Search Strategy

**Direct PMC Search**: Unlike some tools that search PubMed and then try to find PMC links, this library searches PMC directly. This ensures:
- All results have full-text available
- No broken links or paywalled content
- Faster, more reliable downloads
- Better results for generic queries like "microbiome" or "CRISPR"

### Data Flow

```
User Query → PMC Search → PMC IDs → Concurrent Downloads → Parse XML → Extract Metadata → Save JSON
     ↓            ↓            ↓             ↓                  ↓              ↓            ↓
 "microbiome"  E-Search   [123, 456]    Thread Pool      JATS Parser    {title, authors}  PMC*.json
```

### Output Format Options

All formats save as `.json` files with different content:

**`"text"` (default)**: JSON with plain-text content
```json
{
  "pmcid": "PMC12345678",
  "metadata": {"title": "...", "authors": [...]},
  "text": "Introduction\nThis study examines..."
}
```

**`"xml"`**: JSON with raw JATS XML string
```json
{
  "pmcid": "PMC12345678",
  "metadata": {"title": "...", "authors": [...]},
  "xml": "<article>...</article>"
}
```

**`"both"`**: JSON with both XML and text
```json
{
  "pmcid": "PMC12345678",
  "metadata": {"title": "...", "authors": [...]},
  "xml": "<article>...</article>",
  "text": "Introduction\nThis study examines..."
}
```

**Why unified JSON?**
- Consistent file handling (always `.json`)
- Metadata always included
- Easy to query and filter
- Smaller storage (text-only is ~50% smaller than XML)
- Backward compatible with existing pipelines

## Configuration (optional)

Set these environment variables for best results:

```bash
# PowerShell
$env:NCBI_API_KEY = "YOUR_KEY"   # raises rate limit from 3→10 req/s
$env:NCBI_EMAIL   = "you@example.com"

# Bash / Zsh
export NCBI_API_KEY="YOUR_KEY"
export NCBI_EMAIL="you@example.com"
```

You can also pass `--api-key` / `--email` on the command line.

### Rate Limits

NCBI enforces rate limits on API requests:

- **Without API key**: 3 requests/second
- **With API key**: 10 requests/second

The library **automatically detects** whether you have an API key and adjusts the rate limit accordingly:
- With API key: 0.1s between requests (10 req/s)
- Without API key: 0.34s between requests (3 req/s)

You can override this with `--rate-limit` if needed, but the auto-detection works well for most cases.

**Recommendation**: Get a free API key to download ~3x faster. Without a key, the library still works but is slower.

## CLI usage

After installation the `pubmed-stream` command is available:

```bash
# Download up to 50 articles as JSON (default, concurrent)
pubmed-stream download "frailty cytokines" --max-results 50

# Sequential mode for unstable networks
pubmed-stream download "gut microbiome" --sequential

# Custom output directory
pubmed-stream download "Alzheimer microbiome" -o ./my_papers

# Verbose logging
pubmed-stream download "frailty" -v --max-results 5

# Show version
pubmed-stream --version
```

The same interface is available via `python -m pubmed_stream`:

```bash
python -m pubmed_stream download "frailty cytokines" --max-results 50
```

### CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `keyword` | PubMed search query (positional) | required |
| `--max-results` | Maximum articles to download | 100 |
| `--format` | Output format: `text`, `xml`, `both` (all save as `.json`) | `text` |
| `--output-dir`, `-o` | Base output directory | `./publications` |
| `--api-key` | NCBI API key | `NCBI_API_KEY` env var |
| `--email` | Contact email for NCBI | `NCBI_EMAIL` env var |
| `--sequential` | Disable concurrent downloads | concurrent |
| `--workers` | Concurrent thread count | 5 |
| `--exclude-text` | Omit `text` field in JSON (~30% smaller) | included |
| `--rate-limit` | Min seconds between requests | auto: 0.1 with key, 0.34 without |
| `--user-agent` | Custom HTTP `User-Agent` | `pubmed-stream/<ver>` |
| `--verbose`, `-v` | DEBUG-level logging | INFO |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | At least one article downloaded (or all already cached) |
| 1 | No results found for the query |
| 2 | All download attempts failed |

## Python API

### Basic Usage

```python
from pubmed_stream import search_and_download

# Download articles with default settings
stats = search_and_download(
    keyword="gut microbiome inflammation",
    max_results=50,
    fmt="text",  # or "xml", "both"
    output_dir="publications",
)

print(f"Downloaded: {stats.successful}")
print(f"Skipped (already exist): {stats.skipped}")
print(f"Failed: {stats.failed}")
print(f"Success rate: {stats.success_rate:.1f}%")
print(f"Duration: {stats.duration_seconds:.1f}s")
```

### Advanced Usage

```python
from pubmed_stream import search_and_download
from pathlib import Path

# Full control over all parameters
stats = search_and_download(
    keyword="CRISPR gene editing",
    max_results=100,
    fmt="both",              # Save both XML and text
    api_key="your_api_key",  # Or use NCBI_API_KEY env var
    use_concurrent=True,     # Enable parallel downloads
    max_workers=10,          # Use 10 threads
    include_text=True,       # Include plain-text field
    output_dir=Path("./research/crispr"),
    user_agent="MyResearchBot/1.0",
    email="researcher@university.edu",
    rate_limit=0.15,         # Custom rate limit
)

# Access detailed statistics
print(f"Total found in PMC: {stats.total_found}")
print(f"Requested: {stats.requested}")
print(f"Output: {stats.output_dir}")
```

### Low-Level API

For more control, use the underlying functions:

```python
from pubmed_stream import esearch_pmc, efetch_pmc, create_session, RateLimiter
from pathlib import Path

# Create session and rate limiter
session = create_session("MyApp/1.0")
rate_limiter = RateLimiter(0.1)  # 10 req/s

# Search for PMC IDs
pmcids, total_found = esearch_pmc(
    term="microbiome AND aging",
    max_results=20,
    api_key="your_key",
    session=session,
    rate_limiter=rate_limiter
)

print(f"Found {len(pmcids)} PMC IDs (total: {total_found})")

# Download individual articles
for pmcid in pmcids:
    success, status = efetch_pmc(
        pmcid=pmcid,
        out_dir=Path("downloads"),
        fmt="text",
        api_key="your_key",
        session=session,
        rate_limiter=rate_limiter,
        include_text=True
    )
    
    if success:
        print(f"✓ Downloaded PMC{pmcid}")
    else:
        print(f"✗ Failed PMC{pmcid}: {status}")

session.close()
```

### Metadata Extraction

The library automatically extracts metadata from JATS XML:

```python
from pubmed_stream import extract_metadata_from_pmc_xml

xml_content = """<article>...</article>"""  # Your PMC XML

metadata = extract_metadata_from_pmc_xml(xml_content)

# Available metadata fields
print(metadata.get("title"))          # Article title
print(metadata.get("journal"))        # Journal name
print(metadata.get("doi"))            # DOI
print(metadata.get("pmid"))           # PubMed ID
print(metadata.get("pmcid"))          # PMC ID
print(metadata.get("authors"))        # List of authors
print(metadata.get("abstract"))       # Abstract text
print(metadata.get("keywords"))       # Keywords list
print(metadata.get("year"))           # Publication year
print(metadata.get("pub_date"))       # Full publication date
```

## Output Format

### Directory Structure

Articles are organized by search query:

```
publications/
  gut_microbiome_inflammation/
    PMC12345678.json
    PMC12345679.json
    PMC12345680.json
  alzheimer_disease/
    PMC11111111.json
    PMC22222222.json
```

Query strings are slugified (spaces→underscores, special characters removed) for clean directory names.

### JSON Schema

Each JSON file contains:

```json
{
  "pmcid": "PMC12345678",
  "source": "PMC",
  "download_date": "2026-02-17T12:30:45.123456",
  "metadata": {
    "title": "The Role of Gut Microbiome in Inflammation",
    "journal": "Nature Medicine",
    "journal_title": "Nature Medicine",
    "journal_nlm_ta": "Nat Med",
    "journal_iso_abbrev": "Nat. Med.",
    "doi": "10.1038/s41591-024-12345-6",
    "pmid": "38123456",
    "pmcid": "PMC12345678",
    "year": "2024",
    "month": "11",
    "day": "15",
    "pub_date": {
      "year": "2024",
      "month": "11",
      "day": "15"
    },
    "authors": [
      "Smith, John A.",
      "Johnson, Mary B.",
      "Williams, Robert C."
    ],
    "abstract": "Background: The gut microbiome plays a crucial role...",
    "keywords": [
      "microbiome",
      "inflammation",
      "gut health"
    ]
  },
  "text": "Introduction\nThe human gut microbiome comprises...",
  "xml": "<article>...</article>"
}
```

**Field descriptions:**
- `pmcid`: PubMed Central identifier
- `source`: Always "PMC"
- `download_date`: ISO 8601 timestamp
- `metadata`: Structured article information
- `text`: Plain-text content (if `fmt="text"` or `fmt="both"`)
- `xml`: Raw JATS XML string (if `fmt="xml"` or `fmt="both"`)

### Format Comparison

| Format | File Type | Contains | Use Case | Size |
|--------|-----------|----------|----------|------|
| `text` | `.json` | metadata + text | Vector DBs, search, NLP | Smallest (~50% of XML) |
| `xml` | `.json` | metadata + xml | Section parsing, structure analysis | Medium |
| `both` | `.json` | metadata + xml + text | Comprehensive analysis | Largest |

## Use Cases

### 1. Literature Review & Meta-Analysis

```python
# Download recent papers on a specific topic
stats = search_and_download(
    keyword="COVID-19 vaccine efficacy",
    max_results=200,
    fmt="text",
    output_dir="covid19_review"
)

# Process downloaded articles
import json
from pathlib import Path

for json_file in Path("covid19_review/covid_19_vaccine_efficacy").glob("*.json"):
    with open(json_file) as f:
        article = json.load(f)
    
    print(f"Title: {article['metadata']['title']}")
    print(f"Year: {article['metadata']['year']}")
    print(f"Abstract: {article['metadata']['abstract'][:200]}...")
```

### 2. Vector Database Embedding

```python
# Download for embedding into vector database
stats = search_and_download(
    keyword="machine learning healthcare",
    max_results=1000,
    fmt="text",  # Plain text is ideal for embeddings
    include_text=True
)

# Example: Embed into ChromaDB
import chromadb
from pathlib import Path
import json

client = chromadb.Client()
collection = client.create_collection("medical_papers")

for json_file in Path("publications/machine_learning_healthcare").glob("*.json"):
    with open(json_file) as f:
        article = json.load(f)
    
    collection.add(
        documents=[article["text"]],
        metadatas=[{
            "title": article["metadata"]["title"],
            "year": article["metadata"]["year"],
            "doi": article["metadata"].get("doi", ""),
        }],
        ids=[article["pmcid"]]
    )
```

### 3. Section-Level Analysis

```python
# Download with XML for detailed structure parsing
stats = search_and_download(
    keyword="CRISPR therapy clinical trials",
    max_results=50,
    fmt="xml"  # Get raw XML for section extraction
)

# Parse sections from XML
import xml.etree.ElementTree as ET
import json
from pathlib import Path

for json_file in Path("publications/crispr_therapy_clinical_trials").glob("*.json"):
    with open(json_file) as f:
        article = json.load(f)
    
    # Parse XML to extract sections
    root = ET.fromstring(article["xml"])
    
    # Find all sections with sec-type attribute
    for sec in root.findall(".//sec[@sec-type]"):
        sec_type = sec.get("sec-type")
        title = sec.find("title")
        
        if title is not None:
            print(f"Section: {sec_type} - {title.text}")
```

### 4. Batch Processing with Keywords

```python
# Process multiple queries from CSV
import pandas as pd

keywords_df = pd.read_csv("research_keywords.csv")

for _, row in keywords_df.iterrows():
    print(f"Processing: {row['keyword']}")
    
    stats = search_and_download(
        keyword=row['keyword'],
        max_results=row['max_articles'],
        fmt="both",  # Get both formats for flexibility
        output_dir="batch_download"
    )
    
    print(f"  Downloaded: {stats.successful}, Success rate: {stats.success_rate:.1f}%")
```

## Troubleshooting

### Common Issues

**1. "0 downloads" but high PMC result count**
- **Cause**: Files already downloaded (skipped)
- **Solution**: Check `stats.skipped` - this is actually success! Delete folder to re-download.

**2. Rate limiting (HTTP 429)**
- **Cause**: Exceeding NCBI rate limits
- **Solution**: 
  - Get a free API key (increases limit from 3→10 req/s)
  - Use `--rate-limit` to slow down: `--rate-limit 0.5`
  - The library automatically retries with backoff

**3. "Unavailable" articles**
- **Cause**: Article not in PMC or embargoed
- **Solution**: Normal - not all PubMed articles have PMC full-text. The library only returns available articles.

**4. Network timeouts**
- **Cause**: Unstable internet connection
- **Solution**: Use `--sequential` mode: `pubmed-stream download "query" --sequential`

**5. Memory issues with large downloads**
- **Cause**: Processing too many articles concurrently
- **Solution**: Reduce workers: `--workers 2` or use `--sequential`

### Debugging

Enable verbose logging to see detailed information:

```bash
pubmed-stream download "microbiome" -v --max-results 10
```

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from pubmed_stream import search_and_download
stats = search_and_download(keyword="test", max_results=5)
```

## Performance Tuning

### Concurrent vs Sequential

**Concurrent (default)**: Faster for stable networks
```bash
pubmed-stream download "query" --workers 10  # 10 parallel downloads
```

**Sequential**: More reliable for unstable networks
```bash
pubmed-stream download "query" --sequential
```

### Optimal Settings by Network

| Network Quality | Mode | Workers | Rate Limit |
|----------------|------|---------|------------|
| Excellent | Concurrent | 10 | 0.1 (with API key) |
| Good | Concurrent | 5 | 0.1 |
| Fair | Concurrent | 2-3 | 0.2 |
| Poor | Sequential | 1 | 0.34 |

### Performance Benchmarks

Typical download speeds (with API key, 5 workers):
- **Small articles** (~50KB): 2-5 articles/second
- **Medium articles** (~200KB): 1-3 articles/second
- **Large articles** (~1MB): 0.5-1 articles/second

Example: 100 medium-sized articles ≈ 45-60 seconds

Note: The raw XML is not included in JSON format to save storage. Use `--format xml` if you need the raw XML.

## Testing

The repository includes a comprehensive Jupyter notebook for testing all features:

```bash
# Install Jupyter
pip install jupyter

# Launch test notebook
jupyter notebook test_download.ipynb
```

The notebook demonstrates:
- Basic and advanced download scenarios
- All format options (text, xml, both)
- Concurrent vs sequential modes
- Error handling and edge cases
- Performance comparisons
- Low-level API usage

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests (if available)
pytest tests/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with clear commit messages
4. Add tests if applicable
5. Ensure code passes linting: `ruff check .`
6. Submit a pull request

### Code Style

- Follow PEP 8
- Use type hints where appropriate
- Add docstrings for public functions
- Keep functions focused and modular

## Development Roadmap

Future enhancements being considered:
- [ ] Support for PubMed (non-PMC) abstracts
- [ ] Advanced search query builder
- [ ] Automatic deduplication
- [ ] Progress bars for CLI
- [ ] Export to BibTeX/RIS formats
- [ ] Integration with citation managers
- [ ] Parallel processing for metadata extraction

## FAQ

**Q: Why JSON instead of separate XML/TXT files?**  
A: Unified JSON format provides consistent structure, always includes metadata, and simplifies file operations. You can still get raw XML (as a string field) if needed.

**Q: Can I use this for commercial purposes?**  
A: Yes, under the MIT license. However, respect NCBI's usage policies and rate limits.

**Q: How do I get an NCBI API key?**  
A: Register at https://www.ncbi.nlm.nih.gov/account/ and generate an API key in your account settings. It's free.

**Q: Does this violate NCBI terms of service?**  
A: No - this library is built on official NCBI E-utilities APIs (ESearch and EFetch), respects rate limits, and includes proper user-agent headers in compliance with NCBI usage policies.

**Q: Can I resume interrupted downloads?**  
A: Yes - already-downloaded files are automatically skipped (shown in `stats.skipped`).

**Q: What's the difference between PMC and PubMed?**  
A: PubMed contains citation abstracts for millions of papers. PMC (PubMed Central) is a subset with full-text articles. This library accesses PMC for complete article text.

## Project Structure

```
pubmed-stream/
├── pubmed_stream/              # Main package
│   ├── __init__.py            # Public API exports
│   ├── __main__.py            # python -m pubmed_stream entry point
│   ├── cli.py                 # Command-line interface
│   ├── downloader.py          # Core download logic
│   └── py.typed               # Type hint marker
├── examples/
│   ├── keywords/              # Sample keyword CSV files
│   │   ├── pmc_literature_keywords.csv
│   │   └── ...
│   └── utils/                 # Helper scripts
│       ├── manage_text_field.py
│       └── test_pmc_availability.py
├── test_download.ipynb        # Comprehensive test notebook
├── pyproject.toml            # Project metadata and dependencies
├── README.md                 # This file
└── .gitignore               # Git ignore rules
```

## Acknowledgments

This library was developed to support biomedical research at the **University of Massachusetts** by:
- **Haran Lab**
- **Bucci Lab**
- **Microbiology & Microbiome Dynamics AI HUB**

Special thanks to:
- **NCBI** for providing the E-utilities API and open access to PubMed Central
- The open-source community for Python ecosystem tools

## Citation

If you use this library in your research, please cite:

```bibtex
@software{pubmed_stream_2026,
  title = {pubmed-stream: Python Library for PMC Article Downloads via NCBI E-utilities},
  author = {Haran Lab and Bucci Lab and Microbiology \& Microbiome Dynamics AI HUB},
  organization = {University of Massachusetts},
  year = {2026},
  url = {https://github.com/melhzy/pubmed-stream},
  note = {Built on NCBI E-utilities API}
}
```

## License

MIT License

Copyright (c) 2026 University of Massachusetts  
Haran Lab, Bucci Lab, and Microbiology & Microbiome Dynamics AI HUB

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

**Contact**: For questions or support, please open an issue on GitHub.

**Repository**: https://github.com/melhzy/pubmed-stream
