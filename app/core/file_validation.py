from fastapi import HTTPException

MAGIC_BYTES: dict[str, list[bytes]] = {
    "application/pdf":    [b"%PDF"],
    "image/png":          [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg":         [b"\xff\xd8\xff"],
    "image/jpg":          [b"\xff\xd8\xff"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    "application/msword": [b"\xd0\xcf\x11\xe0"],
}


def validate_magic_bytes(contents: bytes, content_type: str) -> None:
    signatures = MAGIC_BYTES.get(content_type)
    if signatures is None:
        raise HTTPException(
            status_code=415,
            detail=f"Tipi i skedarit '{content_type}' nuk lejohet",
        )

    if not any(contents.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=415,
            detail="Skedari nuk përputhet me tipin e deklaruar — ngarkim i refuzuar",
        )
