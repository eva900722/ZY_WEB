from io import BytesIO
from pathlib import Path
import uuid
from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from .models import Attachment


def validate_uploads(files):
    if len(files) > 5:
        raise ValidationError("每次最多5個附件")
    result = []
    for f in files:
        if f.size > 10 * 1024 * 1024:
            raise ValidationError("單檔不得超過10MB")
        data = f.read()
        f.seek(0)
        suffix = Path(f.name).suffix.lower()
        if suffix == ".pdf" and data.startswith(b"%PDF-"):
            from pypdf import PdfReader

            try:
                pdf = PdfReader(BytesIO(data))
                count = len(pdf.pages)
                if count < 1:
                    raise ValueError()
            except Exception:
                raise ValidationError("PDF 格式不正確或已加密")
            mime = "application/pdf"
        elif suffix in [".jpg", ".jpeg", ".png"]:
            try:
                image = Image.open(BytesIO(data))
                image.verify()
                if image.format not in ["JPEG", "PNG"]:
                    raise ValueError()
                mime = "image/png" if image.format == "PNG" else "image/jpeg"
            except Exception:
                raise ValidationError("圖片格式不正確")
        else:
            raise ValidationError("僅接受 PNG、JPEG、PDF")
        result.append((f, data, mime))
    return result


def store(ticket, user, validated, entry=None):
    # Caller cleans any written files if the surrounding transaction rolls back.
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    saved = []
    try:
        for f, data, mime in validated:
            key = uuid.uuid4().hex
            path = root / key
            path.write_bytes(data)
            saved.append(path)
            Attachment.objects.create(
                ticket=ticket,
                entry=entry,
                uploaded_by=user,
                name=Path(f.name).name[:200],
                key=key,
                content_type=mime,
                size=len(data),
                internal=bool(entry and entry.internal),
            )
    except Exception:
        for p in saved:
            p.unlink(missing_ok=True)
        raise
    return saved
