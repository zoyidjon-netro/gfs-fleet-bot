from io import BytesIO
from pypdf import PdfReader
from .domain import extract_vins


def parse_pdf(content, ocr_enabled=False):
    reader = PdfReader(BytesIO(content))
    if len(reader.pages) > 250:
        raise ValueError("PDF 250 sahifadan oshmasin")
    texts = []
    scanned = []
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        texts.append(text)
        if len(text.strip()) < 20:
            scanned.append(index)
    if scanned:
        if not ocr_enabled:
            raise ValueError("PDFda skan sahifalar bor. OCR_ENABLED=true va OCR bog'liqliklari kerak; qisman hisobot chiqarilmadi.")
        import pypdfium2
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        doc = pypdfium2.PdfDocument(content)
        try:
            for index in scanned:
                page = doc[index]
                try:
                    image = page.render(scale=3).to_pil().convert("RGB")
                    result, _ = ocr(np.array(image))
                    texts[index] = "\n".join(item[1] for item in (result or []))
                finally:
                    page.close()
        finally:
            doc.close()
    vins = extract_vins("\n".join(texts))
    if not vins:
        raise ValueError("PDFdan VIN topilmadi. COI formati yoki OCR natijasini tekshiring.")
    return vins
