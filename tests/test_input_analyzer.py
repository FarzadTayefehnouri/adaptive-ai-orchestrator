import unittest
from src.orchestrator.agents.input_analyzer import InputAnalyzer

class TestInputAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = InputAnalyzer()

    def test_audio_detection_by_magic_bytes(self):
        # MP3 disguised as .txt
        mp3_bytes = b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x03Lavf58.29.100"
        result = self.analyzer.analyze("disguised_file.txt", mp3_bytes)
        self.assertEqual(result["modality"], "audio")
        self.assertEqual(result["detected_mime"], "audio/mpeg")
        self.assertTrue(result["requires_transcription"])
        self.assertEqual(result["recommended_pipeline"], "speech_to_text_whisper")

        # WAV
        wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        res_wav = self.analyzer.analyze("recording.wav", wav_bytes)
        self.assertEqual(res_wav["modality"], "audio")
        self.assertEqual(res_wav["detected_mime"], "audio/wav")

    def test_video_detection_by_magic_bytes(self):
        # MP4 video
        mp4_bytes = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
        res_mp4 = self.analyzer.analyze("video_sample.bin", mp4_bytes)
        self.assertEqual(res_mp4["modality"], "video")
        self.assertEqual(res_mp4["detected_mime"], "video/mp4")
        self.assertEqual(res_mp4["recommended_pipeline"], "multimodal_video_audio_frame_extraction")

        # WebM / MKV
        webm_bytes = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04\x42\xf3\x81\x08\x42\x82\x84webm"
        res_webm = self.analyzer.analyze("stream.dat", webm_bytes)
        self.assertEqual(res_webm["modality"], "video")
        self.assertIn("video/", res_webm["detected_mime"])

    def test_image_detection(self):
        # PNG
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        res_png = self.analyzer.analyze("photo.png", png_bytes)
        self.assertEqual(res_png["modality"], "image")
        self.assertEqual(res_png["detected_mime"], "image/png")

        # JPEG
        jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01"
        res_jpg = self.analyzer.analyze("image.jpg", jpg_bytes)
        self.assertEqual(res_jpg["modality"], "image")
        self.assertEqual(res_jpg["detected_mime"], "image/jpeg")

    def test_pdf_scanned_vs_searchable(self):
        # Scanned PDF (images without font/text stream)
        scanned_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /XObject /Subtype /Image >>\nendobj"
        res_scanned = self.analyzer.analyze("doc.pdf", scanned_pdf)
        self.assertEqual(res_scanned["modality"], "document")
        self.assertTrue(res_scanned["is_scanned"])
        self.assertTrue(res_scanned["requires_ocr"])
        self.assertEqual(res_scanned["recommended_pipeline"], "multimodal_vision_ocr")

        # Searchable PDF
        searchable_pdf = b"%PDF-1.4\n1 0 obj\n<< /Font << /F1 2 0 R >> >>\nstream\nBT /F1 12 Tf (Hello) Tj ET\nendstream"
        res_searchable = self.analyzer.analyze("doc.pdf", searchable_pdf)
        self.assertFalse(res_searchable["is_scanned"])
        self.assertFalse(res_searchable["requires_ocr"])
        self.assertEqual(res_searchable["recommended_pipeline"], "direct_pdf_text_extraction")

    def test_text_and_source_code(self):
        code_bytes = b"def calculate_metrics(data):\n    return sum(data)\n"
        res_code = self.analyzer.analyze("script.py", code_bytes)
        self.assertEqual(res_code["modality"], "text")
        self.assertEqual(res_code["detected_mime"], "text/x-source-code")
        self.assertEqual(res_code["recommended_pipeline"], "source_code_analyzer")

if __name__ == '__main__':
    unittest.main()
