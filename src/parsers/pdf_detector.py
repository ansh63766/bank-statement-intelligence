import logging
from typing import Tuple, Literal
import pdfplumber

logger = logging.getLogger("bank_statement_intel.detector")

def detect_pdf_type_and_bank(pdf_path: str) -> Tuple[Literal["TEXT", "SCANNED"], str]:
    """
    Detects whether the PDF is text-based (digital) or scanned (image-only),
    and attempts to identify the bank from key text matches.
    
    Args:
        pdf_path (str): The absolute path to the PDF statement.
        
    Returns:
        Tuple[str, str]: ("TEXT" | "SCANNED", bank_name)
        bank_name is one of: "SBI", "HDFC", "ICICI", "Axis", or "UNKNOWN"
    """
    is_scanned = True
    bank_name = "UNKNOWN"
    raw_text = ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # We check the first few pages (up to 3) to extract text and identify the bank
            pages_to_check = pdf.pages[:3]
            total_chars = 0
            
            for page in pages_to_check:
                page_text = page.extract_text()
                if page_text:
                    raw_text += page_text + "\n"
                    total_chars += len(page_text.strip())
            
            # If we get significant text, it's digital
            # A threshold of 100 characters over 1-3 pages is extremely safe
            if total_chars > 100:
                is_scanned = False
                
    except Exception as e:
        logger.error(f"Error opening/reading PDF during detection: {e}")
        # Default to scanned if we can't open/extract to let LLM fallback attempt it
        return "SCANNED", "UNKNOWN"
        
    if is_scanned:
        # For scanned PDFs, we cannot easily search the text without OCR.
        # We return ("SCANNED", "UNKNOWN") and let the LLM vision parser parse it.
        return "SCANNED", "UNKNOWN"
    
    # Extract only the statement header (text before the transaction table)
    # to avoid matching other banks mentioned inside transaction particulars.
    import re
    lower_text = raw_text.lower()
    header_text = lower_text
    for marker in ["opening balance", "particulars", "tran date", "txn date", "value date"]:
        if marker in lower_text:
            header_text = lower_text.split(marker)[0]
            break
            
    if re.search(r"\bstate bank of india\b|\bsbi\b|\bs\.b\.i\b", header_text):
        bank_name = "SBI"
    elif re.search(r"\bhdfc bank\b|\bhdfc\b", header_text):
        bank_name = "HDFC"
    elif re.search(r"\bicici bank\b|\bicici\b", header_text):
        bank_name = "ICICI"
    elif re.search(r"\baxis bank\b|\baxis\b", header_text):
        bank_name = "Axis"
    else:
        # Fallback to full text if not found in header
        if re.search(r"\bstate bank of india\b|\bsbi\b|\bs\.b\.i\b", lower_text):
            bank_name = "SBI"
        elif re.search(r"\bhdfc bank\b|\bhdfc\b", lower_text):
            bank_name = "HDFC"
        elif re.search(r"\bicici bank\b|\bicici\b", lower_text):
            bank_name = "ICICI"
        elif re.search(r"\baxis bank\b|\baxis\b", lower_text):
            bank_name = "Axis"
    
    logger.info(f"PDF Detection Result: Type=TEXT, Bank={bank_name}")
    return "TEXT", bank_name


