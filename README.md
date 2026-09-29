# 생존형 수익 에이전트 (개인용)

Automaton(Web4)의 "벌지 못하면 죽는다" 구조를 개인 부업용으로 바꾼 버전.
매일 1주제를 정부지원사업 실무 자료에서 뽑아 **유튜브 쇼츠 · 인스타 릴스 · 블로그**로 발행하고, 수익은 디지털 상품 판매로 낸다.

- 수익·채널 설계: `수익구조_채널설계_v1_20260929.md`
- 첫 검토서: `AI자율수익에이전트_실현가능성검토_v2_20260929.md`

| 항목 | Automaton 원본 | 이 버전 |
|---|---|---|
| 돈 | 코인 지갑 | 원화 장부(시드 + 실제 입금 수익 − AI·음성 비용) |
| 죽음 | 잔고 0 → 정지 | 동일 |
| 생존 단계 | 4단계 | 정상(Opus 5.5) → 절약(Sonnet 5.5) → 위기(Haiku 4.5) → 사망 |
| 외부 발행 | AI 직접 | 채널별 전자동 스위치. 끄면 승인 요청 → `execute` 한 줄 |
| 품질 | 없음 | 편집장 심사(별도 AI 호출) 통과해야 영상 제작 |
| 개인정보 | 없음 | 원자료 자동 가림 + 발행 직전 재검사 |

---

## 1. 설치 (맥, 1회)

```bash
git clone <이 저장소> survival && cd survival
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...           # console.anthropic.com
python -m survival_agent init --seed 100000    # 시드 10만 원 ≈ 1개월
```

- ※ Anthropic 콘솔에서 **월 사용 한도를 시드와 같은 금액으로** 걸 것 (코드 장부와 별개의 2중 안전장치)
- ffmpeg 는 파이썬 패키지로 함께 설치됨(별도 설치 불필요)

## 2. 원자료·개인정보

```bash
mkdir -p data/sources
cp ~/정부지원_노하우/*.md data/sources/        # .md / .txt 만 (한글·PDF 는 텍스트로 변환)
echo "고객사명" >> data/redact_terms.txt        # 고객사·수강생 이름 등 한 줄에 하나
```

- 자동으로 가리는 것: 주민·법인번호, 사업자번호, 휴대전화·전화, 이메일, 계좌, 상세주소, 금지어
- 발행 직전 영상 문구·설명·캡션·블로그·사이트 전체를 한 번 더 검사하고 걸리면 발행 중단

## 3. 채널 연결 (한 번씩, 되는 것부터)

| 채널 | 준비 | 설정 |
|---|---|---|
| 자체 블로그 | GitHub 에 `아이디.github.io` 저장소 생성 | `site_repo_url`, `site_base_url` |
| 유튜브 | Google Cloud 프로젝트 → YouTube Data API 사용 설정 → OAuth 클라이언트(데스크톱) JSON 을 `data/youtube_client_secret.json` 으로 저장 → `python -m survival_agent youtube-auth` → **API 감사 신청**(통과 전 업로드는 비공개로 잠김) | — |
| 인스타 | 프로페셔널 계정 전환 → 페이스북 페이지 연결 → Meta 개발자 앱 → `instagram_content_publish` 토큰 | `ig_user_id`, 환경변수 `IG_ACCESS_TOKEN` |
| 음성(선택) | Google Cloud Text-to-Speech API 키 | 환경변수 `GOOGLE_TTS_API_KEY` (없으면 자막형 무음 영상) |

설정 파일: `data/config.json` — 전자동은 `"autopilot": {"youtube": true, "instagram": true, "site": true}`

## 4. 운영

```bash
python -m survival_agent run --once      # 하루 1사이클 (정상 단계 최대 3,000원)
python -m survival_agent status
python -m survival_agent queue           # 승인 요청·촬영 요청 보기 (시간 날 때만)
python -m survival_agent execute 5       # 준비된 발행을 한 줄로 실행
python -m survival_agent reject 6 --note "이 주제는 제외"
python -m survival_agent revenue 29000 "크몽 가이드 1건"   # 실제 입금 확인 후에만
```

- 매일 자동 실행(맥이 켜져 있을 때): `crontab -e` 에 아래 한 줄
  `45 8 * * * cd ~/survival && ANTHROPIC_API_KEY=... .venv/bin/python -m survival_agent run --once >> data/run.log 2>&1`
- 산출물: `workspace/videos`(영상) · `workspace/site/blog`(블로그) · `workspace/naver_drafts`(네이버 복사용) · `workspace/briefs`(기획안·심사 결과) · `workspace/생존일지.md`(에이전트 기억)

## 5. 생존 단계·비용

| 단계 | 모델 | 사이클 상한 | 간격 |
|---|---|---|---|
| 정상 (잔고 50% 이상) | Opus 5.5 | 3,000원 | 24시간 |
| 절약 (20∼50%) | Sonnet 5.5 | 1,500원 | 24시간 |
| 위기 (20% 미만) | Haiku 4.5 | 500원 | 48시간 |

단가(100만 토큰당): Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 4.5 $1/$5 · 웹검색 1회 $0.01 · 환율 1,400원 가정

## 6. 헌법 (system prompt 고정)

1. 한국 법령 준수: 스팸(「정보통신망법」), 가짜 후기·광고 미표기(「표시·광고의 공정화에 관한 법률」), 저작권 침해, 사칭 금지
2. 없는 실적·후기·인증 날조 금지 · 고객사 실적을 운영자 실적처럼 쓰지 않음
3. 코인·주식·예측시장 등 투기 금지
4. AI 제작 고지(설명란·캡션·블로그·유튜브 AI 표시 자동)
5. 개인정보 노출 금지

## 7. 테스트

```bash
python -m pytest -q    # API 키 없이 23개 시나리오 (실제 영상 렌더링·git 배포 포함)
```
