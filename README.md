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
├─ reliability/                ← 2번 담당 (아직 비어있음)
├─ routing/                    ← 3번 담당 (아직 비어있음)
├─ evaluation/                 ← 3번 담당 (아직 비어있음)
├─ tests/                      ← 공동, 나중에 채움
│
├─ llm_router_prototype.py     ← 백업 프로토타입 (LLM이 Tool 고르는 Router, 확정 아님)
├─ run_baseline_dryrun.py      ← 검증용: 알고리즘 Mock Router, 100×10 실행 스크립트
├─ run_baseline_llm.py         ← 검증용: LLM Router, 소규모(10개) 실행 스크립트
├─ run_baseline_llm_full.py    ← 검증용: LLM Router, 100×10 전체 실행 스크립트 (타이머 포함)
│
├─ baseline_provisional_results.csv   ← 알고리즘 버전 결과 (1000행, 검증 완료)
├─ baseline_llm_dryrun.csv            ← LLM 버전 소규모(10개) 결과
├─ baseline_llm_full.csv              ← LLM 버전 100×10 결과 (진행 중/완료 시 갱신)
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
- [x] Reliability Score가 0.0~1.0 범위인가? (Mock 기준 확인 — 2번 실코드 완성 후 재확인 필요)
- [x] Router가 select_tool()을 지원하는가? (Mock 기준 확인 — 3번 실코드 완성 후 재확인 필요)
- [x] Router 반환값이 RoutingDecision인가? (Mock 기준 확인 — 3번 실코드 완성 후 재확인 필요)
- [x] Agent 실행 함수가 `run_task()`인가?
- [x] 평가 로그 컬럼명이 문서 기준과 동일한가? (9개 컬럼 일치)
- [x] 실험 파라미터가 `config.py`에서 관리되는가?
- [x] Random Seed로 재현 가능한가?
- [ ] `ReliabilityManager`가 `update()`/`get_score()`/`get_all_scores()`/`reset()` 지원 — **2번 완성 후 실제 연결 확인 필요**
- [ ] 전체 통합 파이프라인(`main.py`) — **9/22 통합 때 진행**

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
```
