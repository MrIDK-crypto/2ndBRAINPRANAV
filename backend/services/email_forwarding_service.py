"""
Email Forwarding Service
Receives forwarded emails via IMAP from beatatucla@gmail.com
Parses emails and adds them as documents to the database
Also parses email attachments (PDF, DOCX, XLSX, PPTX, etc.)
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
import tempfile
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from pathlib import Path

from database.models import Document, DocumentStatus, utc_now
from parsers.document_parser import DocumentParser

# Supported attachment types for parsing
SUPPORTED_ATTACHMENT_TYPES = {
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'application/vnd.ms-powerpoint': '.ppt',
    'text/plain': '.txt',
    'text/csv': '.csv',
}


class EmailForwardingService:
    """Service to poll and process forwarded emails"""

    def __init__(self, db: Session, config=None):
        self.db = db
        self.config = config
        self.parser = DocumentParser(config=config)

        # Email credentials from environment
        self.email_address = os.getenv("FORWARD_EMAIL_ADDRESS", "beatatucla@gmail.com")
        self.email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

        if not self.email_password:
            raise ValueError("FORWARD_EMAIL_PASSWORD environment variable not set")

    @staticmethod
    def get_tenant_email(base_email: str, tenant_id: str) -> str:
        """
        Generate tenant-specific email address using Gmail plus addressing.

        Example: beatatucla@gmail.com + tenant123 -> beatatucla+tenant123@gmail.com

        This allows each tenant to have a unique forwarding address while
        all emails still arrive at the same Gmail inbox.
        """
        if not tenant_id or tenant_id == "local-tenant":
            return base_email

        # Split email into local part and domain
        if "@" not in base_email:
            return base_email

        local_part, domain = base_email.split("@", 1)

        # Sanitize tenant_id for email (only alphanumeric and hyphens)
        safe_tenant_id = "".join(c if c.isalnum() or c == "-" else "_" for c in tenant_id)

        # Use first 20 chars of tenant_id to keep email reasonable length
        safe_tenant_id = safe_tenant_id[:20]

        return f"{local_part}+{safe_tenant_id}@{domain}"

    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to Gmail IMAP server"""
        try:
            # Connect to Gmail with 30 second timeout
            import socket
            mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
            mail.login(self.email_address, self.email_password)
            print(f"✓ Connected to {self.email_address}")
            return mail
        except socket.timeout:
            raise Exception(f"Connection to Gmail IMAP timed out after 30 seconds. Please check your network connection.")
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            if "AUTHENTICATIONFAILED" in error_msg or "Invalid credentials" in error_msg.lower():
                raise Exception("Gmail authentication failed. Please check: 1) IMAP is enabled in Gmail settings, 2) App Password is correct, 3) Less secure apps may need to be enabled")
            raise Exception(f"IMAP error: {error_msg}")
        except Exception as e:
            raise Exception(f"Failed to connect to IMAP: {str(e)}")

    def fetch_new_emails(self, tenant_id: str, max_emails: int = 50) -> Dict:
        """
        Fetch new unread emails from forwarding inbox

        Args:
            tenant_id: Tenant ID to associate documents with
            max_emails: Maximum number of emails to process

        Returns:
            Dict with processed count and errors
        """
        mail = None
        try:
            mail = self.connect_imap()
            mail.select("INBOX")

            # Search for unread emails
            status, messages = mail.search(None, "UNSEEN")

            if status != "OK":
                return {"success": False, "error": "Failed to search emails"}

            email_ids = messages[0].split()
            total_emails = len(email_ids)

            if total_emails == 0:
                return {
                    "success": True,
                    "processed": 0,
                    "total": 0,
                    "message": "No new emails"
                }

            print(f"\n📧 Found {total_emails} new forwarded emails")

            # Process emails (limit to max_emails)
            processed = 0
            errors = []

            for email_id in email_ids[:max_emails]:
                try:
                    # Fetch email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")

                    if status != "OK":
                        errors.append(f"Failed to fetch email {email_id}")
                        continue

                    # Parse email
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)

                    # Extract metadata and attachments
                    doc_data, attachments = self._extract_email_data(email_message)

                    # Create document for the email body
                    email_doc = self._create_document(tenant_id, doc_data)

                    # Process attachments
                    attachment_count = 0
                    for attachment in attachments:
                        try:
                            attachment_doc = self._process_attachment(
                                tenant_id=tenant_id,
                                attachment=attachment,
                                email_subject=doc_data['subject'],
                                email_sender=doc_data['sender_email'],
                                email_timestamp=doc_data['timestamp'],
                                parent_email_id=str(email_doc.id)
                            )
                            if attachment_doc:
                                attachment_count += 1
                                print(f"    → Attachment: {attachment['filename']}")
                        except Exception as att_err:
                            print(f"    ✗ Failed to process attachment {attachment.get('filename', 'unknown')}: {att_err}")

                    processed += 1
                    print(f"  ✓ Processed: {doc_data['subject'][:50]}... ({attachment_count} attachments)")

                    # Mark as read
                    mail.store(email_id, '+FLAGS', '\\Seen')

                except Exception as e:
                    error_msg = f"Error processing email {email_id}: {str(e)}"
                    errors.append(error_msg)
                    print(f"  ✗ {error_msg}")

            return {
                "success": True,
                "processed": processed,
                "total": total_emails,
                "errors": errors
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass

    def _extract_email_data(self, email_message) -> Tuple[Dict, List[Dict]]:
        """
        Extract data from email message including attachments.

        Returns:
            Tuple of (email_data dict, list of attachment dicts)
        """

        # Subject
        subject = self._decode_header(email_message.get("Subject", "No Subject"))

        # From
        from_addr = self._decode_header(email_message.get("From", "Unknown"))

        # Date
        date_str = email_message.get("Date")
        timestamp = None
        if date_str:
            try:
                timestamp = parsedate_to_datetime(date_str)
            except:
                pass

        # Extract body and attachments
        body = self._extract_body(email_message)
        attachments = self._extract_attachments(email_message)

        # Detect original sender (from forwarded email)
        original_from = self._extract_original_sender(body, from_addr)

        # Create content with attachment info
        attachment_info = ""
        if attachments:
            attachment_names = [a['filename'] for a in attachments]
            attachment_info = f"\n\nAttachments ({len(attachments)}): {', '.join(attachment_names)}"

        content = f"""Subject: {subject}
From: {original_from}
Forwarded by: {from_addr}
Date: {date_str or 'Unknown'}

{body}{attachment_info}"""

        email_data = {
            "subject": subject,
            "sender_email": original_from,
            "forwarded_by": from_addr,
            "content": content,
            "timestamp": timestamp or utc_now(),
            "metadata": {
                "source": "email_forwarding",
                "forwarding_email": self.email_address,
                "original_date": date_str,
                "attachment_count": len(attachments),
                "attachment_names": [a['filename'] for a in attachments]
            }
        }

        return email_data, attachments

    def _decode_header(self, header_value: str) -> str:
        """Decode email header"""
        if not header_value:
            return ""

        decoded_parts = decode_header(header_value)
        header_text = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                header_text += part.decode(encoding or "utf-8", errors="ignore")
            else:
                header_text += part

        return header_text

    def _extract_body(self, email_message) -> str:
        """Extract email body (text or HTML)"""
        body = ""

        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
                    except:
                        pass

                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html = payload.decode(charset, errors='ignore')
                        # Simple HTML stripping (better to use proper parser)
                        import re
                        body = re.sub('<[^<]+?>', '', html)
                    except:
                        pass
        else:
            try:
                payload = email_message.get_payload(decode=True)
                if payload:
                    charset = email_message.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except:
                body = str(email_message.get_payload())

        return body.strip()

    def _extract_attachments(self, email_message) -> List[Dict]:
        """
        Extract attachments from email message.

        Returns:
            List of dicts with 'filename', 'content_type', 'data' (bytes)
        """
        attachments = []

        if not email_message.is_multipart():
            return attachments

        for part in email_message.walk():
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip if not an attachment
            if "attachment" not in content_disposition.lower() and "inline" not in content_disposition.lower():
                # Also check by content type - some attachments don't have Content-Disposition
                content_type = part.get_content_type()
                if content_type in ['text/plain', 'text/html', 'multipart/alternative', 'multipart/mixed']:
                    continue

            # Get filename
            filename = part.get_filename()
            if not filename:
                # Try to get filename from Content-Disposition header
                import re
                match = re.search(r'filename[*]?=["\']?([^"\';\n]+)', content_disposition)
                if match:
                    filename = match.group(1)

            if not filename:
                continue

            # Decode filename if necessary
            filename = self._decode_header(filename)

            # Get content type
            content_type = part.get_content_type()

            # Skip unsupported types
            file_ext = Path(filename).suffix.lower()
            supported_extensions = list(SUPPORTED_ATTACHMENT_TYPES.values())
            type_supported = content_type in SUPPORTED_ATTACHMENT_TYPES or file_ext in supported_extensions

            if not type_supported:
                print(f"    → Skipping unsupported attachment: {filename} ({content_type})")
                continue

            # Get attachment data
            try:
                data = part.get_payload(decode=True)
                if data:
                    attachments.append({
                        'filename': filename,
                        'content_type': content_type,
                        'data': data,
                        'size': len(data)
                    })
                    print(f"    → Found attachment: {filename} ({len(data)} bytes)")
            except Exception as e:
                print(f"    ✗ Failed to extract attachment {filename}: {e}")

        return attachments

    def _process_attachment(
        self,
        tenant_id: str,
        attachment: Dict,
        email_subject: str,
        email_sender: str,
        email_timestamp,
        parent_email_id: str
    ) -> Optional[Document]:
        """
        Process an email attachment: save to temp file, parse, and create document.

        Args:
            tenant_id: Tenant ID
            attachment: Dict with filename, content_type, data
            email_subject: Subject of the parent email
            email_sender: Sender of the parent email
            email_timestamp: Timestamp of the parent email
            parent_email_id: ID of the parent email document

        Returns:
            Created Document or None if parsing failed
        """
        filename = attachment['filename']
        data = attachment['data']

        # Create temp file with proper extension
        file_ext = Path(filename).suffix.lower()
        if not file_ext:
            # Try to get extension from content type
            file_ext = SUPPORTED_ATTACHMENT_TYPES.get(attachment['content_type'], '.bin')

        # Save to temp file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"email_attachment_{int(datetime.now().timestamp() * 1000)}{file_ext}")

        try:
            with open(temp_path, 'wb') as f:
                f.write(data)

            # Parse the file
            if self.parser.can_parse(temp_path):
                parse_result = self.parser.parse(temp_path)

                if parse_result and parse_result.get('content'):
                    # Create document for the attachment
                    document = Document(
                        tenant_id=tenant_id,
                        external_id=f"email_att_{int(datetime.now().timestamp() * 1000)}_{filename}",
                        source_type="email_attachment",
                        title=f"{email_subject} - {filename}",
                        content=parse_result['content'],
                        sender_email=email_sender,
                        source_created_at=email_timestamp,
                        doc_metadata={
                            "source": "email_forwarding_attachment",
                            "forwarding_email": self.email_address,
                            "attachment_filename": filename,
                            "attachment_content_type": attachment['content_type'],
                            "attachment_size": attachment['size'],
                            "parent_email_id": parent_email_id,
                            "parent_email_subject": email_subject,
                            "parse_metadata": parse_result.get('metadata', {})
                        },
                        status=DocumentStatus.PENDING
                    )

                    self.db.add(document)
                    self.db.commit()

                    print(f"      → Created document for attachment: {document.id}")
                    return document
                else:
                    print(f"      → No content extracted from {filename}")
            else:
                print(f"      → Cannot parse {filename} (unsupported format)")

        except Exception as e:
            print(f"      ✗ Error processing attachment {filename}: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass

        return None

    def _extract_original_sender(self, body: str, forwarded_by: str) -> str:
        """
        Try to extract original sender from forwarded email
        Looks for patterns like:
        - From: john@example.com
        - ---------- Forwarded message ---------
        """
        import re

        # Pattern 1: "From: email@domain.com" near top of email
        from_pattern = re.search(r'^From:\s*([^\n<]+(?:<[^>]+>)?)', body, re.MULTILINE | re.IGNORECASE)
        if from_pattern:
            return from_pattern.group(1).strip()

        # Pattern 2: Look for email address in first 500 chars
        email_pattern = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', body[:500])
        if email_pattern:
            found_email = email_pattern.group(1)
            # Make sure it's not the forwarding address
            if found_email.lower() not in forwarded_by.lower():
                return found_email

        # Fallback to forwarded_by
        return forwarded_by

    def _create_document(self, tenant_id: str, doc_data: Dict):
        """Create document in database"""

        # Create document
        document = Document(
            tenant_id=tenant_id,
            external_id=f"email_fwd_{int(datetime.now().timestamp() * 1000)}",
            source_type="email",
            title=doc_data["subject"],
            content=doc_data["content"],
            sender_email=doc_data["sender_email"],
            source_created_at=doc_data["timestamp"],
            doc_metadata=doc_data["metadata"],
            status=DocumentStatus.PENDING
        )

        self.db.add(document)
        self.db.commit()

        print(f"    → Created document: {document.id}")
        return document


def poll_forwarded_emails(tenant_id: str, db: Session, config=None, max_emails: int = 50) -> Dict:
    """
    Convenience function to poll for forwarded emails

    Args:
        tenant_id: Tenant ID
        db: Database session
        config: Configuration object
        max_emails: Max emails to process

    Returns:
        Result dict
    """
    service = EmailForwardingService(db, config)
    return service.fetch_new_emails(tenant_id, max_emails)
