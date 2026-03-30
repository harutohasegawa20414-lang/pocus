"""AI検証: 自動発見された店舗が実在のポーカー店舗かどうかを判定する（Gemini API）"""

import logging

import httpx

from tas.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
あなたはポーカー店舗の検証AIです。
与えられた情報から、これが日本国内に実在するポーカー店舗（アミューズメントポーカー含む）かどうかを判定してください。

## 承認すべきもの
- アミューズメントポーカー店舗（リアル店舗）
- ポーカーバー、ポーカールーム
- ポーカーが遊べるカジノバー（ポーカーがメインまたは主要）
- ポーカーサークルの活動拠点（固定の場所がある場合）

## 却下すべきもの
- オンラインポーカーサイト（GGPoker、PokerStars等）
- オンラインカジノ、ブックメーカー
- 記事ページ、まとめサイト、ランキングページ
- 閉店済みの店舗（明確に閉店と分かる場合のみ）
- ポーカーと無関係な店舗
- 架空・テスト用のデータ

## 回答形式
1行目に「APPROVE」または「REJECT」のみ記載。
2行目に判定理由を短く記載（50文字以内）。"""

_USER_TEMPLATE = """\
以下の情報を検証してください。

店舗名: {name}
URL: {url}
住所: {address}
エリア: {area}
営業時間: {hours}
料金: {price}
概要: {summary}"""


async def verify_venue(
    *,
    name: str,
    url: str,
    address: str = "",
    area: str = "",
    hours: str = "",
    price: str = "",
    summary: str = "",
) -> tuple[str, str]:
    """
    Gemini API で店舗を検証する。

    Returns:
        (visibility_status, reason)
        - ("visible", "理由") — 承認
        - ("hidden", "理由")  — 却下
        - ("pending_review", "理由") — API失敗時のフォールバック
    """
    if not settings.gemini_api_key:
        logger.warning("[AI VERIFY] GEMINI_API_KEY not set — skipping AI verification")
        return "pending_review", "API key not configured"

    user_msg = _USER_TEMPLATE.format(
        name=name,
        url=url,
        address=address or "不明",
        area=area or "不明",
        hours=hours or "不明",
        price=price or "不明",
        summary=(summary or "なし")[:500],
    )

    api_url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
        f"?key={settings.gemini_api_key}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                api_url,
                headers={"content-type": "application/json"},
                json={
                    "systemInstruction": {
                        "parts": [{"text": _SYSTEM_PROMPT}],
                    },
                    "contents": [
                        {"role": "user", "parts": [{"text": user_msg}]},
                    ],
                    "generationConfig": {
                        "maxOutputTokens": 150,
                        "temperature": 0.0,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text: str = (
            data["candidates"][0]["content"]["parts"][0]["text"].strip()
        )
        lines = text.split("\n", 1)
        decision = lines[0].strip().upper()
        reason = lines[1].strip() if len(lines) > 1 else ""

        if decision == "APPROVE":
            logger.info("[AI VERIFY] APPROVED: %s — %s", name[:60], reason[:100])
            return "visible", reason
        elif decision == "REJECT":
            logger.info("[AI VERIFY] REJECTED: %s — %s", name[:60], reason[:100])
            return "hidden", reason
        else:
            logger.warning("[AI VERIFY] unexpected response: %s", text[:200])
            return "pending_review", f"unexpected AI response: {text[:100]}"

    except httpx.HTTPStatusError as exc:
        logger.error(
            "[AI VERIFY] API error %d: %s",
            exc.response.status_code, str(exc)[:200],
        )
        return "pending_review", f"API error: {exc.response.status_code}"
    except Exception as exc:
        logger.error("[AI VERIFY] failed: %s", str(exc)[:200])
        return "pending_review", f"verification error: {str(exc)[:100]}"
