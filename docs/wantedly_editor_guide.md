# Wantedlyストーリーエディタ 完全操作ガイド

> このドキュメントは、Wantedlyストーリーエディタの全機能をPlaywright自動化の観点からまとめたものです。
> 他のシステムへの移行時にも参照できるよう、汎用的に記述しています。

---

## 1. エディタの基本情報

- **エンジン**: Lexical（Meta製リッチテキストエディタフレームワーク）
- **特徴**:
  - Markdownショートカットによるブロック変換対応
  - ブロック挿入メニュー（+ボタン）による画像・目次・リンク等の挿入
  - 自動保存機能（明示的な保存操作不要）
  - H2見出しから目次を自動生成（後からH2を追加しても目次に自動反映される）

---

## 2. ページURL・セレクタ一覧

### 2.1 主要URL

| 用途 | URL |
|------|-----|
| ストーリー新規作成 | `https://www.wantedly.com/manage_posts/articles/new?category=post_article&company_id={COMPANY_ID}&context=admin` |
| ストーリー編集 | `https://www.wantedly.com/manage_posts/articles/{ARTICLE_ID}/edit` |
| ストーリー管理一覧 | `https://www.wantedly.com/manage_posts/list/companies/{COMPANY_SLUG}` |
| 企業ダッシュボード | `https://www.wantedly.com/enterprise/dashboard` |
| ログイン | `https://www.wantedly.com/signin_or_signup` |
| 募集一覧 | `https://www.wantedly.com/companies/{COMPANY_SLUG}/projects` |

> Senjin Holdings: company_id=`1744898`, slug=`senjinholdings`

### 2.2 エディタ内セレクタ

| 要素 | セレクタ | 備考 |
|------|---------|------|
| タイトル入力 | `textarea[placeholder="タイトル"]` | `fill()` で入力可能 |
| 本文エディタ | `[contenteditable="true"][role="textbox"]` | Lexicalエディタ本体 |
| カバー画像 file input | `input[type="file"][accept="image/*"]` | ページ内の1つ目 |
| +ボタン（ブロック挿入） | `[class*="wui-icon-Plus"]` | 空行にカーソルがある時のみ表示 |
| 公開設定ボタン | `button:has-text("公開設定へ")` | |
| H2見出し要素 | `h2.editor-heading-h2` | 本文内のH2を取得 |
| 段落要素 | `p.editor-paragraph` | 本文内の段落を取得 |

---

## 3. テキスト書式（Markdownショートカット）

エディタ内で特定のMarkdown記法を入力すると、自動的にリッチテキストブロックに変換される。

| 入力 | 変換結果 | 生成されるHTML | 用途 |
|------|---------|--------------|------|
| `## テキスト` + Enter | **見出し（H2）** | `<h2 class="editor-heading-h2"><strong>テキスト</strong></h2>` | セクション見出し |
| `> テキスト` + Enter | **引用（Blockquote）** | `<blockquote class="editor-quote"><strong>テキスト</strong></blockquote>` | インタビューの質問 |
| そのまま入力 + Enter | **通常段落** | `<p class="editor-paragraph">テキスト</p>` | 本文 |

### Playwrightでの入力方法

```python
body = page.locator('[contenteditable="true"][role="textbox"]')

# H2見出し
page.keyboard.type("## ")      # "## " まで入力すると変換準備
page.keyboard.type("見出し")    # 続けて見出しテキストを入力
body.press("Enter")             # 確定＋次の行へ

# 引用（Blockquote）
page.keyboard.type("> ")        # "> " まで入力すると変換準備
page.keyboard.type("質問文")    # 続けて質問テキストを入力
body.press("Enter")

# 通常段落
page.keyboard.type("本文テキスト")
body.press("Enter")
```

### 重要な注意点

- **`type()` を使うこと**: `fill()` ではMarkdownショートカットが発動しない
- **`"## "` のスペースが必要**: `"##テキスト"` では変換されない
- **`"> "` のスペースが必要**: `">テキスト"` では変換されない
- 変換は入力と同時にリアルタイムで行われる

