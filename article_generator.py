"""Claude API による記事成形"""

from pathlib import Path
import markdown
import anthropic
import config


def _load_samples() -> str:
    """samples/ 内の参考記事をすべて読み込む"""
    samples = []
    for f in sorted(config.SAMPLES_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        samples.append(f"### 参考記事: {f.name}\n\n{text}")
    return "\n\n---\n\n".join(samples)


def _load_prompt_template() -> str:
    """プロンプトテンプレートを読み込む"""
    template_path = config.PROMPTS_DIR / "article.txt"
    return template_path.read_text(encoding="utf-8")


def _build_prompt(draft_text: str, vol_number: str = "XX", interviewee_name: str = "XX") -> str:
    """テンプレートに原稿と参考記事を埋め込む"""
    template = _load_prompt_template()
    samples = _load_samples()
    return template.format(
        sample_articles=samples,
        draft_article=draft_text,
        vol_number=vol_number,
        interviewee_name=interviewee_name,
    )


def generate_article(draft_text: str, vol_number: str = "XX", interviewee_name: str = "XX") -> str:
    """記事原稿からWantedlyスタイルの記事（Markdown）を生成する"""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = _build_prompt(draft_text, vol_number, interviewee_name)

    print("  記事を成形中...")

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    article_md = message.content[0].text
    print(f"  記事成形完了: {len(article_md)}文字")
    return article_md


def markdown_to_html(md_text: str) -> str:
    """Markdown を HTML に変換する"""
    html_body = markdown.markdown(md_text, extensions=["extra", "toc"])
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.8; color: #333; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
  h2 {{ margin-top: 2rem; color: #555; }}
  blockquote {{ border-left: 4px solid #ddd; margin-left: 0; padding-left: 1rem; color: #666; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""


def save_article(article_md: str, folder_name: str):
    """記事を Markdown と HTML で output/ に保存する"""
    from datetime import date

    today = date.today().strftime("%Y%m%d")
    base_name = f"{today}_{folder_name}"

    md_path = config.OUTPUT_DIR / f"{base_name}.md"
    html_path = config.OUTPUT_DIR / f"{base_name}.html"

    md_path.write_text(article_md, encoding="utf-8")
    html_path.write_text(markdown_to_html(article_md), encoding="utf-8")

    print(f"  保存完了: {md_path.name}, {html_path.name}")
    return md_path, html_path
