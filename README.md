# DeLTA_LAB_Agentic_AI

## 파일 구조

```text
tool_reliability_agent/
├─ main.py                    ← 공식 통합 파일 (아직 비어있음, 9/22 통합 때 3인이 같이 채움)
├─ config.py                  ← 공식 (실험 파라미터: NUM_TASKS, NUM_RUNS, RANDOM_SEED, Tool 성공률 스케줄 등)
├─ models.py                  ← 공식 (TaskInput, ToolResult, RoutingDecision 데이터클래스)
│
├─ agent/                     ← 1번 담당 (완료)
│   ├─ __init__.py
│   └─ agent_core.py          ← run_task() 구현
│
├─ tools/                     ← 1번 담당 (완료)
│   ├─ __init__.py
│   ├─ base_tool.py           ← BaseTool 추상 클래스
│   └─ simulated_tools.py     ← SimulatedToolA(95→60→20→95%), SimulatedToolB(80% 고정)
│
├─ reliability/               ← 2번 담당 (완료: ReliabilityManager, Sliding Window, EWMA)
├─ routing/                    ← 3번 담당 (아직 비어있음)
├─ evaluation/                 ← 3번 담당 (아직 비어있음)
├─ tests/                     ← 2번 Reliability 단위/AgentCore 연결 테스트 추가
│
├─ llm_router_prototype.py     ← 백업 프로토타입 (LLM이 Tool 고르는 Router, 확정 아님)
├─ run_baseline_dryrun.py      ← 검증용: 알고리즘 Mock Router, 100×10 실행 스크립트
├─ run_baseline_llm.py         ← 검증용: LLM Router, 소규모(10개) 실행 스크립트
├─ run_baseline_llm_full.py    ← 검증용: LLM Router, 100×10 전체 실행 스크립트 (타이머 포함)
├─ run_reliability_dryrun.py   ← 2번: Sliding Window/EWMA 동적 변화 검증
│
├─ baseline_provisional_results.csv   ← 알고리즘 버전 결과 (1000행, 검증 완료)
├─ baseline_llm_dryrun.csv            ← LLM 버전 소규모(10개) 결과
├─ baseline_llm_full.csv              ← LLM 버전 100×10 결과 (진행 중/완료 시 갱신)
├─ reliability_dryrun_results.csv     ← 2번 Reliability 검증 결과 (200행)
│
├─ .gitignore
└─ README.md
```

## 상태 요약

**완료 (공식 구조 — `models.py`, `config.py`, `agent/`, `tools/`)**
- 코드 통합 규격 v1 문서 인터페이스 그대로 구현
- Tool A(95→60→20→95% 스케줄), Tool B(80% 고정) 시뮬레이션
- Mock Reliability/Router로 단독 테스트 + 100×10(1000행) 실행 검증
- Tool A 구간별 실측 성공률(97.7 / 68.8 / 21.5 / 90.8%)이 설정값과 거의 일치 확인
- Random seed 고정 → 재현 가능
- 결과: `baseline_provisional_results.csv`

**진행 중 (백업 검증 — LLM 버전, 확정 아님)**
- Qwen3-8B, Ollama 4bit 양자화로 RTX5060(8GB)·RTX4060(8GB) 둘 다 실행 확인
- `LLMBaselineRouter`: task당 LLM 호출 1회, tool 이름만 출력하게 제한
- 소규모(10개) 테스트 완료 → `baseline_llm_dryrun.csv`
- 100×10 전체 실행 중 → 완료되면 `baseline_llm_full.csv` 갱신 예정

## 통합 직전 체크리스트 (문서 17번 기준)

- [x] Tool은 `run()`으로 실행되는가?
- [x] Tool은 `ToolResult`를 반환하는가?
- [x] `success` 필드는 bool 형식인가?
- [x] Tool ID가 `tool_a`/`tool_b`로 통일되어 있는가?
- [x] Reliability Score가 0.0~1.0 범위인가? (2번 실코드 및 자동 테스트로 확인)
- [x] Router가 select_tool()을 지원하는가? (Mock 기준 확인 — 3번 실코드 완성 후 재확인 필요)
- [x] Router 반환값이 RoutingDecision인가? (Mock 기준 확인 — 3번 실코드 완성 후 재확인 필요)
- [x] Agent 실행 함수가 `run_task()`인가?
- [x] 평가 로그 컬럼명이 문서 기준과 동일한가? (9개 컬럼 일치)
- [x] 실험 파라미터가 `config.py`에서 관리되는가?
- [x] Random Seed로 재현 가능한가?
- [x] `ReliabilityManager`가 `update()`/`get_score()`/`get_all_scores()`/`reset()` 지원 — **2번 실코드 및 AgentCore 연결 확인 완료**
- [ ] 전체 통합 파이프라인(`main.py`) — **3번 Router/Evaluation 완료 후 3인 통합 때 진행**

