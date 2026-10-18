"""pubmed-stream – Download PubMed Central full-text articles."""

__version__ = "0.2.0"

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
from .kg import KGResult, create_kg, load_study, record_study
from .vault import VaultStats, build_vault, topic_vault_dir

__all__ = [
    "DownloadStats",
    "KGResult",
    "Neighborhood",
    "RateLimiter",
    "RelatedArticle",
    "VaultStats",
    "create_kg",
    "create_session",
    "download_neighborhood",
    "build_vault",
    "efetch_pmc",
    "esearch_pmc",
    "extract_metadata_from_pmc_xml",
    "extract_text_from_pmc_xml",
    "get_neighborhood",
    "linked_discoveries_url",
    "load_study",
    "record_study",
    "save_neighborhood",
    "search_and_download",
    "strip_xml_tags",
    "topic_vault_dir",
]
