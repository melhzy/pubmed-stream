"""pubmed-stream: literature searches in PubMed and PubMed Central, for researchers and their AI assistants."""

__version__ = "0.4.4"

from .downloader import (
    DownloadStats,
    RateLimiter,
    SearchResult,
    create_session,
    efetch_pmc,
    esearch_pmc,
    esummary_pmc,
    extract_metadata_from_pmc_xml,
    extract_text_from_pmc_xml,
    linked_discoveries_url,
    search_and_download,
    search_pmc,
    strip_xml_tags,
)
from .corpus import list_articles, most_cited
from .abstracts import AbstractStats, count_pubmed, fetch_abstracts
from .export import export_citations, to_bibtex, to_ris
from .review import AssistantError, ModelError, OllamaError, Review, ask_assistant, review
from .assistants import init_folder
from .obsidian import open_vault
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
    "AbstractStats",
    "AssistantError",
    "DownloadStats",
    "KGResult",
    "ModelError",
    "Neighborhood",
    "OllamaError",
    "RateLimiter",
    "RelatedArticle",
    "Review",
    "SearchResult",
    "VaultStats",
    "ask_assistant",
    "build_vault",
    "count_pubmed",
    "create_kg",
    "create_session",
    "download_neighborhood",
    "efetch_pmc",
    "esearch_pmc",
    "esummary_pmc",
    "export_citations",
    "extract_metadata_from_pmc_xml",
    "extract_text_from_pmc_xml",
    "fetch_abstracts",
    "get_neighborhood",
    "init_folder",
    "linked_discoveries_url",
    "list_articles",
    "load_study",
    "most_cited",
    "open_vault",
    "record_study",
    "review",
    "save_neighborhood",
    "search_and_download",
    "search_pmc",
    "strip_xml_tags",
    "to_bibtex",
    "to_ris",
    "topic_vault_dir",
]
