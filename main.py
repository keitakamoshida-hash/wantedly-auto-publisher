"""
記事原稿 + 写真 → 記事自動成形・投稿システム

使い方:
  python main.py          # フォルダ監視を開始
  python main.py --login  # Wantedly・noteにログイン（初回のみ）
"""

import argparse
import sys
import config


def check_api_keys():
    """API キーが設定されているか確認"""
    if not config.ANTHROPIC_API_KEY:
        print("エラー: ANTHROPIC_API_KEY が .env に設定されていません。")
        print(f"\n.env.example を参考に .env ファイルを作成してください。")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="記事原稿と写真からWantedly・note記事を自動投稿するツール"
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Wantedly・noteにブラウザでログインする（初回のみ）",
    )
    args = parser.parse_args()

    if args.login:
        from publisher import login_interactive
        login_interactive()
        return

    check_api_keys()

    print("記事原稿 + 写真 → 自動成形・投稿システム")
    print("=" * 40)

    from watcher import start_watching
    start_watching()


if __name__ == "__main__":
    main()
