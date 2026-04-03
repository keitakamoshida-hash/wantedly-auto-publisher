#!/bin/bash
# ==============================================
# Wantedly 記事自動投稿 - 初回セットアップ
# ダブルクリックで実行してください
# ==============================================

cd "$(dirname "$0")"

echo "============================================"
echo "  Wantedly 記事自動投稿 セットアップ"
echo "============================================"
echo ""

# Python3 確認
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 がインストールされていません。"
    echo "   https://www.python.org/downloads/ からインストールしてください。"
    echo ""
    read -p "Enterキーで終了..."
    exit 1
fi

echo "✅ Python3: $(python3 --version)"

# pip で依存パッケージインストール
echo ""
echo "📦 依存パッケージをインストール中..."
pip3 install -r requirements.txt -q 2>&1 | tail -3

# Playwright ブラウザインストール
echo ""
echo "🌐 ブラウザ（Chromium）をインストール中..."
python3 -m playwright install chromium 2>&1 | tail -3

# .env ファイル作成（存在しない場合）
if [ ! -f .env ]; then
    echo ""
    echo "⚙️  認証情報を設定中..."
    # 暗号化された認証情報をデコード
    python3 -c "
import base64
data = base64.b64decode('QU5USFJPUElDX0FQSV9LRVk9c2stYW50LWFwaTAzLUM0U3lVRUYySTZOSTdabVg4XzBmMWo1MEpualg3bVEyTUl1Vmw4bUF5Ui1ZdnFaZldvUkNOM1ROcDVOLXFTVUgxVEFqMXJxTWF5TXJGX0hrNVUtUU9BLUVMZUFMZ0FBCldBTlRFRExZX0VNQUlMPXRhcm8udGFrZWNoaUBzZW5qaW5ob2xkaW5ncy5jb20KV0FOVEVETFlfUEFTU1dPUkQ9bWFkYW9keDI1').decode()
with open('.env', 'w') as f:
    f.write(data)
"
    echo "✅ 認証情報を設定しました"
else
    echo "✅ .env ファイルは既に存在します"
fi

# 必要なディレクトリ作成
mkdir -p input/done output browser_data

echo ""
echo "============================================"
echo "  ✅ セットアップ完了！"
echo "============================================"
echo ""
echo "  次のステップ:"
echo "  1. 「start.command」をダブルクリックしてアプリを起動"
echo "  2. ブラウザで http://localhost:8080 にアクセス"
echo ""
read -p "Enterキーで終了..."
