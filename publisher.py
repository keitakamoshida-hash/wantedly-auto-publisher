"""Playwright によるWantedly・noteへの下書き投稿（写真付き）"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, BrowserContext
import config


def _get_browser_context(pw) -> BrowserContext:
    """保存済みのログイン状態でブラウザを起動する"""
    config.BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    headless = os.environ.get("HEADLESS", "false").lower() == "true"
    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(config.BROWSER_DATA_DIR),
        headless=headless,
        locale="ja-JP",
    )
    return context


def _ensure_wantedly_login(page):
    """Wantedlyにログインしていなければ自動ログインする"""
    page.goto("https://www.wantedly.com/enterprise/dashboard", timeout=60000)
    time.sleep(5)

    # ログインページにリダイレクトされたらログインが必要
    if "signin" in page.url or "sign_in" in page.url or "login" in page.url:
        print("    Wantedly 自動ログイン中...")

        # メールアドレス入力してEnter
        email_input = page.locator('input[type="email"]')
        email_input.fill(config.WANTEDLY_EMAIL)
        email_input.press("Enter")
        time.sleep(5)

        # パスワード入力してEnter
        pass_input = page.locator('input[type="password"]')
        pass_input.fill(config.WANTEDLY_PASSWORD)
        pass_input.press("Enter")
        time.sleep(8)

        # ダッシュボードに遷移を確認
        page.goto("https://www.wantedly.com/enterprise/dashboard", timeout=60000)
        time.sleep(3)

        if "signin" not in page.url:
            print("    ログイン成功")
        else:
            print("    ログイン失敗 - 認証情報を確認してください")
    else:
        print("    Wantedly ログイン済み")


def login_interactive():
    """ブラウザを開いてWantedly・noteに手動ログインしてもらう"""
    print("\n=== ブラウザログイン ===")
    print("ブラウザが開きます。以下の手順でログインしてください:")
    print("  1. Wantedly にログイン")
    print("  2. note にログイン")
    print("  3. 両方ログインしたらブラウザを閉じてください\n")

    with sync_playwright() as pw:
        context = _get_browser_context(pw)
        page = context.new_page()

        # Wantedly のログインページを開く
        page.goto("https://www.wantedly.com/users/sign_in")
        print("Wantedly のログインページを開きました。ログインしてください。")
        print("ログインが完了したら、noteのログインに進みます。")

        # ユーザーがログインするのを待つ
        try:
            page.wait_for_url("**/dashboard**", timeout=300_000)
        except Exception:
            pass

        # note のログインページを開く
        page2 = context.new_page()
        page2.goto("https://note.com/login")
        print("\nnote のログインページを開きました。ログインしてください。")
        print("両方のログインが完了したら、ブラウザを閉じてください。")

        # ブラウザが閉じられるまで待つ
        try:
            while len(context.pages) > 0:
                time.sleep(1)
        except Exception:
            pass

    print("\nログイン情報を保存しました。")


def _parse_article(article_text: str):
    """記事テキストをタイトル・導入文・目次・セクションに分解する

    原稿の構造:
      タイトル行
      導入文（こんにちは〜）
      導入文続き
      目次
      見出し1
      見出し2
      ...
      見出し1（2回目 = セクション開始）
      質問
      回答...
      見出し2（2回目 = セクション開始）
      ...
    """
    lines = article_text.strip().split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            stripped = stripped[3:].strip()
        elif stripped.startswith("# "):
            stripped = stripped[2:].strip()
        clean_lines.append(stripped)

    # 1. タイトル = 最初の行
    title = clean_lines[0]
    rest = clean_lines[1:]

    # 2. 「目次」の位置を探す
    toc_idx = -1
    for i, line in enumerate(rest):
        if line == "目次":
            toc_idx = i
            break

    # 3. 導入文 = タイトル後〜目次前
    intro_lines = rest[:toc_idx] if toc_idx >= 0 else []

    # 4. 目次項目を収集（目次の次の行から、同じテキストが2回目に出るまで）
    toc_lines = []
    if toc_idx >= 0:
        after_toc = rest[toc_idx + 1:]
        seen = set()
        for line in after_toc:
            if line in seen:
                break  # 2回目に出現 = 本文開始
            seen.add(line)
            toc_lines.append(line)

    # 5. 目次項目をセットにして、本文をセクション分割
    toc_set = set(toc_lines)
    sections = []
    current_section = None
    # 本文開始位置 = 目次項目の最初が2回目に現れる場所
    body_start = False

    for line in rest:
        if line == "目次":
            body_start = False
            continue

        # 目次項目が2回目に出たら本文開始
        if not body_start and line in toc_set:
            # 目次内の出現はスキップ
            if line == toc_lines[0] and not body_start:
                # 最初のtocアイテムかチェック
                # 目次リスト内ならスキップ、本文ならセクション開始
                if toc_lines and line == toc_lines[0]:
                    # toc_linesを消費していく
                    pass
            continue

    # やり直し: もっとシンプルに
    # 全行を走査し、各行の出現回数をカウント
    from collections import Counter
    line_counts = Counter(clean_lines[1:])  # タイトル除く

    # 2回出現する行 = 目次にもセクション見出しにもある = セクション見出し
    heading_candidates = [l for l in toc_lines if line_counts.get(l, 0) >= 2]

    sections = []
    current_section = None
    heading_set = set(heading_candidates)
    found_headings = set()
    past_intro = False

    for line in rest:
        if line == "目次":
            past_intro = True
            continue

        # 導入文
        if not past_intro:
            continue

        # セクション見出し（2回目の出現時にセクション開始）
        if line in heading_set:
            if line not in found_headings:
                # 1回目 = 目次内 → スキップ
                found_headings.add(line)
                continue
            else:
                # 2回目 = セクション見出し
                if current_section:
                    sections.append(current_section)
                current_section = {"heading": line, "paragraphs": []}
                continue

        # セクション内のパラグラフ
        if current_section is not None:
            # 各セクションの最初のパラグラフは質問（blockquote）として扱う
            is_first = len(current_section["paragraphs"]) == 0
            has_question_mark = "？" in line or "?" in line
            is_answer = "：" in line[:10]  # "名前：" パターンは回答

            if is_first and not is_answer:
                current_section["paragraphs"].append({"type": "question", "text": line})
            elif has_question_mark and not is_answer:
                current_section["paragraphs"].append({"type": "question", "text": line})
            else:
                current_section["paragraphs"].append({"type": "text", "text": line})

    if current_section:
        sections.append(current_section)

    # 最後のセクションの末尾に広告/募集文があれば分離する
    closing_lines = []
    if sections:
        last_section = sections[-1]
        paras = last_section["paragraphs"]
        # 末尾から「Senjin Holdings」や「話を聞きに行きたい」を含む段落を探す
        closing_start = None
        for j in range(len(paras) - 1, -1, -1):
            text = paras[j]["text"]
            if "Senjin Holdings" in text or "話を聞きに行きたい" in text or "ご応募" in text:
                closing_start = j
                break
        if closing_start is not None:
            closing_lines = [p["text"] for p in paras[closing_start:]]
            last_section["paragraphs"] = paras[:closing_start]

    return title, intro_lines, toc_lines, sections, closing_lines


def _insert_image_via_menu(page, body, img_path: Path):
    """空行にカーソルがある状態で、プラスボタン→Cameraで画像を挿入する"""
    try:
        # 空行にいることを確認（プラスボタンが見えるまで少し待つ）
        time.sleep(1)
        plus_btn = page.locator('[class*="wui-icon-Plus"]').first
        # プラスボタンが見えなければクリックで空行にフォーカス
        if not plus_btn.is_visible():
            body.press("Enter")
            time.sleep(1)

        plus_btn.click()
        time.sleep(1)
        with page.expect_file_chooser() as fc_info:
            page.locator('[class*="wui-icon-Camera"]').first.click()
        file_chooser = fc_info.value
        file_chooser.set_files(str(img_path))
        print(f"    本文画像: {img_path.name}")
        time.sleep(4)
    except Exception as e:
        print(f"    画像挿入エラー ({img_path.name}): {e}")


def _insert_toc_via_menu(page):
    """プラスボタン→Listで目次を挿入する"""
    try:
        plus_btn = page.locator('[class*="wui-icon-Plus"]').first
        plus_btn.click()
        time.sleep(1)
        page.locator('[class*="wui-icon-List"]').first.click()
        print("    目次挿入完了")
        time.sleep(2)
    except Exception as e:
        print(f"    目次挿入エラー: {e}")


def _insert_separator_via_menu(page, body):
    """プラスボタン→Separatorで横線を挿入する"""
    try:
        time.sleep(0.5)
        plus_btn = page.locator('[class*="wui-icon-Plus"]').first
        if not plus_btn.is_visible():
            body.press("Enter")
            time.sleep(1)
        plus_btn.click()
        time.sleep(1)
        page.locator('[class*="wui-icon-Separator"]').first.click()
        print("    セパレーター挿入完了")
        time.sleep(2)
    except Exception as e:
        print(f"    セパレーター挿入エラー: {e}")


def _paste_text(page, text):
    """クリップボード経由でテキストを高速入力する"""
    page.evaluate("text => navigator.clipboard.writeText(text)", text)
    time.sleep(0.2)
    page.keyboard.press("Meta+v")
    time.sleep(0.3)


def publish_to_wantedly(article_md: str, image_paths: Optional[list[Path]] = None, recruitment_url: Optional[str] = None) -> bool:
    """Wantedly ストーリーに下書き投稿する（写真付き）

    参考記事の構造:
      カバー画像 → タイトル →
      <p> 導入文 → [目次（自動生成）] →
      <h2> 見出し → <画像> → <blockquote> 質問 → <p> 回答...
      (セクション繰り返し) → <p> 締め文

    エディタ操作:
      - "## テキスト" → H2見出しに自動変換
      - "> テキスト" → Blockquoteに自動変換
      - +ボタン → Camera → 画像挿入（空行が必要）
      - +ボタン → List → 目次挿入
    """
    title, intro_lines, toc_lines, sections, closing_lines = _parse_article(article_md)
    image_paths = image_paths or []
    cover_image = image_paths[0] if image_paths else None

    # Claude Visionで写真の最適配置を決定
    from photo_matcher import match_photos_to_sections
    section_images = match_photos_to_sections(sections, image_paths, cover_image)

    body_image_count = sum(1 for img in section_images if img is not None)
    print(f"  Wantedly に下書き投稿中: {title[:40]}...")
    print(f"    セクション数: {len(sections)}, 本文画像: {body_image_count}枚")

    try:
        with sync_playwright() as pw:
            context = _get_browser_context(pw)
            page = context.new_page()

            # ログイン確認
            _ensure_wantedly_login(page)

            # ストーリー作成ページを開く
            page.goto(
                "https://www.wantedly.com/manage_posts/articles/new?category=post_article&company_id=1744898&context=admin",
                timeout=60000,
            )
            time.sleep(5)

            # カバー画像をアップロード
            if image_paths:
                try:
                    cover_input = page.locator('input[type="file"][accept="image/*"]')
                    cover_input.set_input_files(str(image_paths[0]))
                    print(f"    カバー画像: {image_paths[0].name}")
                    time.sleep(3)
                except Exception as e:
                    print(f"    カバー画像アップロードエラー: {e}")

            # タイトル入力
            title_input = page.locator('textarea[placeholder="タイトル"]')
            title_input.click()
            title_input.fill(title)
            print(f"    タイトル: {title[:50]}")

            # 本文エディタにフォーカス
            body = page.locator('[contenteditable="true"][role="textbox"]')
            body.click()
            time.sleep(1)

            # --- 1. 導入文 ---
            for line in intro_lines:
                page.keyboard.type(line)
                body.press("Enter")
                time.sleep(0.3)
            print("    導入文入力完了")

            # --- 2. 目次を挿入（空行にカーソルがある今のうちに） ---
            _insert_toc_via_menu(page)
            body.press("Enter")
            time.sleep(0.5)

            # --- 3. 各セクション: 見出し → 空行(画像用) → 質問 → 回答 ---
            # 画像はセクション数に合わせてループ配分
            for i, section in enumerate(sections):
                # H2見出し（"## " でMarkdown変換）
                page.keyboard.type("## ")
                time.sleep(0.2)
                page.keyboard.type(section["heading"])
                body.press("Enter")
                time.sleep(0.5)

                # 画像挿入（このセクションに割り当てられた画像がある場合）
                if section_images[i] is not None:
                    _insert_image_via_menu(page, body, section_images[i])
                    body.press("Enter")
                    time.sleep(0.5)

                # 質問・回答を入力
                for para in section["paragraphs"]:
                    if para["type"] == "question":
                        page.keyboard.type("> ")
                        time.sleep(0.2)
                        page.keyboard.type(para["text"])
                    else:
                        page.keyboard.type(para["text"])
                    body.press("Enter")
                    time.sleep(0.1)

                body.press("Enter")
                time.sleep(0.3)

            # --- 締め文（募集記事リンク埋め込み + 募集文）---
            if closing_lines:
                # 募集記事リンクを埋め込み（セパレーター代わり）
                try:
                    time.sleep(0.5)
                    plus_btn = page.locator('[class*="wui-icon-Plus"]').first
                    if not plus_btn.is_visible():
                        body.press("Enter")
                        time.sleep(1)
                    plus_btn.click()
                    time.sleep(1)
                    page.locator('[class*="wui-icon-Link"]').first.click()
                    time.sleep(2)
                    recruit_link = recruitment_url or "https://www.wantedly.com/projects/2389407"
                    url_input = page.locator('input[placeholder="https://"]')
                    url_input.fill(recruit_link)
                    url_input.press("Enter")
                    print("    募集記事リンク埋め込み完了")
                    time.sleep(5)
                except Exception as e:
                    print(f"    募集記事リンクエラー: {e}")

                body.press("Enter")
                time.sleep(0.5)
                for line in closing_lines:
                    page.keyboard.type(line)
                    body.press("Enter")
                    time.sleep(0.1)
                print("    締め文入力完了")

            print("    本文入力完了")

            # 自動保存を待つ
            time.sleep(5)
            context.close()

        print("  Wantedly 下書き投稿完了（自動保存）")
        return True

    except Exception as e:
        print(f"  Wantedly 投稿エラー: {e}")
        print("  → output/ の記事ファイルから手動で投稿してください")
        return False


def publish_to_note(article_md: str, image_paths: Optional[list[Path]] = None) -> bool:
    """note に下書き投稿する（写真付き）"""
    title, body = _extract_title_and_body(article_md)
    image_paths = image_paths or []
    print(f"  note に下書き投稿中: {title[:30]}...")

    try:
        with sync_playwright() as pw:
            context = _get_browser_context(pw)
            page = context.new_page()

            # note 記事作成ページを開く
            page.goto("https://note.com/notes/new", wait_until="networkidle")
            time.sleep(2)

            # カバー画像をアップロード
            if image_paths:
                try:
                    cover_input = page.locator('input[type="file"]').first
                    cover_input.set_input_files(str(image_paths[0]))
                    print(f"    カバー画像: {image_paths[0].name}")
                    time.sleep(3)
                except Exception as e:
                    print(f"    カバー画像アップロードエラー: {e}")

            # タイトル入力
            title_input = page.locator(
                'textarea[placeholder*="タイトル"], '
                'textarea[placeholder*="記事タイトル"], '
                ".o-noteContentHeader__title textarea"
            ).first
            title_input.click()
            title_input.fill(title)

            # 本文入力
            body_input = page.locator(
                '[contenteditable="true"], '
                ".ProseMirror, "
                ".o-noteContentBody__editor"
            ).first
            body_input.click()

            for line in body.split("\n"):
                if line.strip():
                    body_input.type(line)
                body_input.press("Enter")

            time.sleep(1)

            # 下書き保存（note は自動保存されるが念のため）
            save_btn = page.locator(
                'button:has-text("下書き保存"), '
                'button:has-text("保存")'
            ).first
            try:
                save_btn.click(timeout=3000)
            except Exception:
                pass  # 自動保存の場合はボタンがない

            time.sleep(2)
            context.close()

        print("  note 下書き投稿完了")
        return True

    except Exception as e:
        print(f"  note 投稿エラー: {e}")
        print("  → output/ の記事ファイルから手動で投稿してください")
        return False
