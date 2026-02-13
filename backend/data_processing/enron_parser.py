"""
Enron Email Dataset Parser and Unclustering Module
Parses Enron maildir format and converts to JSONL with metadata
"""

import os
import json
import email
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
from tqdm import tqdm


class EnronParser:
    """Parse Enron email dataset and convert to structured JSONL format"""

    def __init__(self, maildir_path: str):
        self.maildir_path = Path(maildir_path)
        self.parsed_emails = []

    def parse_email_file(self, file_path: Path) -> Optional[Dict]:
        """
        Parse a single email file and extract metadata and content

        Args:
            file_path: Path to email file

        Returns:
            Dictionary with email metadata and content, or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                msg = email.message_from_file(f)

            # Extract metadata
            from_addr = msg.get('From', '')
            to_addr = msg.get('To', '')
            subject = msg.get('Subject', '')
            date_str = msg.get('Date', '')

            # Parse date
            try:
                date_obj = parsedate_to_datetime(date_str) if date_str else None
                timestamp = date_obj.isoformat() if date_obj else None
            except:
                timestamp = None

            # Extract body content
            body = self._extract_body(msg)

            # Extract employee name from path
            employee_name = self._extract_employee_from_path(file_path)

            # Extract folder/category from path
            folder_category = self._extract_folder_from_path(file_path)

            # Create document
            document = {
                'doc_id': self._generate_doc_id(file_path),
                'content': body,
                'metadata': {
                    'author': from_addr,
                    'employee': employee_name,
                    'to': to_addr,
                    'subject': subject,
                    'timestamp': timestamp,
                    'date_str': date_str,
                    'folder': folder_category,
                    'source_type': 'email',
                    'source_path': str(file_path),
                },
                'source_hyperlink': f'file://{file_path}',
            }

            return document

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def _extract_body(self, msg) -> str:
        """Extract body content from email message"""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        continue
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(msg.get_payload())

        # Clean up body
        body = self._clean_text(body)
        return body

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = text.strip()
        return text

    def _extract_employee_from_path(self, file_path: Path) -> str:
        """Extract employee name from file path structure"""
        # Enron structure: maildir/employee-name/folder/...
        parts = file_path.parts
        maildir_idx = parts.index('maildir') if 'maildir' in parts else -1
        if maildir_idx >= 0 and maildir_idx + 1 < len(parts):
            return parts[maildir_idx + 1]
        return 'unknown'

    def _extract_folder_from_path(self, file_path: Path) -> str:
        """Extract folder category from file path"""
        parts = file_path.parts
        maildir_idx = parts.index('maildir') if 'maildir' in parts else -1
        if maildir_idx >= 0 and maildir_idx + 2 < len(parts):
            # Return the folder name (e.g., 'sent', 'inbox', etc.)
            return parts[maildir_idx + 2]
        return 'unknown'

    def _generate_doc_id(self, file_path: Path) -> str:
        """Generate unique document ID from file path"""
        # Use relative path from maildir as ID
        try:
            relative = file_path.relative_to(self.maildir_path)
            return str(relative).replace('/', '_').replace('\\', '_')
        except:
            return str(hash(str(file_path)))

    def parse_all_emails(self, output_path: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Parse all emails in the maildir and optionally save to JSONL

        Args:
            output_path: Path to save JSONL output (optional)
            limit: Maximum number of emails to parse (optional, for testing)

        Returns:
            List of parsed email documents
        """
        print(f"Scanning {self.maildir_path} for emails...")

        # Find all email files
        email_files = []
        for root, dirs, files in os.walk(self.maildir_path):
            for file in files:
                # Skip hidden files and directories
                if file.startswith('.'):
                    continue
                file_path = Path(root) / file
                # Simple heuristic: email files typically don't have extensions
                if '.' not in file or file.endswith('.'):
                    email_files.append(file_path)

        if limit:
            email_files = email_files[:limit]

        print(f"Found {len(email_files)} email files. Parsing...")

        # Parse emails with progress bar
        self.parsed_emails = []
        for file_path in tqdm(email_files, desc="Parsing emails"):
            doc = self.parse_email_file(file_path)
            if doc and doc['content']:  # Only include emails with content
                self.parsed_emails.append(doc)

        print(f"Successfully parsed {len(self.parsed_emails)} emails")

        # Save to JSONL if output path provided
        if output_path:
            self.save_to_jsonl(output_path)

        return self.parsed_emails

    def save_to_jsonl(self, output_path: str):
        """Save parsed emails to JSONL format"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            for doc in self.parsed_emails:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        print(f"✓ Saved {len(self.parsed_emails)} emails to {output_path}")

    def get_statistics(self) -> Dict:
        """Get statistics about parsed emails"""
        if not self.parsed_emails:
            return {}

        employees = set(doc['metadata']['employee'] for doc in self.parsed_emails)
        folders = set(doc['metadata']['folder'] for doc in self.parsed_emails)

        # Count emails per employee
        employee_counts = {}
        for doc in self.parsed_emails:
            emp = doc['metadata']['employee']
            employee_counts[emp] = employee_counts.get(emp, 0) + 1

        return {
            'total_emails': len(self.parsed_emails),
            'unique_employees': len(employees),
            'unique_folders': len(folders),
            'employees': sorted(employees),
            'folders': sorted(folders),
            'emails_per_employee': employee_counts,
        }


def uncluster_enron_data(maildir_path: str, output_path: str, limit: Optional[int] = None):
    """
    Main function to uncluster Enron data

    Args:
        maildir_path: Path to Enron maildir
        output_path: Path to save unclustered JSONL
        limit: Optional limit for testing
    """
    parser = EnronParser(maildir_path)
    emails = parser.parse_all_emails(output_path, limit=limit)

    # Print statistics
    stats = parser.get_statistics()
    print("\n" + "="*50)
    print("ENRON DATASET STATISTICS")
    print("="*50)
    print(f"Total emails parsed: {stats['total_emails']}")
    print(f"Unique employees: {stats['unique_employees']}")
    print(f"Unique folders: {stats['unique_folders']}")
    print(f"\nTop 10 employees by email count:")
    sorted_employees = sorted(stats['emails_per_employee'].items(), key=lambda x: x[1], reverse=True)[:10]
    for emp, count in sorted_employees:
        print(f"  {emp}: {count} emails")

    return emails


if __name__ == "__main__":
    # Test the parser
    from config.config import Config

    output_path = Config.DATA_DIR / "unclustered" / "enron_emails.jsonl"
    uncluster_enron_data(
        maildir_path=Config.ENRON_MAILDIR,
        output_path=str(output_path),
        limit=1000  # Test with 1000 emails first
    )
