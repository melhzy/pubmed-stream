"""pubmed-stream – Download PubMed Central full-text articles."""

__version__ = "0.1.0"

from .downloader import (
    DownloadStats,
    RateLimiter,
    create_session,
    efetch_pmc,
    esearch_pmc,
    extract_metadata_from_pmc_xml,
    extract_text_from_pmc_xml,
    linked_discoveries_url,
    search_and_download,
    strip_xml_tags,
)
from .neighborhood import (
    Neighborhood,
    RelatedArticle,
    download_neighborhood,
    get_neighborhood,
    save_neighborhood,
)

__all__ = [
    "DownloadStats",
    "Neighborhood",
    "RateLimiter",
    "RelatedArticle",
    "create_session",
    "download_neighborhood",
    "efetch_pmc",
    "esearch_pmc",
    "extract_metadata_from_pmc_xml",
    "extract_text_from_pmc_xml",
    "get_neighborhood",
    "linked_discoveries_url",
    "save_neighborhood",
    "search_and_download",
    "strip_xml_tags",
]