---

## 4. ブロック挿入メニュー（+ボタン）

### 4.1 表示条件

+ボタンは**空行にカーソルがある時のみ**表示される。テキストが入力されている行では表示されない。

### 4.2 メニュー項目

+ボタンをクリックすると、以下のアイコンメニューが展開される:

| アイコン名 | 機能 | セレクタ | 説明 |
|-----------|------|---------|------|
| **List** | 目次（Table of Contents） | `[class*="wui-icon-List"]` | H2見出しから自動生成 |
| **Camera** | 画像挿入 | `[class*="wui-icon-Camera"]` | file_chooserダイアログが開く |
| **Link** | リンク/埋め込み | `[class*="wui-icon-Link"]` | URL入力欄が表示される |
| **Code** | コードブロック | `[class*="wui-icon-Code"]` | コードスニペット用 |
| **Separator** | 区切り線（水平線） | `[class*="wui-icon-Separator"]` | セクション間の区切り |

---

## 5. 各機能の詳細操作

### 5.1 カバー画像のアップロード

ページ上部のカバー画像エリアに画像をセットする。

```python
cover_input = page.locator('input[type="file"][accept="image/*"]')
cover_input.set_input_files(str(cover_image_path))
time.sleep(3)
```

### 5.2 目次（Table of Contents）の挿入

H2見出しから目次を自動生成するウィジェットを挿入する。

```python
# 前提: カーソルが空行にあること
page.locator('[class*="wui-icon-Plus"]').first.click()
time.sleep(1)
page.locator('[class*="wui-icon-List"]').first.click()
time.sleep(2)
```

**重要な発見事項:**
- 目次はH2見出しがまだ存在しない状態で挿入しても、**後からH2が追加されると自動的に目次に反映される**
- そのため、導入文の直後（セクション入力前）に目次を先に挿入して問題ない
- 目次のHTMLには `data-type="table-of-contents"` 属性が付与される

### 5.3 本文中への画像挿入

```python
# 前提: カーソルが空行にあること（+ボタンが見える状態）
page.locator('[class*="wui-icon-Plus"]').first.click()
time.sleep(1)

with page.expect_file_chooser() as fc_info:
    page.locator('[class*="wui-icon-Camera"]').first.click()
file_chooser = fc_info.value
file_chooser.set_files(str(image_path))
time.sleep(4)  # アップロード完了を待つ
```

**注意点:**
- +ボタンが見えない場合は `body.press("Enter")` で空行を作ってから実行
- 画像はWantedlyのサーバー（huntr-assets.s3.amazonaws.com）にアップロードされる
- アップロード後、`<img src="..." alt="Article content">` としてエディタに埋め込まれる
- `set_input_files()` ではなく `expect_file_chooser()` + `set_files()` を使う

### 5.4 リンク/募集記事カードの埋め込み

URLを入力すると、リッチなカード形式で埋め込まれる。Wantedlyの募集記事URLを入れると募集カードになる。

```python
# 前提: カーソルが空行にあること
page.locator('[class*="wui-icon-Plus"]').first.click()
time.sleep(1)
page.locator('[class*="wui-icon-Link"]').first.click()
time.sleep(2)

# URL入力欄に募集記事のURLを入力
url_input = page.locator('input[placeholder="https://"]')
url_input.fill("https://www.wantedly.com/projects/XXXXXXX")
url_input.press("Enter")
time.sleep(5)  # カード生成を待つ
```

**活用方法:**
- 社員インタビュー記事の末尾に募集記事カードを埋め込むことで、セパレーター兼CTAとして機能
- Wantedly内の任意のURL（募集記事、他のストーリー等）がカード表示される
- 外部URLも埋め込み可能（OGPカードとして表示）

### 5.5 区切り線（Separator）の挿入

