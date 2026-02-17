"""Utility to add/remove text field from downloaded PMC JSON files.

Since the 'text' field is just stripped XML (redundant), the downloader
now omits it by default to save ~30% storage. This utility lets you:
1. Add text field to existing JSON files (regenerate from XML)
2. Remove text field from files to save space
3. Check which files have/don't have text field

Usage:
    # Add text field to all JSONs in a folder
    python scripts/utils/manage_text_field.py add publications/frailty_cytokines
    
    # Remove text field to save space
    python scripts/utils/manage_text_field.py remove publications/frailty_cytokines
    
    # Check status
    python scripts/utils/manage_text_field.py check publications/frailty_cytokines
"""

import sys
import json
import re
from pathlib import Path
from typing import List, Tuple


def strip_xml_tags(xml_text: str) -> str:
    """Remove XML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", xml_text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def add_text_field(json_path: Path) -> Tuple[bool, str]:
    """Add text field to a JSON file if it doesn't have one."""
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
        
        if 'text' in data and data['text']:
            return False, "already has text field"
        
        if 'xml' not in data:
            return False, "no XML field to generate from"
        
        # Generate text from XML
        data['text'] = strip_xml_tags(data['xml'])
        
        # Write back
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return True, "text field added"
        
    except Exception as e:
        return False, f"error: {e}"


def remove_text_field(json_path: Path) -> Tuple[bool, str]:
    """Remove text field from a JSON file to save space."""
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
        
        if 'text' not in data:
            return False, "no text field to remove"
        
        # Calculate space saved
        text_size = len(data['text'].encode('utf-8'))
        
        # Remove text field
        del data['text']
        
        # Write back
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return True, f"removed ({text_size/1024:.1f} KB saved)"
        
    except Exception as e:
        return False, f"error: {e}"


def check_text_field(json_path: Path) -> Tuple[bool, str]:
    """Check if a JSON file has text field."""
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
        has_text = 'text' in data and bool(data['text'])
        
        if has_text:
            text_size = len(data['text'].encode('utf-8'))
            return True, f"has text field ({text_size/1024:.1f} KB)"
        else:
            return False, "no text field"
            
    except Exception as e:
        return False, f"error: {e}"


def process_directory(directory: Path, operation: str) -> None:
    """Process all JSON files in a directory."""
    json_files = list(directory.glob("PMC*.json"))
    
    if not json_files:
        print(f"No PMC JSON files found in {directory}")
        return
    
    print(f"\nProcessing {len(json_files)} files in {directory}")
    print("=" * 70)
    
    operation_map = {
        'add': add_text_field,
        'remove': remove_text_field,
        'check': check_text_field
    }
    
    func = operation_map[operation]
    
    success_count = 0
    skip_count = 0
    error_count = 0
    total_saved = 0
    
    for json_path in sorted(json_files):
        success, message = func(json_path)
        
        status = "✓" if success else "○" if "already" in message or "no text" in message else "✗"
        print(f"{status} {json_path.name}: {message}")
        
        if success:
            success_count += 1
            if "KB saved" in message:
                # Extract saved KB from message
                kb = float(message.split("(")[1].split(" KB")[0])
                total_saved += kb
        elif "already" in message or "no text" in message:
            skip_count += 1
        else:
            error_count += 1
    
    print("\n" + "=" * 70)
    print(f"Summary:")
    print(f"  ✓ Processed: {success_count}")
    print(f"  ○ Skipped:   {skip_count}")
    if error_count > 0:
        print(f"  ✗ Errors:    {error_count}")
    if total_saved > 0:
        print(f"\nTotal space saved: {total_saved:.1f} KB ({total_saved/1024:.2f} MB)")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Manage text field in PMC JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add text field to all files (regenerate from XML)
  python scripts/utils/manage_text_field.py add publications/frailty_cytokines
  
  # Remove text field to save ~30% storage
  python scripts/utils/manage_text_field.py remove publications/frailty_cytokines
  
  # Check which files have text field
  python scripts/utils/manage_text_field.py check publications/frailty_cytokines
  
  # Process all subdirectories
  python scripts/utils/manage_text_field.py remove publications
"""
    )
    
    parser.add_argument(
        'operation',
        choices=['add', 'remove', 'check'],
        help='Operation to perform'
    )
    parser.add_argument(
        'directory',
        type=Path,
        help='Directory containing PMC JSON files'
    )
    parser.add_argument(
        '--recursive',
        '-r',
        action='store_true',
        help='Process subdirectories recursively'
    )
    
    args = parser.parse_args()
    
    if not args.directory.exists():
        print(f"Error: Directory not found: {args.directory}")
        sys.exit(1)
    
    if args.recursive:
        # Process all subdirectories with JSON files
        subdirs = [d for d in args.directory.rglob("*") if d.is_dir() and list(d.glob("PMC*.json"))]
        if not subdirs:
            print(f"No subdirectories with PMC JSON files found in {args.directory}")
            sys.exit(1)
        
        print(f"\nFound {len(subdirs)} subdirectories with PMC JSON files")
        for subdir in subdirs:
            process_directory(subdir, args.operation)
    else:
        process_directory(args.directory, args.operation)


if __name__ == "__main__":
    main()
