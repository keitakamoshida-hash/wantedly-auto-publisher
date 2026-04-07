"""Wantedlyのストーリーをnoteにコピー投稿するスクリプト"""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext

import config


TEMP_IMG_DIR = Path("/tmp/wantedly_images")
TEMP_IMG_DIR.mkdir(parents=True, exist_ok=True)


def _get_browser_context(pw) -> BrowserContext:
    config.BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    headless = os.environ.get("HEADLESS", "false").lower() == "true"
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(config.BROWSER_DATA_DIR),
        headless=headless,
        locale="ja-JP",
    )


def extract_wantedly_article(page, article_id: str) -> dict:
    """Wantedlyの編集画面から記事の構造を抽出する"""
    import re

    page.goto(f"https://www.wantedly.com/manage_posts/articles/{article_id}/edit", timeout=60000)
    time.sleep(8)

    title = page.locator('textarea[placeholder="タイトル"]').input_value()

    # カバー画像を公開ページからスクリーンショットで取得
    cover_screenshot_path = ""
    try:
        pub_page = page.context.new_page()
        pub_page.goto(f"https://www.wantedly.com/companies/senjinholdings/post_articles/{article_id}", timeout=60000)
        time.sleep(5)
        cover_el = pub_page.locator('.article-cover-image-background')
        if cover_el.count() > 0:
            ss_path = str(TEMP_IMG_DIR / f"cover_{article_id}.png")
            cover_el.screenshot(path=ss_path)
            cover_screenshot_path = ss_path
        pub_page.close()
    except Exception:
        pass

    body = page.locator('[contenteditable="true"][role="textbox"]')

    children = body.evaluate("""el => Array.from(el.children).map((c, i) => ({
        idx: i,
        tag: c.tagName,
        text: (c.innerText || ''),
        hasImg: c.querySelector('img') !== null,
        imgSrc: c.querySelector('img')?.src || '',
        isToc: c.getAttribute('data-type') === 'table-of-contents'
    }))""")

    # 構造を解析
    intro_lines = []
    sections = []
    current_section = None
    images = []

    for child in children:
        tag = child["tag"]
        text = child["text"].strip()

        if child["isToc"]:
            continue

        if tag == "H2":
            if current_section:
                sections.append(current_section)
            current_section = {"heading": text, "paragraphs": [], "image_src": None}
            continue

        if child["hasImg"] and current_section:
            current_section["image_src"] = child["imgSrc"]
            continue

        if current_section is None:
            if text:
                intro_lines.append(text)
        else:
            if tag == "BLOCKQUOTE" and text:
                current_section["paragraphs"].append({"type": "question", "text": text})
            elif text:
                current_section["paragraphs"].append({"type": "text", "text": text})

    if current_section:
        sections.append(current_section)

    return {
        "title": title,
        "intro_lines": intro_lines,
        "sections": sections,
        "cover_screenshot_path": cover_screenshot_path,
    }


def download_image(url: str, filename: str) -> Path:
    """画像をダウンロードする（毎回上書き）"""
    path = TEMP_IMG_DIR / filename
    try:
        urllib.request.urlretrieve(url, str(path))
    except Exception as e:
        print(f"    画像DLエラー: {e}")
        return None
    return path


