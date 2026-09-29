"""편집장 심사: 기획안(대본 포함)을 별도 호출로 냉정하게 채점한다. 통과해야 영상 제작 가능.

제작자와 심사자를 분리하는 이유: 같은 대화 안에서 스스로 매긴 점수는 후해지기 때문.
"""
from __future__ import annotations

import json

CRITERIA = {
    "demand": "수요 근거: 이 주제를 사람들이 실제로 찾는다는 확인된 사실(검색 결과, 비슷한 영상의 조회수, 커뮤니티 질문)이 제시됐는가. 추측뿐이면 1∼2점",
    "viewer": "시청자 명확성: 구체적인 시청자 한 명과 그 사람의 질문 한 개가 분명한가",
    "hook": "첫 3초 훅: 첫 장면 문구만 보고 멈춰서 볼 이유가 생기는가. 인사·자기소개·뻔한 제목은 1∼2점",
    "originality": "고유 정보: 구체적 수치·절차·사례가 있어 다른 영상과 구별되는가. 문구만 바꾼 템플릿형이면 1∼2점",
    "payoff": "끝까지 볼 이유: 약속한 것을 영상 안에서 실제로 주는가. '자세한 건 링크에서'로 미루면 감점",
    "product_fit": "상품 연결: 영상을 본 사람이 연결 상품·사이트로 넘어갈 이유가 자연스러운가",
}
PASS_MIN_EACH = 3
PASS_MIN_AVG = 3.5

SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {"type": "object",
                   "properties": {k: {"type": "integer"} for k in CRITERIA},
                   "required": list(CRITERIA), "additionalProperties": False},
        "feedback": {"type": "string", "description": "가장 점수가 낮은 항목부터, 무엇을 어떻게 고칠지 구체적으로"},
    },
    "required": ["scores", "feedback"],
    "additionalProperties": False,
}

SYSTEM = f"""너는 조회수로 평가받는 쇼츠 채널의 냉정한 편집장이다. 기획안을 1∼5점으로 채점한다.
3점 = 올려도 되는 수준, 5점 = 이 분야 상위 10% 영상 수준. 후하게 주지 마라. 애매하면 낮은 점수.
채점 기준:
{chr(10).join(f'- {k}: {v}' for k, v in CRITERIA.items())}
"""


def verdict(scores: dict) -> bool:
    vals = [scores[k] for k in CRITERIA]
    return min(vals) >= PASS_MIN_EACH and sum(vals) / len(vals) >= PASS_MIN_AVG


def review(client, model: str, effort: str | None, brief: dict):
    """반환: (결과 dict, response.usage, 실제 응답 모델)"""
    params = dict(
        model=model, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": "다음 기획안을 채점하라.\n\n" + json.dumps(brief, ensure_ascii=False, indent=1)}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if effort:
        params["output_config"]["effort"] = effort
    resp = client.messages.create(**params)
    if resp.stop_reason == "refusal":
        return {"passed": False, "scores": {}, "feedback": "심사 거절됨 — 주제를 바꿀 것"}, resp.usage, resp.model
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    data["scores"] = {k: max(1, min(5, int(data["scores"][k]))) for k in CRITERIA}
    data["passed"] = verdict(data["scores"])
    return data, resp.usage, resp.model
