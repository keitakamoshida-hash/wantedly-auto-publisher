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

    Markdown形式の記事を解析する:
      # タイトル
      導入文
      ## 目次
      - 見出し1
      - 見出し2
      ## 見出し1
      本文...
      ## 見出し2
      本文...
    """
    lines = article_text.strip().split("\n")

    title = ""
    intro_lines = []
    toc_lines = []
    sections = []
    current_section = None
    phase = "start"  # start -> intro -> toc -> body

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # H1 = タイトル
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            phase = "intro"
            continue

        # H2 = 目次 or セクション見出し
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if heading == "目次":
                phase = "toc"
                continue
            else:
                # セクション見出し
                phase = "body"
                if current_section:
                    sections.append(current_section)
                current_section = {"heading": heading, "paragraphs": []}
                continue

        # 目次項目（- で始まる行）
        if phase == "toc":
            item = stripped.lstrip("- ").strip()
            if item:
                toc_lines.append(item)
            continue

        # 導入文
        if phase == "intro":
            intro_lines.append(stripped)
            continue

        # セクション内のパラグラフ
        if phase == "body" and current_section is not None:
            # **太字**で囲まれた行 = 質問候補
            is_bold = stripped.startswith("**") and stripped.endswith("**")
            # 各セクションの最初の太字質問のみquestionとする
            has_question_already = any(p["type"] == "question" for p in current_section["paragraphs"])

            if is_bold and not has_question_already:
                # 最初の太字 = メイン質問（小見出し）
                q_text = stripped.strip("*").strip()
                current_section["paragraphs"].append({"type": "question", "text": q_text})
            elif is_bold:
                # 2つ目以降の太字 = 通常テキスト（太字のまま）
                current_section["paragraphs"].append({"type": "text", "text": stripped})
            else:
                current_section["paragraphs"].append({"type": "text", "text": stripped})

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


def publish_to_wantedly(article_md: str, image_paths: Optional[list[Path]] = None, recruitment_url: Optional[str] = None, schedule_datetime: Optional[str] = None) -> bool:
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

            # --- 投稿予約（指定されている場合） ---
            if schedule_datetime:
                print(f"    投稿予約設定中: {schedule_datetime}")
                try:
                    # 公開設定へボタンをクリック
                    page.locator('button:has-text("公開設定へ")').click()
                    time.sleep(5)

                    # 「投稿を予約する」チェックボックスをクリック
                    schedule_btn = page.locator('text=投稿を予約する').locator("..").locator("button[role='checkbox']")
                    schedule_btn.scroll_into_view_if_needed()
                    time.sleep(1)
                    schedule_btn.click()
                    time.sleep(3)

                    # 日付を設定
                    # schedule_datetime = "2026-04-10 12:00" 形式
                    parts = schedule_datetime.split(" ")
                    date_str = parts[0]  # "2026-04-10"
                    time_parts = parts[1].split(":") if len(parts) > 1 else ["12", "00"]
                    hour = time_parts[0]
                    minute = time_parts[1] if len(time_parts) > 1 else "00"

                    # 日付入力
                    date_input = page.locator('input[type="date"]')
                    date_input.fill(date_str)
                    time.sleep(1)

                    # 時間・分のドロップダウン
                    selects = page.locator('select, [class*="DropDownSelect"]')
                    select_count = selects.count()
                    if select_count >= 2:
                        # 時間
                        selects.nth(0).select_option(hour)
                        time.sleep(0.5)
                        # 分
                        selects.nth(1).select_option(minute)
                        time.sleep(0.5)

                    # 「投稿を予約」ボタンをクリック
                    reserve_btn = page.locator('button:has-text("投稿を予約")')
                    reserve_btn.click()
                    time.sleep(3)

                    print(f"    投稿予約完了: {schedule_datetime}")
                except Exception as e:
                    print(f"    投稿予約エラー: {e}")
                    print("    下書きとして保存されています")

            context.close()

        print("  Wantedly 下書き投稿完了（自動保存）")
        return True

    except Exception as e:
        print(f"  Wantedly 投稿エラー: {e}")
        print("  → output/ の記事ファイルから手動で投稿してください")
        return False


def _ensure_note_login(page):
    """noteにログインしていなければ自動ログインする"""
    page.goto("https://note.com/dashboard", timeout=60000)
    time.sleep(5)

    if "login" in page.url:
        print("    note 自動ログイン中...")
        email_input = page.locator('input[placeholder*="mail"]')
        email_input.fill(config.NOTE_EMAIL)
        time.sleep(0.5)

        pass_input = page.locator('input[type="password"]')
        pass_input.fill(config.NOTE_PASSWORD)
        time.sleep(0.5)

        page.locator('button:has-text("ログイン")').click()
        time.sleep(8)

        if "login" not in page.url:
            print("    ログイン成功")
        else:
            print("    ログイン失敗")
    else:
        print("    note ログイン済み")


def _note_insert_image(page, body, img_path: Path):
    """noteエディタで画像を挿入する（メニュー→画像→file input）"""
    try:
        page.locator('[aria-label="メニューを開く"]').click()
        time.sleep(1)
        page.locator('button:has-text("画像")').click()
        time.sleep(2)

        file_input = page.locator('input[type="file"][accept*="image"]')
        file_input.set_input_files(str(img_path))
        print(f"    本文画像: {img_path.name}")
        time.sleep(4)
    except Exception as e:
        print(f"    画像挿入エラー ({img_path.name}): {e}")


def publish_to_note(article_md: str, image_paths: Optional[list[Path]] = None, schedule_datetime: Optional[str] = None) -> bool:
    """note にテキスト記事を下書き投稿する（写真付き）

    noteエディタの操作:
      - "## テキスト" → H2見出しに自動変換
      - "> テキスト" → Blockquoteに自動変換
      - メニュー→画像 → file inputで画像挿入
      - メニュー→目次 → 目次挿入
    """
    title, intro_lines, toc_lines, sections, closing_lines = _parse_article(article_md)
    image_paths = image_paths or []
    cover_image = image_paths[0] if image_paths else None

    # Claude Visionで写真配置
    from photo_matcher import match_photos_to_sections
    section_images = match_photos_to_sections(sections, image_paths, cover_image)

    print(f"  note に下書き投稿中: {title[:40]}...")

    try:
        with sync_playwright() as pw:
            context = _get_browser_context(pw)
            page = context.new_page()

            # ログイン確認
            _ensure_note_login(page)

            # 新規記事作成ページ
            page.goto("https://editor.note.com/new", timeout=60000)
            time.sleep(5)

            # タイトル入力
            title_input = page.locator('[placeholder="記事タイトル"]')
            title_input.fill(title)
            print(f"    タイトル: {title[:50]}")

            # 本文エディタにフォーカス
            body = page.locator('.ProseMirror[role="textbox"]')
            body.click()
            time.sleep(1)

            # --- 1. 導入文 ---
            for line in intro_lines:
                page.keyboard.type(line)
                body.press("Enter")
                time.sleep(0.3)
            print("    導入文入力完了")

            # --- 2. 目次を挿入（空行にカーソルがある状態で） ---
            try:
                page.locator('[aria-label="メニューを開く"]').click()
                time.sleep(1)
                page.locator('button:has-text("目次")').click()
                time.sleep(2)
                page.keyboard.press("ArrowDown")
                body.press("Enter")
                time.sleep(0.5)
                print("    目次挿入完了")
            except Exception as e:
                print(f"    目次挿入エラー: {e}")

            # --- 3. 各セクション ---
            for i, section in enumerate(sections):
                # H2見出し（メニューから「大見出し」を選択）
                page.locator('[aria-label="メニューを開く"]').click()
                time.sleep(1)
                page.locator('button:has-text("大見出し")').click()
                time.sleep(0.5)
                page.keyboard.type(section["heading"])
                body.press("Enter")
                time.sleep(0.5)

                # 画像挿入（割り当てられたセクションのみ）
                if section_images[i] is not None:
                    _note_insert_image(page, body, section_images[i])
                    body.press("Enter")
                    time.sleep(1)

                # 質問・回答
                for para in section["paragraphs"]:
                    if para["type"] == "question":
                        # 質問を小見出し（メニューから）で表示
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

            # --- 4. 締め文 ---
            if closing_lines:
                try:
                    page.locator('[aria-label="メニューを開く"]').click()
                    time.sleep(1)
                    page.locator('button:has-text("区切り線")').click()
                    time.sleep(1)
                    body.press("Enter")
                    time.sleep(0.5)
                except Exception:
                    pass

                for line in closing_lines:
                    page.keyboard.type(line)
                    body.press("Enter")
                    time.sleep(0.1)
                print("    締め文入力完了")

            print("    本文入力完了")

            # 下書き保存
            time.sleep(2)
            page.locator('button:has-text("下書き保存")').click()
            time.sleep(3)

            context.close()

        print("  note 下書き投稿完了")
        return True

    except Exception as e:
        print(f"  note 投稿エラー: {e}")
        print("  → output/ の記事ファイルから手動で投稿してください")
        return False
