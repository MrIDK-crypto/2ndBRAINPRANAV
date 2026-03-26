#!/usr/bin/env python3
"""
Slack Inventory Message Parser

Parses Slack JSON files from the inventory channel and extracts inventory items
with their quantities and status updates. Tracks changes over time and outputs
the most recent state of each item to a CSV file.

Usage:
    python parse_inventory_slack.py /path/to/inventory/folder output.csv
"""

import json
import os
import re
import csv
import sys
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


# Patterns to match quantities
QUANTITY_PATTERNS = [
    # "3 x UHP N2" or "3x UHP N2"
    (r'^(\d+)\s*x\s+(.+)$', lambda m: (int(m.group(1)), m.group(2).strip())),
    # "Half box of X"
    (r'^half\s+box\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (0.5, m.group(1).strip())),
    # "One box of X" / "1 box of X"
    (r'^one\s+box\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (1, m.group(1).strip())),
    (r'^(\d+)\s+box(?:es)?\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (int(m.group(1)), m.group(2).strip())),
    # "Two boxes of X" / "Three boxes of X"
    (r'^two\s+box(?:es)?\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (2, m.group(1).strip())),
    (r'^three\s+box(?:es)?\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (3, m.group(1).strip())),
    (r'^four\s+box(?:es)?\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (4, m.group(1).strip())),
    (r'^five\s+box(?:es)?\s+(?:of\s+)?(.+?)(?:\s+left)?$', lambda m: (5, m.group(1).strip())),
    # "X left" pattern
    (r'^(.+?)\s+left$', lambda m: (None, m.group(1).strip())),
]

# Status patterns
STATUS_PATTERNS = [
    (r'ran\s+out', 'out_of_stock'),
    (r'running\s+low', 'low_stock'),
    (r'empty', 'out_of_stock'),
    (r'finished', 'out_of_stock'),
    (r'swapped', 'replaced'),
    (r'ordered', 'ordered'),
    (r'received', 'in_stock'),
    (r'arrived', 'in_stock'),
    (r'restocked', 'in_stock'),
]

# Messages to skip (system messages, join messages, etc.)
SKIP_SUBTYPES = {'channel_join', 'channel_purpose', 'channel_topic', 'bot_message'}


def clean_slack_formatting(text: str) -> str:
    """Remove Slack-specific formatting from text."""
    # Remove user mentions <@U...>
    text = re.sub(r'<@U[A-Z0-9]+(?:\|[^>]+)?>', '', text)
    # Remove channel mentions <#C...>
    text = re.sub(r'<#C[A-Z0-9]+(?:\|[^>]+)?>', '', text)
    # Extract text from links <url|text> -> text, or just remove <url>
    text = re.sub(r'<https?://[^|>]+\|([^>]+)>', r'\1', text)
    text = re.sub(r'<https?://[^>]+>', '', text)
    # Remove file upload mentions
    text = re.sub(r'uploaded a file:.*?and commented:', '', text)
    text = re.sub(r'uploaded a file:.*$', '', text)
    # Remove asterisks (bold)
    text = re.sub(r'\*+', '', text)
    # Clean up whitespace
    text = ' '.join(text.split())
    return text.strip()


def normalize_item_name(name: str) -> str:
    """Normalize item name for deduplication."""
    # First clean Slack formatting
    name = clean_slack_formatting(name)
    # Remove extra whitespace
    name = ' '.join(name.split())
    # Convert to lowercase for comparison
    name_lower = name.lower()
    # Remove common suffixes
    name_lower = re.sub(r'\s+left$', '', name_lower)
    name_lower = re.sub(r'\s+\(.*\)$', '', name_lower)
    return name_lower


def extract_item_info(text: str) -> Optional[Dict]:
    """Extract item name, quantity, and status from message text."""
    original_text = text.strip()
    if not original_text:
        return None

    # Clean Slack formatting first
    text = clean_slack_formatting(original_text)

    # Skip very short messages after cleaning
    if len(text) < 3:
        return None

    # Skip messages that are mostly just file uploads
    if 'uploaded a file' in original_text.lower() and len(text) < 5:
        return None

    # Skip messages that are primarily URLs
    if original_text.startswith('<http') and len(text) < 10:
        return None

    # Skip messages that look like conversations
    conversation_indicators = [
        'thanks', 'thank you', 'ok', 'okay', 'yes', 'no', 'sure', 'great',
        'will do', 'got it', 'please', 'can you', 'could you', 'james,',
        'we have', 'i have', 'i will', 'i\'ll', 'we\'ll', 'let me',
        'sounds good', 'perfect', 'done', 'ordered it', 'on my bench',
        'this month', 'this week', 'tomorrow', 'today', 'did we order',
        'have you ordered', 'can we order', 'wondering if', 'want to confirm',
        'any updates', 'have been ordered', 'inquire about'
    ]
    text_lower = text.lower()
    if any(indicator in text_lower for indicator in conversation_indicators):
        # Check if it still contains useful info
        if not any(re.search(pattern[0], text_lower) for pattern in STATUS_PATTERNS):
            return None

    result = {
        'name': text,
        'quantity': None,
        'unit': None,
        'status': 'mentioned',  # Default status
        'original_text': original_text
    }

    # Check for status patterns
    for pattern, status in STATUS_PATTERNS:
        if re.search(pattern, text_lower):
            result['status'] = status
            break

    # Try to extract quantity
    for pattern, extractor in QUANTITY_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            qty, name = extractor(match)
            result['quantity'] = qty
            result['name'] = name
            if 'box' in text_lower:
                result['unit'] = 'boxes'
            break

    # Clean up the item name
    result['name'] = clean_slack_formatting(result['name']).strip()
    result['name_normalized'] = normalize_item_name(result['name'])

    # Final validation - skip if name is too short or mostly punctuation
    if len(result['name']) < 3:
        return None
    if len(re.sub(r'[^a-zA-Z0-9]', '', result['name'])) < 2:
        return None

    return result


def parse_slack_file(filepath: str) -> List[Dict]:
    """Parse a single Slack JSON file and extract messages."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading {filepath}: {e}")
        return []

    messages = []
    for msg in data:
        # Skip non-message types
        if msg.get('type') != 'message':
            continue

        # Skip system messages
        if msg.get('subtype') in SKIP_SUBTYPES:
            continue

        text = msg.get('text', '').strip()
        if not text:
            continue

        # Get timestamp and user info
        ts = msg.get('ts', '0')
        user_profile = msg.get('user_profile', {})
        user_name = user_profile.get('real_name', user_profile.get('display_name', 'Unknown'))

        messages.append({
            'text': text,
            'timestamp': float(ts),
            'user': user_name,
            'user_id': msg.get('user', '')
        })

    return messages


def parse_all_files(folder_path: str) -> List[Dict]:
    """Parse all JSON files in folder chronologically."""
    all_messages = []

    # Get all JSON files
    files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    # Sort by date in filename
    files.sort()

    print(f"Found {len(files)} JSON files to process...")

    for i, filename in enumerate(files):
        filepath = os.path.join(folder_path, filename)
        messages = parse_slack_file(filepath)

        # Add date from filename
        date_str = filename.replace('.json', '')
        for msg in messages:
            msg['date'] = date_str

        all_messages.extend(messages)

        if (i + 1) % 200 == 0:
            print(f"Processed {i + 1}/{len(files)} files...")

    # Sort all messages by timestamp
    all_messages.sort(key=lambda x: x['timestamp'])

    print(f"Total messages: {len(all_messages)}")
    return all_messages


def build_inventory_state(messages: List[Dict]) -> Dict[str, Dict]:
    """
    Build inventory state by processing messages chronologically.
    Returns the most recent state of each item.
    """
    # Track items by normalized name
    inventory = {}
    # Track history for each item
    history = defaultdict(list)

    for msg in messages:
        item_info = extract_item_info(msg['text'])
        if not item_info:
            continue

        norm_name = item_info['name_normalized']

        # Create history entry
        history_entry = {
            'date': msg['date'],
            'timestamp': msg['timestamp'],
            'user': msg['user'],
            'text': msg['text'],
            'quantity': item_info['quantity'],
            'status': item_info['status']
        }
        history[norm_name].append(history_entry)

        # Update current state (last message wins)
        if norm_name not in inventory:
            inventory[norm_name] = {
                'name': item_info['name'],
                'name_normalized': norm_name,
                'quantity': item_info['quantity'],
                'unit': item_info['unit'],
                'status': item_info['status'],
                'last_updated': msg['date'],
                'last_updated_by': msg['user'],
                'mention_count': 1,
                'history': []
            }
        else:
            # Update with newer info
            inventory[norm_name]['quantity'] = item_info['quantity'] or inventory[norm_name]['quantity']
            inventory[norm_name]['unit'] = item_info['unit'] or inventory[norm_name]['unit']
            inventory[norm_name]['status'] = item_info['status']
            inventory[norm_name]['last_updated'] = msg['date']
            inventory[norm_name]['last_updated_by'] = msg['user']
            inventory[norm_name]['mention_count'] += 1

    # Attach history to each item
    for norm_name, item in inventory.items():
        item['history'] = history[norm_name]

    return inventory


def categorize_item(name: str) -> str:
    """Categorize item based on keywords."""
    name_lower = name.lower()

    categories = {
        'Gases': ['nitrogen', 'n2', 'helium', 'argon', 'co2', 'oxygen', 'gas'],
        'Plasticware': ['plate', 'dish', 'tube', 'flask', 'pipette', 'tip', 'eppendorf', 'falcon', 'well'],
        'Reagents': ['dmso', 'buffer', 'medium', 'media', 'fbs', 'serum', 'pbs', 'tris'],
        'Antibodies': ['antibody', 'anti-', 'ab ', 'igg', 'igm'],
        'Enzymes': ['enzyme', 'ase', 'polymerase', 'ligase', 'kinase'],
        'Chemicals': ['acid', 'base', 'salt', 'solution', 'reagent'],
        'Lab Supplies': ['glove', 'paper', 'towel', 'foil', 'tape', 'marker'],
        'Equipment': ['tank', 'pump', 'machine', 'equipment', 'meter'],
    }

    for category, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return category

    return 'General Lab Supplies'


def export_to_csv(inventory: Dict[str, Dict], output_path: str, include_history: bool = False):
    """Export inventory to CSV file."""

    # CSV headers matching the import format
    headers = [
        'Name',
        'Quantity',
        'Unit',
        'Category',
        'Status',
        'Last Updated',
        'Last Updated By',
        'Mention Count',
        'Notes'
    ]

    if include_history:
        headers.append('History')

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        # Sort items by category then name
        items = sorted(inventory.values(), key=lambda x: (categorize_item(x['name']), x['name']))

        for item in items:
            row = [
                item['name'],
                item['quantity'] if item['quantity'] is not None else '',
                item['unit'] if item['unit'] else '',
                categorize_item(item['name']),
                item['status'],
                item['last_updated'],
                item['last_updated_by'],
                item['mention_count'],
                f"Last message: {item['history'][-1]['text']}" if item['history'] else ''
            ]

            if include_history:
                # Format history as a summary
                history_summary = '; '.join([
                    f"{h['date']}: {h['text'][:50]}..." if len(h['text']) > 50 else f"{h['date']}: {h['text']}"
                    for h in item['history'][-5:]  # Last 5 entries
                ])
                row.append(history_summary)

            writer.writerow(row)

    print(f"Exported {len(inventory)} items to {output_path}")


def export_import_ready_csv(inventory: Dict[str, Dict], output_path: str):
    """Export CSV optimized for 2nd Brain inventory import."""
    import_path = output_path.replace('.csv', '_import_ready.csv')

    # Headers that match the import endpoint's column mapping
    headers = [
        'Name',           # Required
        'Quantity',       # Maps to quantity
        'Unit',           # Maps to unit
        'Category',       # Auto-creates categories
        'Notes'           # Maps to notes/description
    ]

    with open(import_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        # Sort items by category then name
        items = sorted(inventory.values(), key=lambda x: (categorize_item(x['name']), x['name']))

        for item in items:
            # Build notes with context
            notes_parts = []
            if item['status'] != 'mentioned':
                notes_parts.append(f"Status: {item['status']}")
            notes_parts.append(f"Last updated: {item['last_updated']} by {item['last_updated_by']}")
            if item['history']:
                notes_parts.append(f"Latest: {item['history'][-1]['text'][:100]}")

            row = [
                item['name'],
                int(item['quantity']) if item['quantity'] is not None else 0,
                item['unit'] if item['unit'] else 'units',
                categorize_item(item['name']),
                ' | '.join(notes_parts)
            ]
            writer.writerow(row)

    print(f"Exported import-ready CSV ({len(inventory)} items) to {import_path}")
    return import_path


def export_full_history(inventory: Dict[str, Dict], output_path: str):
    """Export full history of all inventory changes to a separate CSV."""
    history_path = output_path.replace('.csv', '_history.csv')

    headers = ['Item Name', 'Date', 'User', 'Message', 'Quantity Mentioned', 'Status']

    all_history = []
    for item in inventory.values():
        for h in item['history']:
            all_history.append({
                'item_name': item['name'],
                'date': h['date'],
                'user': h['user'],
                'message': h['text'],
                'quantity': h['quantity'],
                'status': h['status']
            })

    # Sort by date
    all_history.sort(key=lambda x: x['date'])

    with open(history_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for entry in all_history:
            writer.writerow([
                entry['item_name'],
                entry['date'],
                entry['user'],
                entry['message'],
                entry['quantity'] if entry['quantity'] is not None else '',
                entry['status']
            ])

    print(f"Exported full history ({len(all_history)} entries) to {history_path}")


def main():
    # Default paths
    if len(sys.argv) >= 3:
        input_folder = sys.argv[1]
        output_csv = sys.argv[2]
    else:
        input_folder = '/Users/badri/Desktop/Desktop/Badri/Research/inventory'
        output_csv = '/Users/badri/Desktop/Desktop/Badri/Research/inventory_current_state.csv'

    print(f"Input folder: {input_folder}")
    print(f"Output CSV: {output_csv}")
    print("-" * 50)

    # Parse all messages
    messages = parse_all_files(input_folder)

    # Build inventory state
    print("\nBuilding inventory state from messages...")
    inventory = build_inventory_state(messages)

    print(f"Found {len(inventory)} unique inventory items")

    # Export to CSV
    print("\nExporting to CSV...")
    export_to_csv(inventory, output_csv, include_history=True)

    # Export full history
    export_full_history(inventory, output_csv)

    # Export import-ready CSV (optimized for 2nd Brain import)
    import_ready_path = export_import_ready_csv(inventory, output_csv)

    # Print summary by category
    print("\n" + "=" * 50)
    print("INVENTORY SUMMARY BY CATEGORY")
    print("=" * 50)

    by_category = defaultdict(list)
    for item in inventory.values():
        cat = categorize_item(item['name'])
        by_category[cat].append(item)

    for category in sorted(by_category.keys()):
        items = by_category[category]
        print(f"\n{category} ({len(items)} items):")
        for item in sorted(items, key=lambda x: x['name'])[:5]:
            qty_str = f" [{item['quantity']}]" if item['quantity'] else ""
            status_str = f" - {item['status']}" if item['status'] != 'mentioned' else ""
            print(f"  - {item['name']}{qty_str}{status_str}")
        if len(items) > 5:
            print(f"  ... and {len(items) - 5} more")

    print("\n" + "=" * 50)
    print("Done!")


if __name__ == '__main__':
    main()
