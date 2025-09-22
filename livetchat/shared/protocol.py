# Shared protocol
CHUNK_SIZE = 64 * 1024
MAX_IMAGE_BYTES = 1_500_000
MAX_VIDEO_BYTES = 20_000_000
MAX_AUDIO_BYTES = 10_000_000
START_AFTER_IMAGE_MS = 1200
START_AFTER_VIDEO_MS = 3000
START_AFTER_AUDIO_MS = 1500
ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/gif"}
ALLOWED_VIDEO_MIME = {"video/mp4"}
ALLOWED_AUDIO_MIME = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"}
EVENT_IMAGE_START = "image_start"
EVENT_IMAGE_END   = "image_end"
EVENT_VIDEO_START = "video_start"
EVENT_VIDEO_END   = "video_end"
EVENT_AUDIO_START = "audio_start"
EVENT_AUDIO_END   = "audio_end"