```python
page.locator('[class*="wui-icon-Plus"]').first.click()
time.sleep(1)
page.locator('[class*="wui-icon-Separator"]').first.click()
time.sleep(1)
```

---

## 6. 社員インタビュー記事の完成構造

参考記事: https://www.wantedly.com/companies/senjinholdings/post_articles/1009888

```
[カバー画像]  ← Senjinロゴ前の写真（全記事共通）
[タイトル]    ← 「社員インタビューvol.XX｜サブタイトル」

<p>   導入文（こんにちは、Senjin Holdingsの人事責任者・武智です。）
<p>   導入文続き（〜語っていただきました。）

[目次]        ← +ボタン → List（H2から自動生成）

<h2>  セクション見出し1         ← "## " で入力
[画像]                           ← +ボタン → Camera
<blockquote> 質問               ← "> " で入力
<p>   回答段落（名前：〜）
<p>   回答段落（続き）

<h2>  セクション見出し2
[画像]
<blockquote> 質問
<p>   回答段落...

... セクション繰り返し（通常5セクション程度）...

[募集記事カード]  ← +ボタン → Link → 募集URL入力
<p>   締め文（Senjin Holdingsでは〜ご応募ください。）
```

### 写真配置ルール
- **カバー画像**: Senjinロゴ前のポートレート写真（全記事固定）
- **本文画像**: 4枚使用、各セクションの**見出し直後**に配置
- **写真選び**: セクション内容に合った写真を選ぶ
  - スキル・経歴系セクション → 作業風景の写真
  - 挑戦・苦労系セクション → アクティブな撮影/現場写真
  - 成長・変化系セクション → クリエイティブ空間の写真
  - 目標・未来系セクション → ステージ/登壇写真

### 記事入力順序（推奨フロー）

1. カバー画像アップロード
2. タイトル入力（`fill()` でOK）
3. 導入文入力（`type()` + Enter）
4. **目次挿入**（+ボタン → List）← H2の前でOK
5. 各セクションをループ:
   - H2見出し入力（`"## " + type()`）
   - 画像挿入（+ボタン → Camera）
   - 質問入力（`"> " + type()`）
   - 回答段落入力（`type()` + Enter）
6. 募集記事カード埋め込み（+ボタン → Link → URL）
7. 締め文入力
8. 自動保存を待つ（5秒程度）

---

## 7. ログイン

### 7.1 ログインURL
```
https://www.wantedly.com/signin_or_signup?redirect_to=https%3A%2F%2Fwww.wantedly.com%2Fenterprise%2Fdashboard
```

> 注意: `https://www.wantedly.com/users/sign_in` は404になる（2026年4月時点）

### 7.2 ログインフロー（2段階認証）

```
1. メールアドレス入力画面
   - input[type="email"] placeholder="youremail@example.com"
   - Enter で次へ

2. パスワード入力画面
   - input[type="password"] placeholder="パスワード"
   - Enter でログイン

3. ダッシュボードにリダイレクト
```

### 7.3 Playwright実装

```python
# 1. ダッシュボードにアクセス（未ログインならリダイレクト）
page.goto("https://www.wantedly.com/enterprise/dashboard", timeout=60000)
time.sleep(5)

# 2. ログイン必要か判定
if "signin" in page.url:
    # 3. メールアドレス入力
    page.locator('input[type="email"]').fill(email)
    page.locator('input[type="email"]').press("Enter")
    time.sleep(5)

    # 4. パスワード入力
    page.locator('input[type="password"]').fill(password)
    page.locator('input[type="password"]').press("Enter")
    time.sleep(8)

    # 5. ログイン成功確認
    page.goto("https://www.wantedly.com/enterprise/dashboard", timeout=60000)
    if "signin" not in page.url:
        print("ログイン成功")
```

### 7.4 セッション管理

