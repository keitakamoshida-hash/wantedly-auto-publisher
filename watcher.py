"""input/ フォルダの監視と処理パイプライン"""

import shutil
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
from article_generator import generate_article, save_article
from publisher import publish_to_wantedly, publish_to_note


def find_article_file(folder: Path):
    """フォルダ内の記事ファイルを探す"""
    for ext in config.ARTICLE_EXTENSIONS:
        files = list(folder.glob(f"*{ext}"))
        if files:
            return files[0]
    return None


def find_image_files(folder: Path) -> list[Path]:
    """フォルダ内の画像ファイルを探す"""
    images = []
    for ext in config.IMAGE_EXTENSIONS:
        images.extend(folder.glob(f"*{ext}"))
    return sorted(images)


def process_folder(folder: Path):
    """フォルダ1つを処理するパイプライン"""
    print(f"\n{'='*50}")
    print(f"処理開始: {folder.name}")
    print(f"{'='*50}")

    try:
        # 1. 記事ファイルを探す
        article_file = find_article_file(folder)
        if not article_file:
            print(f"  エラー: 記事ファイル（.txt / .md）が見つかりません")
            return

        draft_text = article_file.read_text(encoding="utf-8")
        print(f"  記事原稿: {article_file.name} ({len(draft_text)}文字)")

        # 2. 画像ファイルを探す
        image_files = find_image_files(folder)
        if image_files:
            print(f"  写真: {len(image_files)}枚 ({', '.join(f.name for f in image_files)})")
        else:
            print("  写真: なし")

        # 3. Claude APIで記事を成形
        article_md = generate_article(draft_text)

        # 4. ファイル保存
        md_path, html_path = save_article(article_md, folder.name)

        # 5. Wantedly に下書き投稿（写真付き）
        publish_to_wantedly(article_md, image_files)

        # 6. note に下書き投稿（写真付き）
        publish_to_note(article_md, image_files)

        # 7. 処理済みフォルダを移動
        done_path = config.DONE_DIR / folder.name
        if done_path.exists():
            shutil.rmtree(done_path)
        shutil.move(str(folder), str(done_path))

        print(f"\n処理完了: {folder.name} → done/")
        print(f"  記事: {md_path}")
        print(f"  HTML: {html_path}")
        print(f"  Wantedly・note に下書き投稿済み（各サイトで確認してください）")

    except Exception as e:
        print(f"\nエラー: {folder.name} の処理に失敗しました")
        print(f"  原因: {e}")


class ArticleFolderHandler(FileSystemEventHandler):
    """input/ フォルダに追加されたサブフォルダを検知するハンドラ"""

    def __init__(self):
        self._processing = set()

    def on_created(self, event):
        if not event.is_directory:
            return

        path = Path(event.src_path)

        # done/ 内は無視
        if "done" in path.parts:
            return

        # input/ 直下のフォルダのみ対象
        if path.parent != config.INPUT_DIR:
            return

        # 重複処理防止
        if path.name in self._processing:
            return

        self._processing.add(path.name)

        # ファイルのコピー完了を待つ
        time.sleep(3)

        try:
            process_folder(path)
        finally:
            self._processing.discard(path.name)


def start_watching():
    """input/ フォルダの監視を開始する"""
    # 起動時に既にあるフォルダを処理
    existing = [
        d for d in config.INPUT_DIR.iterdir()
        if d.is_dir() and d.name != "done"
    ]
    for d in existing:
        if find_article_file(d):
            process_folder(d)

    # フォルダ監視開始
    observer = Observer()
    observer.schedule(ArticleFolderHandler(), str(config.INPUT_DIR), recursive=False)
    observer.start()

    print(f"\n監視を開始しました。input/ にフォルダを作成して記事原稿と写真を入れてください。")
    print(f"  監視フォルダ: {config.INPUT_DIR}")
    print(f"  記事形式: {', '.join(sorted(config.ARTICLE_EXTENSIONS))}")
    print(f"  画像形式: {', '.join(sorted(config.IMAGE_EXTENSIONS))}")
    print(f"  終了するには Ctrl+C を押してください\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n監視を終了しました。")
    observer.join()
