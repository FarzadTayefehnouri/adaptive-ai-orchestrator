"""Input Analyzer implementing Section 3 of requirements.
Performs deep content inspection beyond file extensions (e.g., text vs scanned PDF).
"""
import mimetypes
from typing import Dict, Any

class InputAnalyzer:
    def analyze(self, filename: str, raw_bytes: bytes = b"") -> Dict[str, Any]:
        guessed_type, _ = mimetypes.guess_type(filename)
        guessed_type = guessed_type or "application/octet-stream"
        
        is_pdf = filename.lower().endswith(".pdf") or "pdf" in guessed_type
        is_scanned = False
        detected_format = guessed_type
        
        if is_pdf and len(raw_bytes) > 0:
            has_fonts = b"/Font" in raw_bytes or b"/Type /Font" in raw_bytes
            has_text_stream = b"BT" in raw_bytes and b"ET" in raw_bytes
            has_images = b"/Image" in raw_bytes or b"/XObject" in raw_bytes
            
            if has_images and not (has_fonts and has_text_stream):
                is_scanned = True
                detected_format = "application/pdf;variant=scanned_image_only"
            else:
                detected_format = "application/pdf;variant=searchable_text"

        return {
            "filename": filename,
            "detected_mime": detected_format,
            "is_scanned": is_scanned,
            "size_bytes": len(raw_bytes),
            "requires_ocr": is_scanned,
            "recommended_pipeline": "multimodal_vision_ocr" if is_scanned else "direct_text_extraction"
        }
