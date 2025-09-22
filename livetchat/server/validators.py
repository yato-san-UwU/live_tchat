def _sniff_is_image(prefix: bytes) -> bool:
    return (
        prefix.startswith(b'\xff\xd8\xff') or
        prefix.startswith(b'\x89PNG\r\n\x1a\n') or
        prefix.startswith(b'GIF87a') or
        prefix.startswith(b'GIF89a')
    )

def _sniff_is_mp4(prefix: bytes) -> bool:
    return len(prefix) >= 12 and prefix[4:8] == b'ftyp'

def _sniff_is_audio(prefix: bytes, content_type: str) -> bool:
    ct = (content_type or "").lower()
    if "mpeg" in ct:  # mp3
        return prefix.startswith(b'ID3') or (len(prefix) >= 2 and prefix[0] == 0xFF and (prefix[1] & 0xE0) == 0xE0)
    if "wav" in ct:
        return len(prefix) >= 12 and prefix.startswith(b'RIFF') and prefix[8:12] == b'WAVE'
    if "ogg" in ct:
        return prefix.startswith(b'OggS')
    if "mp4" in ct:
        return _sniff_is_mp4(prefix)
    if prefix.startswith(b'ID3') or (len(prefix) >= 2 and prefix[0] == 0xFF and (prefix[1] & 0xE0) == 0xE0):
        return True
    return False
