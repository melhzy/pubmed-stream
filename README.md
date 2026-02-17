# pubmed-stream

Download PubMed Central (PMC) full-text articles from the command line or
Python code. Handles search, PMC ID resolution, concurrent downloads, retries,
and metadata extraction out of the box.

## Installation

```bash
pip install .            # from a local clone
# or, in development mode:
pip install -e ".[dev]"
```

The only runtime dependency is [requests](https://pypi.org/project/requests/).

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
| `--format` | Output format: `json`, `xml`, `txt` | `json` |
| `--output-dir`, `-o` | Base output directory | `./publications` |
| `--api-key` | NCBI API key | `NCBI_API_KEY` env var |
| `--email` | Contact email for NCBI | `NCBI_EMAIL` env var |
| `--sequential` | Disable concurrent downloads | concurrent |
| `--workers` | Concurrent thread count | 5 |
| `--exclude-text` | Omit `text` field in JSON (~30 % smaller) | included |
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

```python
from pubmed_stream import search_and_download

stats = search_and_download(
    keyword="frailty cytokines",
    max_results=50,
    fmt="json",
    output_dir="publications",
)

print(f"Downloaded {stats.successful}, skipped {stats.skipped}, "
      f"failed {stats.failed} in {stats.duration_seconds:.1f}s")
```

Lower-level helpers are also exported:

```python
from pubmed_stream import esearch_pmc, efetch_pmc, extract_metadata_from_pmc_xml
```

## Output format

Articles land in `<output_dir>/<keyword_slug>/`:

```
publications/
  frailty_cytokines/
    PMC12345678.json
    PMC12345679.json
```

Each JSON file contains:

```json
{
  "pmcid": "PMC12345678",
  "source": "PMC",
  "download_date": "2025-12-07T11:30:45",
  "metadata": {
    "title": "Article Title",
    "journal": "Journal Name",
    "doi": "10.1234/example",
    "year": "2024",
    "authors": ["Smith J", "Doe A"],
    "abstract": "...",
    "keywords": ["frailty", "cytokines"]
  },
  "text": "Plain-text version (optional)"
}
```

Note: The raw XML is not included in JSON format to save storage. Use `--format xml` if you need the raw XML.

## Project layout

```
pubmed_stream/        # installable package
  __init__.py
  __main__.py         # python -m pubmed_stream
  cli.py              # argument parsing + entry point
  downloader.py       # search, fetch, metadata extraction
examples/
  keywords/           # sample keyword CSV files
  utils/              # helper scripts (manage_text_field, test_pmc_availability)
pyproject.toml
README.md
```

## License

MIT
