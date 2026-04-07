"""全自動パイプライン: 音声+写真 → 文字起こし → 記事整形 → 写真配置 → Wantedly下書き作成"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

from transcriber import transcribe
from article_generator import generate_article, save_article
from publisher import publish_to_wantedly


def run_pipeline(
    audio_path: Path,
    image_paths: list[Path],
    cover_image: Path,
    interviewee_name: str,
    vol_number: str = "XX",
    schedule_datetime: str = None,
):
    """全自動パイプラインを実行する

    Args:
        audio_path: 音声ファイルのパス
        image_paths: 全画像ファイルのパスリスト（カバー含む）
        cover_image: カバー画像のパス
        interviewee_name: インタビュー対象者の名前
        vol_number: 社員インタビューのvol番号
        schedule_datetime: 投稿予約日時（"2026-04-10 12:00" 形式、Noneなら下書きのみ）
    """
    print("=" * 60)
    print("  全自動パイプライン開始")
    print("=" * 60)
    print(f"  音声: {audio_path.name}")
    print(f"  写真: {len(image_paths)}枚（カバー: {cover_image.name}）")
    print(f"  対象者: {interviewee_name}")
    print(f"  Vol: {vol_number}")
    if schedule_datetime:
        print(f"  予約投稿: {schedule_datetime}")
    print()

    # --- Step 1: 音声文字起こし ---
    print("[Step 1/4] 音声文字起こし")
    transcript = transcribe(audio_path)
    print()

    # --- Step 2: 記事整形 ---
    print("[Step 2/4] 記事整形（Claude API）")
    article = generate_article(transcript, vol_number=vol_number, interviewee_name=interviewee_name)

    # 保存
    folder_name = f"{interviewee_name}_{vol_number}"
    md_path, html_path = save_article(article, folder_name)
    print()

    # --- Step 3: 写真配置決定 ---
    print("[Step 3/4] 写真配置（Claude Vision）")
    # image_pathsの順番: カバーを先頭にする
    ordered_images = [cover_image] + [p for p in image_paths if p != cover_image]

    # --- Step 4: Wantedly投稿 ---
    print("[Step 4/4] Wantedly下書き作成")
    success = publish_to_wantedly(
        article,
        ordered_images,
        schedule_datetime=schedule_datetime,
    )

    print()
    print("=" * 60)
    if success:
        print("  パイプライン完了！")
        print(f"  記事: {md_path}")
        if schedule_datetime:
            print(f"  投稿予約: {schedule_datetime}")
        else:
            print("  Wantedlyに下書き保存済み")
    else:
        print("  Wantedly投稿に失敗しました")
        print(f"  記事は {md_path} に保存されています")
    print("=" * 60)

    return success


if __name__ == "__main__":
    # コマンドラインから実行する場合の例
    # python pipeline.py /path/to/audio.m4a /path/to/images/ cover.jpg 鴨志田 24
    if len(sys.argv) < 5:
        print("使い方: python pipeline.py <音声ファイル> <画像フォルダ> <カバー画像名> <対象者名> [vol番号] [予約日時]")
        print("例: python pipeline.py interview.m4a photos/ cover.jpg 鴨志田 24 '2026-04-10 12:00'")
        sys.exit(1)

    audio = Path(sys.argv[1])
    image_dir = Path(sys.argv[2])
    cover_name = sys.argv[3]
    name = sys.argv[4]
    vol = sys.argv[5] if len(sys.argv) > 5 else "XX"
    schedule = sys.argv[6] if len(sys.argv) > 6 else None

    images = sorted([f for f in image_dir.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    cover = image_dir / cover_name

    run_pipeline(audio, images, cover, name, vol, schedule)
