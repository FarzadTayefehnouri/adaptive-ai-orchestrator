"""Enhanced Input Analyzer with Evidence-Based PDF Classification (Point 14).
Computes text characters, image pages, total pages, text-to-image ratio, and confidence score.
"""
import re
import io
import zipfile
import mimetypes
from typing import Dict, Any
from src.orchestrator.agents.input_analyzer import InputAnalyzer as BaseInputAnalyzer

class EnhancedInputAnalyzer(BaseInputAnalyzer):
    def analyze_pdf_deep(self, raw_bytes: bytes) -> Dict[str, Any]:
        """Point 14.2: Extract text char count, count pages & image objects, compute ratio & confidence."""
        page_matches = re.findall(rb"/Type\s*/Page\b", raw_bytes)
        total_pages = max(1, len(page_matches))
        image_matches = re.findall(rb"/Subtype\s*/Image\b", raw_bytes)
        image_pages = min(total_pages, len(image_matches))

        # Extract text inside PDF text blocks (...) between BT and ET
        text_blocks = re.findall(rb"BT(.*?)ET", raw_bytes, flags=re.DOTALL)
        extracted_chars = 0
        for blk in text_blocks:
            strings = re.findall(rb"\((.*?)\)", blk)
            extracted_chars += sum(len(s) for s in strings)

        chars_per_page = extracted_chars / float(total_pages)
        if extracted_chars < 30 and image_pages >= 1:
            classification = "scanned"
            confidence = min(0.99, round(0.75 + 0.20 * (image_pages / total_pages), 2))
            requires_ocr = True
        elif extracted_chars >= 30 and image_pages == 0:
            classification = "searchable_text"
            confidence = min(0.99, round(0.80 + min(0.19, chars_per_page / 500.0), 2))
            requires_ocr = False
        elif extracted_chars >= 30 and image_pages > 0:
            classification = "hybrid"
            confidence = 0.85
            requires_ocr = chars_per_page < 80
        else:
            classification = "scanned"
            confidence = 0.65
            requires_ocr = True

        return {
            "classification": classification,
            "confidence": confidence,
            "requires_ocr": requires_ocr,
            "evidence": {
                "text_chars": extracted_chars,
                "image_pages": image_pages,
                "total_pages": total_pages,
                "chars_per_page": round(chars_per_page, 1)
            }
        }

    def analyze(self, filename: str, raw_bytes: bytes = b"") -> Dict[str, Any]:
        base_res = super().analyze(filename, raw_bytes)
        if raw_bytes.startswith(b"%PDF"):
            pdf_detail = self.analyze_pdf_deep(raw_bytes)
            base_res["pdf_analysis"] = pdf_detail
            base_res["is_scanned"] = pdf_detail["classification"] == "scanned"
            base_res["requires_ocr"] = pdf_detail["requires_ocr"]
            base_res["confidence"] = pdf_detail["confidence"]
            base_res["evidence"] = pdf_detail["evidence"]
        return base_res