def publish_to_note_from_wantedly(article: dict) -> bool:
    """Wantedlyから抽出した記事をnoteに投稿する"""
    title = article["title"]
    intro_lines = article["intro_lines"]
    sections = article["sections"]

    print(f"\n  note投稿中: {title[:50]}...")

    try:
        with sync_playwright() as pw:
            context = _get_browser_context(pw)
            page = context.new_page()

            # noteログイン確認
            page.goto("https://note.com/dashboard", timeout=60000)
            time.sleep(5)
            if "login" in page.url:
                page.locator('input[placeholder*="mail"]').fill(config.NOTE_EMAIL)
                page.locator('input[type="password"]').fill(config.NOTE_PASSWORD)
                page.locator('button:has-text("ログイン")').click()
                time.sleep(8)

            # 新規記事作成
            page.goto("https://editor.note.com/new", timeout=60000)
            time.sleep(5)

            # カバー画像をアップロード（スクリーンショットから）
            cover_path_str = article.get("cover_screenshot_path", "")
            if cover_path_str:
                try:
                    cover_path = Path(cover_path_str)
                    if cover_path.exists():
                        page.locator('[aria-label="画像を追加"]').click()
                        time.sleep(2)
                        with page.expect_file_chooser() as fc_info:
                            page.locator('button:has-text("画像をアップロード")').click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(str(cover_path))
                        time.sleep(5)
                        # クロップモーダルの「保存」をクリック（モーダル内のボタン）
                        modal = page.locator('.ReactModalPortal')
                        modal.locator('button:has-text("保存")').click(force=True)
                        time.sleep(3)
                        print("    カバー画像: OK")
                except Exception as e:
                    print(f"    カバー画像エラー: {e}")

            # タイトル
            title_input = page.locator('[placeholder="記事タイトル"]')
            title_input.fill(title)
            print(f"    タイトル: {title[:50]}")

            # 本文エディタ
            body = page.locator('.ProseMirror[role="textbox"]')
            body.click()
            time.sleep(1)

            # 導入文
            for line in intro_lines:
                page.keyboard.type(line)
                body.press("Enter")
                time.sleep(0.3)
            print("    導入文完了")

            # 導入文の直後に目次を挿入（この時点でカーソルは導入文の次の空行にある）
            try:
                page.locator('[aria-label="メニューを開く"]').click()
                time.sleep(1)
                page.locator('button:has-text("目次")').click()
                time.sleep(3)
                print("    目次完了")
            except Exception as e:
                print(f"    目次エラー: {e}")

            # 目次の下にカーソルを移動
            # 目次ブロックの後ろに移動するため、目次要素の次をクリック
            try:
                toc = body.locator('table-of-contents, [class*="table-of-contents"], [data-type="toc"]')
                if toc.count() > 0:
                    toc.first.click()
                    time.sleep(0.3)
                    page.keyboard.press("ArrowDown")
                    time.sleep(0.3)
                else:
                    page.keyboard.press("Meta+End")
                body.press("Enter")
                time.sleep(0.5)
            except Exception:
                page.keyboard.press("Meta+End")
                body.press("Enter")
                time.sleep(0.5)

            # 各セクション
            for i, section in enumerate(sections):
                # H2（大見出し）
                page.locator('[aria-label="メニューを開く"]').click()
                time.sleep(1)
                page.locator('button:has-text("大見出し")').click()
                time.sleep(0.5)
                page.keyboard.type(section["heading"])
                body.press("Enter")
                time.sleep(0.5)

                # 画像
                if section.get("image_src"):
                    # 記事タイトルのハッシュ値で画像名をユニークにする
                    import hashlib
                    art_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                    img_path = download_image(section["image_src"], f"img_{art_hash}_{i}.jpg")
                    if img_path and img_path.exists():
                        try:
                            page.locator('[aria-label="メニューを開く"]').click()
                            time.sleep(1)
                            page.locator('button:has-text("画像")').click()
                            time.sleep(2)
                            file_input = page.locator('input[type="file"][accept*="image"]')
                            file_input.set_input_files(str(img_path))
                            print(f"    画像{i+1}: OK")
                            time.sleep(4)
                            body.press("Enter")
                            time.sleep(0.5)
                        except Exception as e:
                            print(f"    画像{i+1}エラー: {e}")

                # 質問・回答
                for para in section["paragraphs"]:
                    if para["type"] == "question":
                        page.locator('[aria-label="メニューを開く"]').click()
                        time.sleep(1)
                        page.locator('button:has-text("小見出し")').click()
                        time.sleep(0.5)
                        page.keyboard.type(para["text"])
                        body.press("Enter")
                    else:
                        page.keyboard.type(para["text"])
                        body.press("Enter")
                    time.sleep(0.1)

                body.press("Enter")
                time.sleep(0.3)

            # --- 募集セクション ---
            try:
                body.press("Enter")
                time.sleep(0.5)

                # 区切り線
                page.locator('[aria-label="メニューを開く"]').click()
                time.sleep(1)
                page.locator('button:has-text("区切り線")').click()
                time.sleep(1)
                body.press("Enter")
                time.sleep(0.5)

                # 見出し
                page.locator('[aria-label="メニューを開く"]').click()
                time.sleep(1)
                page.locator('button:has-text("大見出し")').click()
                time.sleep(0.5)
                page.keyboard.type("Senjin Holdingsでは一緒に働く仲間を募集しています")
                body.press("Enter")
                time.sleep(0.5)
                # 大見出しのコンテキストを抜けるために通常テキストを入力→削除
                page.keyboard.type(" ")
                time.sleep(0.3)
                page.keyboard.press("Backspace")
                time.sleep(0.5)
                body.press("Enter")
                time.sleep(0.5)

                # 募集リンクを埋め込み
                recruit_urls = [
                    "https://www.wantedly.com/projects/2389407",
                    "https://www.wantedly.com/projects/2393042",
                    "https://www.wantedly.com/projects/2393724",
                ]
                for url in recruit_urls:
                    page.locator('[aria-label="メニューを開く"]').click()
                    time.sleep(1)
                    page.locator('button:has-text("埋め込み")').click()
                    time.sleep(2)
                    url_input = page.locator('[placeholder="https://example.com"]')
                    url_input.click()
                    time.sleep(0.5)
                    page.keyboard.type(url)
                    time.sleep(1)
                    page.locator('button:has-text("適用")').click()
                    time.sleep(5)
                    body.press("Enter")
                    time.sleep(0.5)

                print("    募集セクション完了")
            except Exception as e:
                print(f"    募集セクションエラー: {e}")

            print("    本文完了")

            # 公開に進む → ハッシュタグを追加 → 下書き保存に戻る
            try:
                page.locator('button:has-text("公開に進む")').click()
                time.sleep(5)

                tag_input = page.locator('[placeholder="ハッシュタグを追加する"]')

                # 共通タグ
                common_tags = ["社員インタビュー", "マーケティング", "広告", "ベンチャー", "キャリア"]

                # 記事内容からキーワードを抽出して追加タグを生成
                all_text = " ".join([s["heading"] for s in sections])
                all_text += " ".join([p["text"] for s in sections for p in s["paragraphs"]])

                content_tags = []
                keyword_map = {
                    "エンジニア": "エンジニア",
                    "デザイン": "デザイン",
                    "動画": "動画編集",
                    "映像": "映像制作",
                    "AI": "AI",
                    "営業": "営業",
                    "フリーランス": "フリーランス",
                    "新卒": "新卒",
                    "未経験": "未経験",
                    "成長": "成長",
                    "挑戦": "挑戦",
                }
                for keyword, tag in keyword_map.items():
                    if keyword in all_text and tag not in common_tags:
                        content_tags.append(tag)

                all_tags = common_tags + content_tags[:3]  # 最大8タグ

                for tag in all_tags:
                    tag_input.click()
                    time.sleep(0.3)
                    tag_input.fill(tag)
                    time.sleep(0.3)
                    page.keyboard.press("Enter")
                    time.sleep(0.5)

                print(f"    タグ: {', '.join(all_tags)}")

                # 閉じるで編集画面に戻る
                page.locator('button:has-text("閉じる")').first.click()
                time.sleep(3)
            except Exception as e:
                print(f"    タグ追加エラー: {e}")

            # 下書き保存
            time.sleep(2)
            page.locator('button:has-text("下書き保存")').click()
            time.sleep(3)

            context.close()

        print(f"  note投稿完了: {title[:40]}")
        return True

    except Exception as e:
        print(f"  noteエラー: {e}")
        return False


