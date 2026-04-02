# 音声ファイル → 記事自動生成システム

## 概要

`input/` フォルダに音声ファイルを入れるだけで、自動的に文字起こし → 記事生成 → Wantedly・noteに下書き投稿まで行うツール。

## 使い方（利用者向け）

1. `input/` フォルダに音声ファイル（mp3, wav, m4a, mp4 等）を入れる
2. 自動で処理が走る（フォルダ監視）
3. 記事が生成され `output/` フォルダに保存される
4. Wantedlyストーリーとnoteに**下書き**として自動投稿される
5. 各サイトで下書きを確認・編集して公開する

※ 初回のみ `.env` ファイルにAPIキーの設定 + ブラウザログインが必要（セットアップ手順は下記）

## 技術スタック

- **言語**: Python 3.11+
- **文字起こし**: OpenAI Whisper API (`openai` SDK)
- **記事生成**: Claude API (`anthropic` SDK)
- **フォルダ監視**: `watchdog` ライブラリ
- **ブラウザ自動操作**: `playwright`（Wantedly・note への下書き投稿用）

## ディレクトリ構成

```
.
├── CLAUDE.md              # このファイル（プロジェクト設計）
├── requirements.txt       # 依存パッケージ
├── .env.example           # 環境変数テンプレート
├── .env                   # 環境変数（APIキー）※ git管理外
├── main.py                # エントリーポイント（フォルダ監視起動）
├── watcher.py             # input/ フォルダの監視
├── transcriber.py         # Whisper APIによる文字起こし
├── article_generator.py   # Claude APIによる記事生成
├── publisher.py           # Wantedly・note への下書き投稿（Playwright）
├── config.py              # 設定管理
├── prompts/
│   └── article.txt        # 記事生成用プロンプトテンプレート
├── samples/               # 参考記事（スタイル参照用）
│   ├── vol20_baba.md
│   └── vol21_kanazawa.md
├── input/                 # ★ ここに音声ファイルを入れる
│   └── done/              # 処理済みファイルの移動先
└── output/                # ★ ここに記事が出力される
```

## 処理フロー

```
1. main.py 起動 → input/ フォルダを監視開始
2. 音声ファイルが追加されたことを検知
3. Whisper API で文字起こし → テキスト取得
4. samples/ 内の参考記事を読み込み
5. Claude API に文字起こしテキスト + 参考記事スタイルを渡して記事生成
6. Markdown (.md) と HTML (.html) の両形式で output/ に保存
7. Playwright でブラウザを操作し、Wantedly・note に下書き投稿
8. 処理済みファイルは input/done/ に移動
```

## セットアップ手順

```bash
# 1. 依存パッケージをインストール
pip install -r requirements.txt

# 2. Playwright のブラウザをインストール
playwright install chromium

# 3. 環境変数を設定
cp .env.example .env
# .env を開いて API キーを記入

# 4. 初回のみ: ブラウザでWantedly・noteにログイン
python main.py --login
# → ブラウザが開くのでWantedlyとnoteにログインする
# → ログイン状態が保存され、次回以降は自動で使われる

# 5. 起動
python main.py
# → 「監視を開始しました。input/ に音声ファイルを入れてください」と表示される
```

## 環境変数

| 変数名 | 説明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API キー（Whisper用） |
| `ANTHROPIC_API_KEY` | Anthropic API キー（Claude用） |

## 自動投稿の仕様

### Wantedly ストーリー
- 「ストーリーを作成」画面を自動操作
- タイトル・本文を入力し**下書き保存**（公開はしない）
- 投稿先: Senjin Holdings の企業ページ

### note
- 「テキスト記事を作成」画面を自動操作
- タイトル・本文を入力し**下書き保存**（公開はしない）

### ログイン状態の管理
- 初回は `--login` オプションでブラウザを開き、手動ログイン
- ログインのCookie/セッションは `browser_data/` に保存
- セッション切れ時は再度 `--login` を実行

## 参考記事によるスタイル指定

`samples/` ディレクトリに Wantedly 掲載済みの社員インタビュー記事を配置済み。
デフォルトでは `samples/` 内の全 .md を読み込んでスタイルの参考にする。

### 記事スタイルの要点（samples/ の記事から抽出）

- **タイトル**: 「社員インタビューvol.XX｜サブタイトル」形式
- **冒頭**: 人事責任者・武智による導入文
- **目次**: セクション見出しのリスト
- **語り口**: 3人称ナラティブ + 本人発言の直接引用（「」）
- **構成**: 経歴 → 入社きっかけ → 苦労・転機 → 成長 → 目標 → 一緒に働きたい人
- **見出し**: ストーリー性のある印象的フレーズ
- **分量**: 1500〜2500文字

プロンプトテンプレートは `prompts/article.txt` に定義。

## 開発メモ

- Whisper APIの音声ファイルサイズ上限は **25MB**。超える場合は分割処理を検討
- Claude APIのモデルは `claude-sonnet-4-20250514` をデフォルトとする
- 出力ファイル名は `{日付}_{元ファイル名}.md / .html` 形式
- 処理完了後、入力ファイルは `input/done/` に移動（重複処理防止）
- 対象: Senjin Holdings の社員インタビュー記事（Wantedly掲載用 + note掲載用）
- Playwright のブラウザデータは `browser_data/` に保存（git管理外）
