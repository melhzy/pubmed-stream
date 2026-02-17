"""Quick utility to test PMC article availability for different keywords.

This helps identify search terms that return actual downloadable full-text
articles vs metadata-only results.

Usage:
    python scripts/utils/test_pmc_availability.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "scripts" / "utils"))

from literature_downloader import esearch_pmc, efetch_pmc, NCBI_API_KEY, PUBLICATIONS_DIR
import time

# Test keywords relevant to frailty research
TEST_KEYWORDS = [
    "frailty cytokines",
    "frailty inflammation aging",
    "frailty biomarkers elderly",
    "sarcopenia cytokines",
    "inflammaging frailty",
    "interleukin frailty",
    "TNF alpha frailty",
    "IL-6 frailty elderly",
]


def test_keyword_availability(keyword: str, sample_size: int = 5) -> dict:
    """Test if a keyword returns downloadable articles."""
    print(f"\n{'='*70}")
    print(f"Testing: {keyword}")
    print(f"{'='*70}")
    
    try:
        pmcids, total = esearch_pmc(keyword, max_results=sample_size, api_key=NCBI_API_KEY)
        
        if not pmcids:
            print(f"❌ No results found")
            return {"keyword": keyword, "total_available": 0, "tested": 0, "downloadable": 0}
        
        print(f"Found {len(pmcids)} IDs to test (total available: {total})")
        
        # Test each ID
        downloadable = 0
        unavailable = 0
        errors = 0
        
        temp_dir = PUBLICATIONS_DIR / "_test_temp"
        
        for i, pmcid in enumerate(pmcids, 1):
            success, status = efetch_pmc(pmcid, temp_dir, fmt="json", api_key=NCBI_API_KEY)
            
            if status == "success":
                downloadable += 1
                print(f"  ✓ PMC{pmcid}: Available")
            elif status == "unavailable":
                unavailable += 1
                print(f"  ✗ PMC{pmcid}: Not available in full-text")
            else:
                errors += 1
                print(f"  ⚠ PMC{pmcid}: Error")
            
            time.sleep(0.34)
        
        # Clean up temp files
        if temp_dir.exists():
            for f in temp_dir.glob("*.json"):
                f.unlink()
            temp_dir.rmdir()
        
        availability_rate = (downloadable / len(pmcids)) * 100 if pmcids else 0
        print(f"\nAvailability: {downloadable}/{len(pmcids)} ({availability_rate:.0f}%)")
        
        if availability_rate >= 50:
            print(f"✅ GOOD - {keyword} has {availability_rate:.0f}% availability")
        elif availability_rate > 0:
            print(f"⚠️  MIXED - {keyword} has only {availability_rate:.0f}% availability")
        else:
            print(f"❌ POOR - {keyword} has no downloadable full-text articles")
        
        return {
            "keyword": keyword,
            "total_available": total,
            "tested": len(pmcids),
            "downloadable": downloadable,
            "unavailable": unavailable,
            "errors": errors,
            "availability_rate": availability_rate
        }
        
    except Exception as e:
        print(f"❌ Error testing keyword: {e}")
        return {"keyword": keyword, "total_available": 0, "tested": 0, "downloadable": 0, "error": str(e)}


def main():
    """Test all keywords and summarize results."""
    print("\n" + "="*70)
    print("PMC Article Availability Test")
    print("Testing keywords to find those with downloadable full-text articles")
    print("="*70)
    
    results = []
    for keyword in TEST_KEYWORDS:
        result = test_keyword_availability(keyword, sample_size=5)
        results.append(result)
        time.sleep(1)  # Pause between keywords
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY - Best Keywords for Download")
    print("="*70)
    
    # Sort by availability rate
    results_sorted = sorted(results, key=lambda x: x.get("availability_rate", 0), reverse=True)
    
    print(f"\n{'Keyword':<35} {'Total':<8} {'Tested':<8} {'Available':<10} {'Rate':<8}")
    print("-" * 70)
    
    for r in results_sorted:
        keyword = r["keyword"]
        total = r.get("total_available", 0)
        tested = r.get("tested", 0)
        available = r.get("downloadable", 0)
        rate = r.get("availability_rate", 0)
        
        status = "✅" if rate >= 50 else "⚠️" if rate > 0 else "❌"
        print(f"{status} {keyword:<33} {total:<8} {tested:<8} {available:<10} {rate:>6.0f}%")
    
    # Recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    good_keywords = [r["keyword"] for r in results_sorted if r.get("availability_rate", 0) >= 50]
    
    if good_keywords:
        print("\n✅ Use these keywords for successful downloads:")
        for kw in good_keywords:
            print(f"   • {kw}")
        print(f"\nExample command:")
        print(f'   python -m pubmed_stream.cli download "{good_keywords[0]}" --max-results 50')
    else:
        print("\n❌ None of the tested keywords have good availability.")
        print("   This may indicate:")
        print("   • Recent articles not yet in PMC full-text collection")
        print("   • Need to broaden search terms")
        print("   • Try searching PubMed instead of PMC for abstracts")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)  # Suppress INFO logs for cleaner output
    main()
