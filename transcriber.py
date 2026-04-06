"""Gemini API による音声文字起こし"""

from __future__ import annotations

import time
from pathlib import Path

from google import genai
from google.genai import types

import config

MIME_MAP = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}


def transcribe(audio_path: Path) -> str:
    """音声ファイルを文字起こしする"""
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    mime_type = MIME_MAP.get(audio_path.suffix.lower(), "audio/mpeg")
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)

    print(f"  文字起こし中: {audio_path.name} ({file_size_mb:.1f}MB)")

    # 20MB以上はFile APIでアップロード
    if file_size_mb > 20:
        print("    大きいファイルのためアップロード中...")
        uploaded = client.files.upload(
            file=str(audio_path),
            config=types.UploadFileConfig(mime_type=mime_type),
        )
        # アップロード完了を待つ
        while uploaded.state.name == "PROCESSING":
            time.sleep(5)
            uploaded = client.files.get(name=uploaded.name)
            print(f"    処理中... ({uploaded.state.name})")

        audio_part = types.Part.from_uri(
            file_uri=uploaded.uri,
            mime_type=uploaded.mime_type,
        )
    else:
        audio_bytes = audio_path.read_bytes()
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

    prompt_text = (
        "この音声を正確に日本語で文字起こししてください。\n"
        "話者が複数いる場合は話者を区別してください（例: 話者A:、話者B:）。\n"
        "インタビュー形式の場合は、質問者と回答者を区別してください。\n"
        "話し言葉のまま、できるだけ忠実に文字起こししてください。"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[audio_part, prompt_text],
    )

    transcript = response.text
    print(f"  文字起こし完了: {len(transcript)}文字")
    return transcript