## 모델/방식 결정 사항 & 확인 필요

**결정하고 진행 중:**
- 코드 통합 규격 문서(LLM/Qwen/GPU 언급 0건) 기준, **Tool 선택은 알고리즘(Router) 기반을 메인으로 진행**
- 단, 팀원이 하드웨어(RTX 4060/5060, 8GB 4bit 양자화) 확인해준 것 참고해서, **Qwen3-8B + LLM Router 버전도 백업으로 병행 검증 중** (소규모 완료, 100×10 진행/완료)

**아직 확인 필요:**
- Baseline 실험(100×10)이 1번 몫인지, 3번 `BaselineRouter` 완성 후 통합해서 함께 도는 건지 — 문서마다 표현이 달라서(doc 24는 1번 몫, 코드 스펙은 `routing/` 폴더 소관) 팀 확정 필요


## 실행 방법

프로젝트 루트에서:
```bash
python run_baseline_dryrun.py      # 알고리즘 버전, 100×10
python run_baseline_llm.py         # LLM 버전, 소규모 10개
python run_baseline_llm_full.py    # LLM 버전, 100×10 (타이머 포함)
python run_reliability_dryrun.py   # 2번 Reliability, sliding_window + ewma 각 100개
```


## 2번 Reliability 구현 완료

`reliability/reliability_manager.py`에 `ReliabilityManager`를 구현했다. 기존 1번 담당자의 `AgentCore`는 수정하지 않았으며 다음 흐름으로 직접 연결된다.

```text
AgentCore.get_all_scores()
→ Router.select_tool(...)
→ selected_tool.run(task)
→ ReliabilityManager.update(result)
```

지원 인터페이스:
- `update(result)`
- `get_score(tool_name)`
- `get_all_scores()`
- `reset()`

기본 정책:
- Tool ID: `tool_a`, `tool_b`
- 초기 score: `0.5`
- 기본 method: `sliding_window`
- `WINDOW_SIZE = 10`
- `EWMA_ALPHA = 0.30`
- 점수는 항상 `0.0 <= score <= 1.0`
- `get_all_scores()`는 내부 상태와 분리된 새 dict 반환
- 알 수 없는 Tool ID는 오타를 숨기지 않도록 명확한 `ValueError` 발생
- 지원하지 않는 reliability method도 `ValueError` 발생

### Sliding Window

Tool별 독립 `deque(maxlen=WINDOW_SIZE)`에 성공=1, 실패=0을 저장하고 최근 window 평균으로 계산한다.

```text
R = 최근 window 내 성공값 합 / 현재 window 길이
```

### EWMA

초기값 `R_0 = 0.5`에서 아래 식을 사용한다.

```text
R_t = alpha * x_t + (1 - alpha) * R_(t-1)
```

기본 `alpha = 0.30`, 성공 `x_t = 1`, 실패 `x_t = 0`이다.

### 자동 테스트

```bash
cd tool_reliability_agent
pytest -q
# 또는
python -m unittest discover -s tests -v
```

실제 실행 결과: **13 passed**.

검증 범위는 초기 score, Sliding Window 성공/실패, window eviction, Tool A/B 독립성, score 범위, EWMA 수식(첫 성공 후 0.65), reset, get_all_scores 복사본, 잘못된 method/Tool ID 예외, 실제 AgentCore 연결을 포함한다.

### Reliability dry run

공식 3번 Router가 아직 없으므로 `run_reliability_dryrun.py`의 테스트 전용 `AlwaysToolARouter`로 Tool A를 고정 선택한다. Router 연구 목적이 아니라 `AgentCore → SimulatedToolA → ToolResult → ReliabilityManager.update()` 연결 검증 목적이다.

동일한 `RANDOM_SEED = 42`로 Sliding Window와 EWMA를 각각 100 Task 실행하고 `reliability_dryrun_results.csv`에 총 200행을 기록한다.

CSV 컬럼:
- `task_id`
- `tool_name`
- `success`
- `reliability_score`
- `reliability_method`

Seed 42 실제 결과의 구간별 평균 Reliability:

| Tool A 구간 | 설정 성공률 | Sliding Window 평균 R | EWMA 평균 R |
|---|---:|---:|---:|
| Task 1~25 | 95% | 0.996 | 0.941 |
| Task 26~50 | 60% | 0.596 | 0.594 |
| Task 51~75 | 20% | 0.260 | 0.189 |
| Task 76~100 | 95% | 0.764 | 0.819 |

두 방식 모두 **높음 → 감소 → 최저 → 회복** 추세가 확인되었다.

Reliability 코드 추가 후 기존 `run_baseline_dryrun.py`도 다시 실행하여 **1000행 정상 생성**을 확인했다. 기존 1번 담당 핵심 파일(`agent/agent_core.py`, `tools/*`, `models.py`)은 수정하지 않았다.
