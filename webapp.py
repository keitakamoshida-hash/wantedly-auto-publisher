"""Webアプリ: 記事原稿 + 写真 → Wantedly自動投稿"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import re
import unicodedata

import config
from publisher import publish_to_wantedly, _parse_article


def safe_filename(filename: str) -> str:
    """日本語ファイル名を保持しつつ安全にする"""
    # パス区切り文字を除去
    filename = filename.replace("/", "_").replace("\\", "_")
    # 制御文字を除去
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    # 先頭のドットを除去
    filename = filename.lstrip(".")
    return filename or "unnamed"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "wantedly_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_ARTICLE = {".txt", ".md", ".docx"}
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _read_article_file(file_path: Path) -> str:
    """記事ファイルを読み込む（docx対応）"""
    if file_path.suffix.lower() == ".docx":
        from docx import Document
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        return file_path.read_text(encoding="utf-8")


@app.route("/")
def index():
    """アップロード画面"""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """ファイルアップロード → プレビュー画面へ"""
    # 記事ファイル
    article_file = request.files.get("article")
    if not article_file or article_file.filename == "":
        flash("記事ファイルを選択してください")
        return redirect(url_for("index"))

    # 一時ディレクトリを作成
    session_dir = Path(tempfile.mkdtemp(dir=UPLOAD_DIR))

    # 記事保存
    article_name = safe_filename(article_file.filename)
    article_path = session_dir / article_name
    article_file.save(str(article_path))

    # 画像保存
    image_files = request.files.getlist("images")
    image_names = []
    for img in image_files:
        if img and img.filename:
            img_name = safe_filename(img.filename)
            img_path = session_dir / img_name
            img.save(str(img_path))
            image_names.append(img_name)

    # 記事内容を読み込んでパース
    article_text = _read_article_file(article_path)
    title, intro, toc, sections, closing = _parse_article(article_text)

    session_id = session_dir.name

    return render_template(
        "preview.html",
        session_id=session_id,
        title=title,
        intro=intro,
        toc=toc,
        sections=sections,
        closing=closing,
        image_names=image_names,
        article_name=article_name,
    )


def _get_latest_recruitment_url():
    """Senjin Holdingsの直近の募集記事URLを取得する"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                user_data_dir=str(config.BROWSER_DATA_DIR),
                headless=True,
                locale="ja-JP",
            )
            page = context.new_page()
            page.goto("https://www.wantedly.com/companies/senjinholdings/projects", timeout=60000)
            import time
            time.sleep(5)
            links = page.locator('a[href*="/projects/"]')
            for i in range(links.count()):
                href = links.nth(i).get_attribute("href") or ""
                if "/projects/" in href and href != "/enterprise/projects/new":
                    context.close()
                    return f"https://www.wantedly.com{href}"
            context.close()
    except Exception:
        pass
    return "https://www.wantedly.com/projects/2389407"


@app.route("/publish", methods=["POST"])
def publish():
    """Wantedlyに投稿"""
    session_id = request.form.get("session_id")
    article_name = request.form.get("article_name")
    cover_image = request.form.get("cover_image")
    all_images = request.form.getlist("all_images")
    platform = request.form.get("platform", "wantedly")

    session_dir = UPLOAD_DIR / session_id

    if not session_dir.exists():
        flash("セッションが期限切れです。もう一度アップロードしてください。")
        return redirect(url_for("index"))

    # 記事読み込み
    article_path = session_dir / article_name
    article_text = _read_article_file(article_path)

    # 画像パスを構築（カバー + カバー以外を自動で本文画像に）
    image_paths = []
    if cover_image:
        image_paths.append(session_dir / cover_image)
    for img_name in all_images:
        if img_name and img_name != cover_image:
            image_paths.append(session_dir / img_name)

    # 直近の募集記事URLを自動取得
    recruitment_url = _get_latest_recruitment_url()

    # 投稿実行
    try:
        if platform == "wantedly":
            import traceback
            print(f"[PUBLISH] 投稿開始: {article_name}, 画像{len(image_paths)}枚")
            print(f"[PUBLISH] WANTEDLY_EMAIL: {config.WANTEDLY_EMAIL[:5]}...")
            print(f"[PUBLISH] HEADLESS: {os.environ.get('HEADLESS', 'not set')}")
            success = publish_to_wantedly(
                article_text,
                image_paths,
                recruitment_url=recruitment_url,
            )
            if success:
                flash("Wantedlyに下書き投稿しました！管理画面で確認してください。")
            else:
                flash("投稿に失敗しました。output/の記事ファイルから手動で投稿してください。")
        elif platform == "note":
            flash("noteへの投稿機能は準備中です。")
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[PUBLISH ERROR] {error_detail}")
        flash(f"エラーが発生しました: {e}")

    # 一時ファイル削除
    shutil.rmtree(session_dir, ignore_errors=True)

    return redirect(url_for("index"))


@app.route("/preview_image/<session_id>/<filename>")
def preview_image(session_id, filename):
    """アップロード画像のプレビュー用"""
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR / session_id, filename)


if __name__ == "__main__":
    print("=" * 50)
    print("Wantedly 記事自動投稿 Webアプリ")
    print("http://localhost:8080 でアクセスしてください")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=8080)
