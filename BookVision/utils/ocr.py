import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import io
import cv2
import numpy as np
import logging
# Removed: from typing import str # 'str' is a built-in type

logger = logging.getLogger(__name__)

TESSERACT_LANG: str = 'eng'

def extract_text_from_image(image_path: str) -> str:
    try:
        logger.info(f"Starting OCR for image: {image_path}")
        img_cv = cv2.imread(image_path)
        if img_cv is None:
            logger.warning(f"OpenCV could not read {image_path}. Falling back to PIL.")
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=TESSERACT_LANG)
            logger.info(f"Successfully extracted text from {image_path} using PIL fallback.")
            return text

        gray_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        _, thresh_img = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        pil_img = Image.fromarray(thresh_img)
        text = pytesseract.image_to_string(pil_img, lang=TESSERACT_LANG, timeout=30)
        logger.info(f"Successfully extracted text from {image_path} using OpenCV and Tesseract.")
        return text
    except pytesseract.TesseractError as te:
        logger.error(f"Tesseract error during image OCR for {image_path}: {te}", exc_info=True)
        return "Error during Tesseract OCR processing."
    except Exception as e:
        logger.error(f"General error during image OCR for {image_path}: {e}", exc_info=True)
        try:
            logger.warning(f"Falling back to basic PIL processing for {image_path} due to previous error.")
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=TESSERACT_LANG, timeout=30)
            logger.info(f"Successfully extracted text from {image_path} using PIL fallback after error.")
            return text
        except Exception as pil_e:
            logger.error(f"Error during fallback PIL processing for {image_path}: {pil_e}", exc_info=True)
            return "Error extracting text from image after multiple attempts."


def extract_text_from_pdf(pdf_path: str) -> str:
    full_text: str = ""
    logger.info(f"Starting text extraction for PDF: {pdf_path}")
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page_text_content: str = ""
            try:
                page = doc.load_page(page_num)
                page_text_content = page.get_text("text")
                
                if not page_text_content.strip():
                    logger.info(f"Page {page_num+1} in {pdf_path} has no direct extractable text, attempting OCR.")
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if img_cv is not None:
                        gray_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                        _, thresh_img = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        pil_img = Image.fromarray(thresh_img)
                        page_text_content = pytesseract.image_to_string(pil_img, lang=TESSERACT_LANG, timeout=60)
                        logger.info(f"OCR for PDF page {page_num+1} yielded {len(page_text_content)} chars.")
                    else:
                        logger.warning(f"Could not convert PDF page {page_num+1} to image for OCR.")
                        page_text_content = "[OCR failed for this page]"
                full_text += page_text_content + "\n"
            except Exception as page_e:
                logger.error(f"Error processing page {page_num+1} of PDF {pdf_path}: {page_e}", exc_info=True)
                full_text += f"[Error processing page {page_num+1}]\n"
        
        logger.info(f"Successfully processed PDF: {pdf_path}")
        return full_text.strip()
    except Exception as e:
        logger.error(f"Critical error processing PDF {pdf_path}: {e}", exc_info=True)
        return "Error extracting text from PDF."
