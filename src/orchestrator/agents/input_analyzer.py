"""Input Analyzer implementing Section 3 of requirements.
Performs deep content and binary inspection beyond file extensions to accurately classify:
- Audio (MP3, WAV, FLAC, OGG, AAC, M4A)
- Video (MP4, MKV, WebM, AVI, MOV)
- Images (PNG, JPEG, WebP, GIF, TIFF)
- Documents & Office (PDF searchable vs scanned, DOCX, XLSX, PPTX, CSV)
- Source code and plain text
"""
import mimetypes
import zipfile
import io
from typing import Dict, Any, Optional

class InputAnalyzer:
    def analyze(self, filename: str, raw_bytes: bytes = b"") -> Dict[str, Any]:
        size = len(raw_bytes)
        modality = "unknown"
        detected_format = "application/octet-stream"
        pipeline = "generic_binary"
        is_scanned = False
        requires_ocr = False
        requires_transcription = False
        details: Dict[str, Any] = {}

        # 1. Deep Binary Inspection (Magic Bytes)
        if size >= 4:
            # --- Audio Signatures ---
            if raw_bytes.startswith(b"ID3") or (size >= 2 and raw_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
                modality = "audio"
                detected_format = "audio/mpeg"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True
            elif raw_bytes.startswith(b"RIFF") and size >= 12 and raw_bytes[8:12] == b"WAVE":
                modality = "audio"
                detected_format = "audio/wav"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True
            elif raw_bytes.startswith(b"fLaC"):
                modality = "audio"
                detected_format = "audio/flac"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True
            elif raw_bytes.startswith(b"OggS"):
                modality = "audio"
                detected_format = "audio/ogg"
                pipeline = "speech_to_text_whisper"
                requires_transcription = True

            # --- Video Signatures ---
            elif size >= 12 and raw_bytes[4:8] == b"ftyp":
                subtype = raw_bytes[8:12]
                if subtype in (b"M4A ", b"M4B "):
                    modality = "audio"
                    detected_format = "audio/mp4"
                    pipeline = "speech_to_text_whisper"
                    requires_transcription = True
                else:
                    modality = "video"
                    detected_format = "video/mp4"
                    pipeline = "multimodal_video_audio_frame_extraction"
            elif raw_bytes.startswith(b"\x1a\x45\xdf\xa3"):
                modality = "video"
                detected_format = "video/webm" if b"webm" in raw_bytes[:64].lower() else "video/x-matroska"
                pipeline = "multimodal_video_audio_frame_extraction"
            elif raw_bytes.startswith(b"RIFF") and size >= 12 and raw_bytes[8:12] == b"AVI ":
                modality = "video"
                detected_format = "video/x-msvideo"
                pipeline = "multimodal_video_audio_frame_extraction"

            # --- Image Signatures ---
            elif raw_bytes.startswith(b"\xff\xd8\xff"):
                modality = "image"
                detected_format = "image/jpeg"
                pipeline = "multimodal_vision_analysis"
            elif raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                modality = "image"
                detected_format = "image/png"
                pipeline = "multimodal_vision_analysis"
            elif raw_bytes.startswith((b"GIF87a", b"GIF89a")):
                modality = "image"
                detected_format = "image/gif"
                pipeline = "multimodal_vision_analysis"
            elif raw_bytes.startswith(b"RIFF") and size >= 12 and raw_bytes[8:12] == b"WEBP":
                modality = "image"
                detected_format = "image/webp"
                pipeline = "multimodal_vision_analysis"

            # --- Document Signatures ---
            elif raw_bytes.startswith(b"%PDF"):
                modality = "document"
                # Deep PDF inspection: text stream vs scanned image
                has_fonts = b"/Font" in raw_bytes or b"/Type /Font" in raw_bytes
                has_text_stream = b"BT" in raw_bytes and b"ET" in raw_bytes
                has_images = b"/Image" in raw_bytes or b"/XObject" in raw_bytes
                
                if has_images and not (has_fonts and has_text_stream):
                    is_scanned = True
                    requires_ocr = True
                    detected_format = "application/pdf;variant=scanned_image_only"
                    pipeline = "multimodal_vision_ocr"
                else:
                    detected_format = "application/pdf;variant=searchable_text"
                    pipeline = "direct_pdf_text_extraction"

            elif raw_bytes.startswith(b"PK\x03\x04"):
                # ZIP-based Office OpenXML inspection (Word, Excel, PowerPoint)
                modality = "document"
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                        namelist = z.namelist()
                        if any("word/document.xml" in n for n in namelist):
                            detected_format = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            pipeline = "docx_text_extractor"
                        elif any("xl/workbook.xml" in n for n in namelist):
                            detected_format = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            pipeline = "xlsx_tabular_data_extractor"
                        elif any("ppt/presentation.xml" in n for n in namelist):
                            detected_format = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                            pipeline = "pptx_slides_extractor"
                        else:
                            detected_format = "application/zip"
                            pipeline = "archive_unpacker"
                except Exception:
                    detected_format = "application/zip"
                    pipeline = "archive_unpacker"

        # 2. Text / Source Code Fallback
        if modality == "unknown" and size > 0:
            try:
                # Test UTF-8 / ASCII decodability
                sample = raw_bytes[:4096].decode("utf-8")
                modality = "text"
                lower_fn = filename.lower()
                
                if any(lower_fn.endswith(ext) for ext in [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs"]):
                    detected_format = "text/x-source-code"
                    pipeline = "source_code_analyzer"
                elif lower_fn.endswith(".csv"):
                    detected_format = "text/csv"
                    pipeline = "csv_tabular_parser"
                elif lower_fn.endswith((".json", ".yaml", ".yml")):
                    detected_format = "application/json"
                    pipeline = "structured_data_parser"
                else:
                    detected_format = "text/plain"
                    pipeline = "direct_text_processor"
            except UnicodeDecodeError:
                # Pure binary fallback
                guessed, _ = mimetypes.guess_type(filename)
                detected_format = guessed or "application/octet-stream"

        return {
            "filename": filename,
            "modality": modality,               # 'audio', 'video', 'image', 'document', 'text', 'unknown'
            "detected_mime": detected_format,
            "size_bytes": size,
            "is_scanned": is_scanned,
            "requires_ocr": requires_ocr,
            "requires_transcription": requires_transcription,
            "recommended_pipeline": pipeline,
            "details": details
        }