- ログイン状態は `browser_data/` ディレクトリに保存される（Playwrightの persistent context）
- 一度ログインすれば、次回以降は自動的にログイン状態が維持される
- セッション切れ時は自動的に再ログインされる

---

## 8. 下書き管理

### 8.1 下書き一覧
```
https://www.wantedly.com/manage_posts/list/companies/{COMPANY_SLUG}
```

下書きカードには以下の情報が表示される:
- タイトル
- 作成者名
- 最終編集日
- カバー画像サムネイル

### 8.2 下書き削除

1. 下書きカードに**ホバー**する → ゴミ箱アイコンが表示される
2. ゴミ箱アイコンをクリック
3. 確認ダイアログで「削除」をクリック

```python
# Playwrightでの削除
draft_card = page.locator('a[href="/manage_posts/articles/{ARTICLE_ID}/edit"]')
draft_card.hover()
time.sleep(1)
# ゴミ箱ボタンをクリック（ホバーで表示される）
trash_btn = draft_card.locator("..").locator("button")  # 要調整
trash_btn.click()
time.sleep(1)
# 確認ダイアログ
page.locator('button:has-text("削除")').click()
```

### 8.3 自動保存

- エディタは自動保存機能あり
- 入力後5秒程度待てば自動的に下書きとして保存される
- 明示的な「下書き保存」ボタンは不要
- ブラウザを閉じても下書きは保持される

---

## 9. エディタHTML構造リファレンス

### 9.1 ブロック要素

| ブロック | HTMLタグ | クラス名 |
|---------|---------|---------|
| 通常段落 | `<p>` | `editor-paragraph` |
| H2見出し | `<h2>` | `editor-heading-h2` |
| 引用 | `<blockquote>` | `editor-quote` |
| 画像 | `<div>` → `<figure>` → `<img>` | `data-lexical-decorator` |
| 目次 | `<div>` | `data-type="table-of-contents"` |
| テキスト | `<span>` | `data-lexical-text="true"` |
| 太字 | `<strong>` | `editor-text-bold` |

### 9.2 画像のHTML構造
```html
<p class="editor-paragraph">
  <div data-lexical-decorator="true" contenteditable="false" style="display: contents;">
    <div class="sc-aXZVg kGRXWo">
      <figure class="sc-dAlyuH iSJXBW">
        <img src="https://huntr-assets.s3.amazonaws.com/users/{USER_ID}/{UUID}"
             alt="Article content" tabindex="0" class="sc-jlZhew MknbU">
      </figure>
    </div>
  </div>
</p>
```

### 9.3 目次のHTML構造
```html
<div data-type="table-of-contents"
     data-entries='[{"key":"10","text":"見出し1","tag":"h2"},{"key":"20","text":"見出し2","tag":"h2"}]'
     data-lexical-decorator="true" contenteditable="false">
  <!-- 内部にTableOfContentsBody コンポーネントが展開される -->
</div>
```

---

## 10. トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|--------|
| +ボタンが表示されない | カーソルがテキスト行にある | `body.press("Enter")` で空行を作る |
| Markdownショートカットが効かない | `fill()` を使っている | `type()` に変更する |
| 画像が挿入されない | `set_input_files()` を使っている | `expect_file_chooser()` + `set_files()` を使う |
| 目次が空 | H2見出しがない状態で挿入 | 問題なし（後からH2追加で自動反映） |
| ページ読み込みタイムアウト | `wait_until="networkidle"` を使用 | `timeout=60000` のみ指定し、`time.sleep()` で待つ |
| ログインページが404 | `/users/sign_in` は廃止済み | `/signin_or_signup` を使用 |
| 下書き削除ボタンが見つからない | クリックではなくホバーが必要 | カードに `hover()` してからボタンを探す |

---

## 11. 環境変数

| 変数名 | 説明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API キー（記事成形用） |
| `WANTEDLY_EMAIL` | Wantedlyログイン用メールアドレス |
| `WANTEDLY_PASSWORD` | Wantedlyログイン用パスワード |
