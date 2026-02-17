"""pubmed-stream – Download PubMed Central full-text articles."""

__version__ = "0.1.0"

from .downloader import (
    DownloadStats,
    RateLimiter,
    create_session,
    efetch_pmc,
    esearch_pmc,
    extract_metadata_from_pmc_xml,
    search_and_download,
    strip_xml_tags,
)

__all__ = [
    "DownloadStats",
    "RateLimiter",
    "create_session",
    "efetch_pmc",
    "esearch_pmc",
    "extract_metadata_from_pmc_xml",
    "search_and_download",
    "strip_xml_tags",
]