def migrate_articles(article_ids: list[dict]):
    """複数記事をWantedlyからnoteに一括移行する"""
    print("=" * 60)
    print(f"  Wantedly → note 一括移行（{len(article_ids)}本）")
    print("=" * 60)

    with sync_playwright() as pw:
        context = _get_browser_context(pw)
        page = context.new_page()

        for i, item in enumerate(article_ids):
            print(f"\n[{i+1}/{len(article_ids)}] {item['title'][:50]}")

            # Wantedlyから記事抽出
            article = extract_wantedly_article(page, item["id"])
            print(f"  セクション: {len(article['sections'])}個")

            context.close()

            # noteに投稿
            publish_to_note_from_wantedly(article)

            # 次の記事のためにブラウザを再起動
            if i < len(article_ids) - 1:
                context = _get_browser_context(pw)
                page = context.new_page()
                time.sleep(2)


if __name__ == "__main__":
    # vol.15〜23を移行
    articles_to_migrate = [
        {"id": "994364", "title": "社員インタビューvol.15"},
        {"id": "999730", "title": "社員インタビューvol.16"},
        {"id": "1001162", "title": "社員インタビューvol.17"},
        {"id": "1001091", "title": "社員インタビューvol.18"},
        {"id": "1008356", "title": "社員インタビューvol.19"},
        {"id": "1009888", "title": "社員インタビューvol.20"},
        {"id": "1011834", "title": "社員インタビューvol.21"},
        {"id": "1040964", "title": "社員インタビューvol.22"},
        {"id": "1054288", "title": "社員インタビューvol.23"},
    ]

    migrate_articles(articles_to_migrate)
