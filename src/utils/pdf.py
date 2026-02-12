import fitz
import logging
from typing import List

logger = logging.getLogger("bank_statement_intel.pdf_utils")

def get_pdf_page_count(pdf_path: str) -> int:
    """Returns the total number of pages in the PDF."""
    try:
        with fitz.open(pdf_path) as doc:
            return len(doc)
    except Exception as e:
        logger.error(f"Error reading PDF page count: {e}")
        return 0

def pdf_page_to_image_bytes(pdf_path: str, page_num: int, dpi: int = 150) -> bytes:
    """
    Renders a specific page of a PDF as a PNG image in memory and returns the bytes.
    
    Args:
        pdf_path (str): Path to the PDF.
        page_num (int): 0-indexed page number.
        dpi (int): Resolution to render. 150 is usually perfect for LLM readability.
        
    Returns:
        bytes: Raw PNG image bytes.
    """
    try:
        with fitz.open(pdf_path) as doc:
            if page_num < 0 or page_num >= len(doc):
                raise ValueError(f"Page index {page_num} out of bounds (PDF has {len(doc)} pages)")
            
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            return pix.tobytes("png")
    except Exception as e:
        logger.error(f"Error converting PDF page {page_num} to image: {e}")
        raise e
