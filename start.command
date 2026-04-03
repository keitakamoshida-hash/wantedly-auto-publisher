#!/bin/bash
# ==============================================
# Wantedly 記事自動投稿 - アプリ起動
# ダブルクリックで実行してください
# ==============================================

cd "$(dirname "$0")"

echo "============================================"
echo "  Wantedly 記事自動投稿 起動中..."
echo "============================================"
echo ""

# .env 存在確認
if [ ! -f .env ]; then
    echo "❌ セットアップが完了していません。"
    echo "   先に setup.command を実行してください。"
    read -p "Enterキーで終了..."
    exit 1
fi

# ポート確認（既に使用中なら停止）
if lsof -i:8080 > /dev/null 2>&1; then
    echo "⚠️  ポート8080が使用中です。既存プロセスを停止します..."
    kill $(lsof -t -i:8080) 2>/dev/null
    sleep 1
fi

echo "🚀 アプリを起動しています..."
echo ""
echo "  ブラウザで以下のURLにアクセスしてください:"
echo "  👉 http://localhost:8080"
echo ""
echo "  終了するには Ctrl+C を押してください"
echo ""

# ブラウザを自動で開く
sleep 2 && open http://localhost:8080 &

# Flask アプリ起動
python3 webapp.py
