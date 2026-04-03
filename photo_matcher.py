"""写真とセクションの自動マッチング（Claude Vision API使用）"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import anthropic
import config


def _encode_image(image_path: Path) -> tuple[str, str]:
    """画像をbase64エンコードする"""
    suffix = image_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/jpeg")
    data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    return data, media_type


def match_photos_to_sections(
    sections: list[dict],
    image_paths: list[Path],
    cover_image: Path,
) -> list[Optional[Path]]:
    """各セクションに最適な写真を割り当てる

    Returns:
        セクション数と同じ長さのリスト。各要素は割り当てられた画像パス or None
    """
    # カバー以外の本文用画像
    body_images = [p for p in image_paths if p != cover_image]

    if not body_images or not sections:
        return [None] * len(sections)

    # セクション情報を整理
    section_descriptions = []
    for i, s in enumerate(sections):
        desc = f"セクション{i+1}: 「{s['heading']}」\n"
        for p in s["paragraphs"][:3]:
            desc += f"  {p['text'][:100]}\n"
        section_descriptions.append(desc)

    # Claude APIに画像とセクション情報を送って最適な配置を判断
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # メッセージを構築
    content = []

    # 画像を添付
    for i, img_path in enumerate(body_images):
        data, media_type = _encode_image(img_path)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        })
        content.append({
            "type": "text",
            "text": f"↑ 画像{i+1}: {img_path.name}",
        })

    # プロンプト
    sections_text = "\n".join(section_descriptions)
    content.append({
        "type": "text",
        "text": f"""あなたはWantedlyの社員インタビュー記事の編集者です。
以下のセクションに、上記の画像を最適に配置してください。

【セクション一覧】
{sections_text}

【ルール】
- 各画像は最大1回だけ使用できます
- 全ての画像を使い切る必要はありません（4枚程度が理想）
- セクションの内容に合った画像を選んでください
  - 作業中の写真 → スキルや業務内容のセクション
  - 撮影/現場写真 → 挑戦や成長のセクション
  - ステージ/登壇写真 → 目標や将来のセクション
  - ポートレート写真 → 導入や自己紹介のセクション
- 画像がどのセクションにも合わない場合はスキップしてください
- 最後のセクション（締め/将来の話）にも画像があると良いです

【出力形式】
JSON配列で返してください。セクション番号（1始まり）をキー、画像ファイル名を値とします。
例: {{"1": "photo_a.jpg", "3": "photo_b.jpg", "5": "photo_c.jpg"}}

JSONのみを返してください。説明は不要です。""",
    })

    print("    写真配置を分析中（Claude Vision）...")

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": content}],
    )

    # レスポンスをパース
    response_text = message.content[0].text.strip()
    # JSON部分を抽出
    if "{" in response_text:
        json_str = response_text[response_text.index("{"):response_text.rindex("}") + 1]
        mapping = json.loads(json_str)
    else:
        mapping = {}

    print(f"    配置結果: {mapping}")

    # マッピングをリストに変換
    # ファイル名からPathへのルックアップ
    name_to_path = {p.name: p for p in body_images}

    result = []
    for i in range(len(sections)):
        section_num = str(i + 1)
        if section_num in mapping:
            img_name = mapping[section_num]
            result.append(name_to_path.get(img_name))
        else:
            result.append(None)

    return result
