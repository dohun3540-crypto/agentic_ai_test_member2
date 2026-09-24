# Tool Reliability-Aware Agentic AI Experiment

이 프로젝트는 **시간에 따라 Tool 성능이 변하는 환경**에서 Agent가 각 Tool의 최근 성공/실패 이력을 **신뢰도 점수(Reliability Score)** 로 기억하고, Reliability-aware Router가 그 정보를 Tool 선택에 사용했을 때 Reliability를 선택에 사용하지 않는 Baseline보다 동적 환경 변화에 더 잘 적응할 수 있는지 검증하는 Agentic AI 실험 프로젝트이다.

> 이 README는 현재 통합 코드가 존재하는 **integration/member3-routing-evaluation 브랜치**를 기준으로 작성되었다. 현재 default main 브랜치는 아직 통합 전 코드이므로, 통합 실험을 재현할 때는 이 브랜치를 기준으로 확인해야 한다.

---

## 1. 연구 질문

핵심 연구 질문은 다음과 같다.

> **시간에 따라 Tool의 성능이 변하는 환경에서, 최근 Tool 사용 결과를 Reliability Memory로 기억하는 Agent가 Reliability를 Tool 선택에 사용하지 않는 Baseline보다 더 안정적으로 Tool을 선택할 수 있는가?**

보조적으로 다음도 확인한다.

- Tool A의 성능 저하를 Router가 얼마나 빨리 감지하는가?
- 성능이 다시 회복되었을 때 Tool A를 얼마나 빨리 재사용하는가?
- Reliability 기반 선택이 전체 Task 성공률과 실패 회피율에 어떤 차이를 만드는가?
- Exploration / Forced Probe / Hysteresis가 Tool 전환과 회복 감지에 어떤 역할을 하는가?

---

## 2. 역할별 구현 구조

| 역할 | 주요 위치 | 현재 구현 |
|---|---|---|
| 1번: Agent / Tool Environment | agent/, tools/ | Agent 실행 흐름, Tool 실행, ToolResult 생성, Tool A/B 확률 환경 |
| 2번: Tool Reliability Memory | reliability/ | Sliding Window, EWMA, Tool별 독립 Reliability 상태 관리 |
| 3번: Routing + Evaluation | routing/, evaluation/ | BaselineRouter, ReliabilityRouter, Exploration, Forced Probe, Hysteresis, 로그/지표 |
| 공동 통합 | main.py, config.py, models.py, tests/ | 실험 설정, 공통 데이터 구조, End-to-End 실행 및 검증 |

현재 통합에서는 1번의 실제 Tool 구현과 2번의 Reliability 구현을 유지하고, 3번의 Router/Evaluator를 연결한다.

---

## 3. 전체 Agent 실행 흐름

~~~text
TaskInput
   ↓
AgentCore.run_task()
   ↓
ReliabilityManager.get_all_scores()
   ↓
Router.select_tool()
   ↓
RoutingDecision
   ↓
Selected Tool
   ↓
ToolResult
   ↓
ReliabilityManager.update(result)
   ↓
Evaluator.log_step(...)
   ↓
Next Task
~~~

Agent는 **현재 Reliability snapshot**을 Router에 전달한다. Router는 Baseline 또는 Proposed 정책으로 Tool을 선택하고, Tool 실행 결과가 나온 뒤 ReliabilityManager가 성공/실패를 반영한다. 이 업데이트된 Reliability는 **다음 Task의 Tool 선택**에 사용된다.

따라서 이 구조는 Agentic AI의 반복 루프인 **Memory → Decision → Action → Observation → Update**를 단순한 시뮬레이션 형태로 구현한다.

중요하게도 Evaluator CSV에는 Tool 실행 후 갱신된 점수가 아니라, **해당 Task에서 Router가 실제 선택에 사용했던 update 이전 Reliability snapshot**이 기록된다.

---

## 4. Tool 환경

### Tool A: 시간에 따라 성능이 변하는 Tool

| Task 구간 | 성공확률 |
|---|---:|
| 1~25 | 0.95 |
| 26~50 | 0.60 |
| 51~75 | 0.20 |
| 76~100 | 0.95 |

Tool A는 초기에 매우 안정적이지만 Task 26부터 Tool B보다 낮은 성공확률로 떨어지고, Task 51~75에서는 심한 장애 상태를 가정한다. Task 76부터 다시 0.95로 회복한다.

### Tool B: 안정적인 대체 Tool

Tool B의 성공확률은 전체 Task에서 **0.80 고정**이다.

이 환경은 Agent가 단순히 평균적으로 좋은 Tool을 선택하는지가 아니라, **최근 상태 변화에 적응하여 Tool A를 피하고 다시 회복했을 때 재사용할 수 있는지**를 보기 위한 시뮬레이션이다.

---

## 5. 공식 실험 설정

현재 config.py 기준 설정은 다음과 같다.

| 설정 | 현재 값 | 의미 |
|---|---:|---|
| NUM_TASKS | 100 | 1 Run의 Task 수 |
| NUM_RUNS | 10 | 반복 Run 수 |
| RANDOM_SEED | 42 | 첫 Run의 기준 seed |
| RELIABILITY_METHOD | sliding_window | 공식 main 실험의 Reliability 방식 |
| WINDOW_SIZE | 10 | Sliding Window 최대 길이 |
| EWMA_ALPHA | 0.30 | EWMA 최근 관측 가중치 |
| INITIAL_RELIABILITY | 0.50 | Tool 초기 신뢰도 |
| EXPLORATION_RATE | 0.10 | 확률적 탐색 비율 |
| FORCED_PROBE_INTERVAL | 10 | 오랫동안 선택되지 않은 Tool 재확인 간격 |
| MIN_SWITCH_GAIN | 0.05 | Tool 전환에 필요한 최소 score 우위 |
| BASELINE_PREFERRED_TOOL | tool_a | 공식 Baseline 기본 선택 Tool |

공식 main 실험은 **Baseline 100 Task × 10 Run + Proposed 100 Task × 10 Run**을 실행한다.

---

## 6. Reliability 계산

ReliabilityManager는 Tool별 상태를 독립적으로 관리하며 다음 인터페이스를 제공한다.

- update(result)
- get_score(tool_name)
- get_all_scores()
- reset()

성공은 1.0, 실패는 0.0으로 변환하며 score는 항상 0.0~1.0 범위로 유지한다.

### Sliding Window

현재 공식 방식이다.

최근 N개의 성공/실패 결과 평균을 Reliability로 사용한다.

~~~text
R_t = 최근 N개 관측값의 평균
~~~

현재 WINDOW_SIZE는 10이다.

예를 들어 최근 관측이 다음과 같다면,

~~~text
[1, 1, 0, 1, 0]
~~~

Reliability는 0.6이다.

주의할 점은 initial score 0.5가 Sliding Window 안에 가상의 관측값으로 들어가는 것은 아니라는 점이다. 아직 선택되지 않은 Tool은 0.5를 유지하고, 처음 실제 결과가 들어온 Tool은 그 실제 history를 기준으로 score가 계산된다.

### EWMA

코드에서 지원되는 대체 방식이다.

~~~text
R_t = α x_t + (1 - α) R_(t-1)
~~~

현재 α는 0.30이며 초기 score는 0.50이다.

- 성공: x_t = 1
- 실패: x_t = 0

EWMA는 과거 상태를 연속적으로 유지하면서 최근 관측에 더 큰 가중치를 주는 방식이다.

ReliabilityManager는 현재 **cumulative, sliding_window, ewma 세 방식**을 지원한다.

### Cumulative

전체 관측 이력을 누적하여 성공 비율을 계산한다.

~~~text
R_t = 누적 성공 횟수 / 누적 실행 횟수
~~~

실행 이력이 없을 때는 INITIAL_RELIABILITY(기본 0.50)를 유지하고, 첫 실제 관측부터 누적 성공률로 갱신한다. Tool A/B의 success count와 total count는 서로 독립적으로 관리되며 reset() 시 모두 초기화된다.

---

## 7. Baseline vs Proposed

| 구분 | 공식 Baseline | Proposed |
|---|---|---|
| Router | BaselineRouter | ReliabilityRouter |
| Reliability 계산 | AgentCore 구조상 계속 업데이트됨 | 계속 업데이트됨 |
| Reliability를 Tool 선택에 사용 | **사용하지 않음** | **사용함** |
| 기본 선택 | tool_a 선호 | 높은 Reliability 우선 |
| Exploration | 없음 | 0.10 |
| Forced Probe | 없음 | 10 Task 간격 |
| Hysteresis | 없음 | MIN_SWITCH_GAIN = 0.05 |

### 공식 Baseline

BaselineRouter는 Reliability Score를 전달받더라도 **Tool 선택 결정에는 사용하지 않는다**.

현재 BASELINE_PREFERRED_TOOL이 tool_a이므로, tool_a가 candidate에 있는 정상 실험에서는 계속 tool_a를 선택한다.

따라서 Baseline에 대해 “Reliability를 계산하지 않는다”라고 설명하면 정확하지 않다. AgentCore는 동일한 ReliabilityManager를 연결하고 실행 결과를 계속 업데이트하지만, **BaselineRouter가 그 score를 선택 정책에 사용하지 않는 것**이 정확한 차이다.

### Proposed

ReliabilityRouter는 Tool별 Reliability를 실제 선택에 사용한다.

정상 선택에서는 score가 가장 높은 Tool을 우선하며, 추가로 Exploration / Forced Probe / Hysteresis를 적용한다.

---

## 8. ReliabilityRouter 정책

### Reliability-based selection

Exploration이나 Forced Probe가 발생하지 않는 경우 Reliability가 가장 높은 Tool을 후보로 선택한다.

### Epsilon Exploration

EXPLORATION_RATE = 0.10 확률로 현재 Reliability 최상위 Tool만 고집하지 않고 다른 Tool을 탐색한다.

Exploration 시에는 현재 선택 중인 Tool과 다른 Tool을 우선 후보로 사용한다.

### Forced Probe

FORCED_PROBE_INTERVAL = 10이다.

특정 Tool이 10 Task 이상 선택되지 않았다면 그 Tool을 강제로 다시 실행하여 **성능이 회복되었는지 확인**할 기회를 만든다.

Forced Probe도 RoutingDecision의 used_exploration = True로 기록된다.

### Hysteresis

현재 Tool과 최고 Reliability Tool의 score 차이가 MIN_SWITCH_GAIN = 0.05보다 작으면 기존 Tool을 유지한다.

즉 아주 작은 score 차이 때문에 Tool이 계속 바뀌는 현상을 줄이기 위한 정책이다.

---

## 9. Evaluation

Evaluator는 각 Task의 로그를 저장하고 다음 metric을 계산한다.

| Metric | 현재 계산 의미 |
|---|---|
| task_success_rate | 전체 Task 중 Tool 실행 성공 비율 |
| failure_avoidance_rate | 두 Tool의 실제 설정 성공확률이 다를 때, 더 높은 성공확률의 Tool을 선택한 비율 |
| detection_lag | Tool A가 Tool B보다 불리해진 시점 이후, exploration이 아닌 정상 선택으로 처음 Tool A를 피할 때까지의 Task 수 |
| recovery_lag | Tool A 회복 이후, exploration이 아닌 정상 선택으로 다시 Tool A를 선택할 때까지의 Task 수 |
| tool_switching_rate | 연속 Task 사이 selected_tool이 바뀐 비율 |
| retry_count | 현재 재시도 로직이 없어 항상 0 |
| token_count | 공식 알고리즘 Router는 LLM을 호출하지 않아 항상 0 |
| avg_latency_sec | ToolResult에 기록된 Tool 실행 latency 평균 |

### Detection / Recovery 기준

현재 ground truth에서 Tool A는 Task 26부터 0.60으로 떨어져 Tool B의 0.80보다 낮아진다. 따라서 **degradation 기준점은 Task 26**이다.

Tool A는 Task 76부터 0.95로 회복해 Tool B보다 다시 높아지므로 **recovery 기준점은 Task 76**이다.

Baseline은 계속 tool_a를 선택하므로 detection_lag와 recovery_lag가 정의되지 않아 null이 될 수 있다.

main.py가 여러 Run의 metric을 평균낼 때는 null이 아닌 값만 평균에 사용한다.

### Simulation Ground Truth 주의

failure_avoidance_rate, detection_lag, recovery_lag는 config.get_tool_success_probability()를 통해 **시뮬레이션의 실제 성공확률을 알고 있기 때문에 계산 가능한 metric**이다.

실제 production Agent에서는 Tool의 진짜 성공확률을 직접 알 수 없을 수 있으므로 이 지표를 그대로 사용할 수 있다고 가정하면 안 된다.

---

## 10. CSV 로그 형식

공식 통합 실험의 각 Run CSV는 다음 9개 컬럼을 사용한다.

| 컬럼 | 의미 |
|---|---|
| run_id | Run 번호 |
| task_id | Task 번호 |
| selected_tool | 선택한 Tool ID |
| tool_success | 성공 1 / 실패 0 |
| tool_a_reliability | Router 선택 시점의 Tool A Reliability |
| tool_b_reliability | Router 선택 시점의 Tool B Reliability |
| used_exploration | Exploration 또는 Forced Probe 사용 여부 |
| latency_sec | Tool 실행 latency |
| retry_count | 현재는 0 |

---

## 11. 설치

### 공식 알고리즘 실험

현재 공식 main.py, Reliability, Routing, Evaluation은 Python 표준 라이브러리만 사용한다.

코드에 Python 3.10 문법인 union type 표기 등이 사용되므로 **Python 3.10 이상**을 권장한다.

~~~bash
git clone https://github.com/dohun3540-crypto/agentic_ai_test_member2.git
cd agentic_ai_test_member2
git checkout main
cd tool_reliability_agent
~~~

공식 실험 실행 자체에는 별도 requirements.txt가 필요하지 않으며, 현재 저장소에도 requirements.txt는 없다.

pytest로 테스트하려면 pytest만 별도로 설치하면 된다.

~~~bash
pip install pytest
~~~

unittest만 사용할 경우 별도 테스트 패키지 설치가 필요 없다.

---

## 12. 빠른 실행

프로젝트의 tool_reliability_agent 폴더에서 실행한다.

### 1) 전체 자동 테스트

~~~bash
python -m unittest discover -s tests -v
~~~

pytest가 설치되어 있다면 다음도 가능하다.

~~~bash
pytest -q
~~~

현재 테스트 코드는 Cumulative 및 동일-sequence 공식 검증을 포함해 총 31개의 unittest-compatible 테스트 케이스를 포함한다.

### 2) Reliability Dry Run

~~~bash
python run_reliability_dryrun.py
~~~

이 스크립트는 AlwaysToolARouter로 Tool A를 고정 선택하여 Router 성능을 평가하는 것이 아니라 **AgentCore → Tool A → ToolResult → ReliabilityManager.update() 연결과 Reliability 추세**를 검증한다.

sliding_window와 ewma를 각각 100 Task씩 실행하고 총 200행을 reliability_dryrun_results.csv에 저장한다.

### 3) Baseline Dry Run

~~~bash
python run_baseline_dryrun.py
~~~

중요: 이 파일의 MockBaselineRouter는 random.choice()로 Tool을 선택한다.

따라서 이 스크립트는 **과거 1번 구현 검증용 provisional dry run**이며, 현재 공식 main.py에서 사용하는 BaselineRouter와 동일한 정책이 아니다.

공식 Baseline 비교 결과를 얻으려면 반드시 main.py를 실행해야 한다.

### 4) 공식 1+2+3 통합 실험

~~~bash
python main.py
~~~

이 명령 하나로 다음이 실행된다.

~~~text
각 Run 1~10
  ├─ 같은 run seed로 Baseline 100 Task
  └─ 같은 run seed로 Proposed 100 Task
       ↓
각 Run CSV 저장
       ↓
10 Run 평균 metric 계산
       ↓
results/integrated_summary.json 저장
~~~

---

## 13. Random Seed 정책

main.py는 Run별로 다음 seed를 사용한다.

~~~text
seed = RANDOM_SEED + run_id - 1
~~~

따라서 현재는 Run 1~10에 대해 42~51을 사용한다.

각 Run에서 Baseline 시작 직전과 Proposed 시작 직전에 동일한 seed로 random.seed(seed)를 다시 설정한다.

또한 ReliabilityRouter의 exploration RNG는 random.Random(seed)라는 별도 RNG를 사용한다. 이 때문에 Router의 탐색 난수가 Tool simulation의 전역 random stream을 불필요하게 소비하지 않는다.

이 구조의 목적은 Baseline과 Proposed를 가능한 한 동일한 난수 조건에서 비교하여 **Router 정책 차이의 영향**을 더 명확하게 보기 위함이다.

RANDOM_SEED를 바꾸면 개별 성공/실패 결과가 달라질 수 있으므로, 기존 결과와 직접 비교할 때는 seed 정책을 반드시 기록해야 한다.

---

## 14. 결과 파일

### 공식 main.py 실행 시 생성

~~~text
results/
├─ integrated_baseline_run_01.csv
├─ ...
├─ integrated_baseline_run_10.csv
├─ integrated_proposed_run_01.csv
├─ ...
├─ integrated_proposed_run_10.csv
└─ integrated_summary.json
~~~

현재 Git 저장소에는 **results/integrated_summary.json이 커밋되어 있고, per-run integrated CSV는 커밋되어 있지 않다.** python main.py를 실행하면 per-run CSV가 재생성된다.

또한 현재 main.py는 integrated_summary.json에 per_run 세부 metric까지 기록한다. 현재 커밋된 summary 파일은 compact 형태로 보관되어 있어, main.py를 다시 실행하면 파일 구조가 더 상세한 형태로 다시 생성될 수 있다.

### 별도 검증 결과

~~~text
baseline_provisional_results.csv
baseline_llm_dryrun.csv
baseline_llm_full.csv
reliability_dryrun_results.csv
~~~

baseline_provisional_results.csv와 LLM CSV는 공식 integrated Baseline/Proposed 결과와 구분해서 사용해야 한다.

---

## 15. 현재 커밋된 공식 통합 결과

현재 results/integrated_summary.json에 기록된 10-Run 평균은 다음과 같다.

| Metric | Baseline | Proposed |
|---|---:|---:|
| task_success_rate | 0.673 | 0.777 |
| failure_avoidance_rate | 0.500 | 0.570 |
| detection_lag | N/A | 3.9 |
| recovery_lag | N/A | 15.0 |
| tool_switching_rate | 0.000 | 0.265 |
| retry_count | 0.0 | 0.0 |
| token_count | 0.0 | 0.0 |
| avg_latency_sec | 0.0 | 0.0 |

이 결과는 현재 설정된 확률 기반 Tool 환경, seed 42~51, sliding_window, 현재 Router 정책에서 생성된 **simulation 결과**이다.

avg_latency_sec가 0.0으로 보이는 것은 SimulatedToolA/B가 매우 짧은 wall-clock 실행 시간을 측정한 뒤 소수점 4자리로 반올림하기 때문이다.

---

## 16. 결과 해석 방법

현재 환경을 기준으로 Proposed가 의도대로 적응한다면 다음과 같은 흐름을 기대할 수 있다.

~~~text
Task 1~25
Tool A = 0.95, Tool B = 0.80
→ Tool A가 ground truth상 우세

Task 26~50
Tool A = 0.60, Tool B = 0.80
→ Tool A Reliability가 떨어지기 시작
→ Router가 Tool B로 전환할 근거가 생김

Task 51~75
Tool A = 0.20, Tool B = 0.80
→ Tool B 선택이 더 중요해지는 심한 성능 저하 구간

Task 76~100
Tool A = 0.95, Tool B = 0.80
→ Exploration / Forced Probe로 Tool A 회복을 관측할 기회 확보
→ Reliability 회복 후 Tool A 재사용 가능
~~~

다만 Tool 성공/실패 자체가 확률적으로 샘플링되므로 한 Run의 모든 Task가 이 패턴을 완벽하게 따르지는 않는다.

따라서 한 번의 실행보다 **여러 Run 평균과 구간별 선택 변화**를 함께 보는 것이 중요하다.

---

## 17. 실험 설정 변경

주요 실험 parameter는 config.py에서 관리한다.

변경 가능한 핵심 항목은 Tool A 성공확률 schedule, Tool B 성공률, NUM_TASKS, NUM_RUNS, RANDOM_SEED, RELIABILITY_METHOD, WINDOW_SIZE, EWMA_ALPHA, INITIAL_RELIABILITY, EXPLORATION_RATE, FORCED_PROBE_INTERVAL, MIN_SWITCH_GAIN, BASELINE_PREFERRED_TOOL이다.

하나 이상의 parameter를 변경했다면 기존 integrated_summary.json과 동일한 조건의 실험이 아니다. 결과 파일명 또는 별도 디렉터리를 사용하여 **기존 공식 결과와 구분**하는 것을 권장한다.

특히 Tool 성공확률 schedule을 바꾸면 Evaluator가 ground truth에서 찾는 degradation/recovery 기준도 함께 변할 수 있다.

Reliability 방식을 ewma로 변경하려면 config.py의 RELIABILITY_METHOD를 ewma로 설정할 수 있지만, 현재 커밋된 공식 통합 결과는 sliding_window 기준이다.

---

## 18. LLM Router는 공식 실험이 아님

다음 파일은 공식 알고리즘 Baseline vs Proposed와 별도의 **백업/추가 프로토타입**이다.

~~~text
llm_router_prototype.py
run_baseline_llm.py
run_baseline_llm_full.py
~~~

llm_router_prototype.py는 smolagents의 LiteLLMModel과 로컬 Ollama endpoint를 사용하며 기본 모델 ID는 ollama_chat/qwen3:8b이다.

LLMBaselineRouter는 LLM에게 실제 Reliability를 주지 않고 모든 Tool score를 0.5로 가려서 선택하게 한다.

이 LLM 코드는 공식 main.py에서 import되지 않는다.

따라서 **Qwen, Ollama, smolagents를 설치하지 않아도 공식 알고리즘 기반 main.py 실험은 실행 가능**하다.

LLM 결과 CSV도 공식 integrated_summary.json과 혼합해서 해석하지 않는다.

---

## 19. 주의사항 및 한계

1. 현재 Tool 환경은 실제 외부 API 장애가 아니라 random.random() 기반의 확률 시뮬레이션이다.
2. Tool의 ground-truth 성공확률은 config.py에 미리 정의되어 있다.
3. failure_avoidance_rate, detection_lag, recovery_lag는 simulation ground truth를 알고 있기 때문에 계산 가능한 지표다.
4. 100 Task × 10 Run은 연구 prototype 수준의 설정이며 모든 환경에 일반화할 수 없다.
5. seed를 고정해 재현성을 높였지만 seed를 변경하면 개별 결과가 달라질 수 있다.
6. 한 Run보다 여러 Run 평균을 중심으로 비교하는 것이 적절하다.
7. 현재 성능 결과는 현재 Tool schedule, Reliability 방식, Router parameter 아래에서의 결과이며 실제 모든 Agent 시스템에서 동일한 결과를 보장하지 않는다.
8. retry_count는 현재 재시도 기능을 측정하는 지표가 아니라 구현상 0으로 고정되어 있다.
9. token_count도 공식 알고리즘 Router에서는 LLM을 호출하지 않으므로 0이다.
10. latency는 실제 네트워크/API latency가 아니라 로컬 시뮬레이터 함수 실행 시간이다.
11. run_baseline_dryrun.py의 random-choice Mock Baseline과 main.py의 공식 BaselineRouter를 혼동하면 안 된다.
12. 현재 default main 브랜치에는 1+2+3 통합 코드가 반영되어 있으므로 공식 재현은 main 기준으로 수행한다.

---

## 20. 코드를 수정할 때 지켜야 할 인터페이스

통합 구조를 유지하려면 다음 규칙을 지키는 것이 안전하다.

- Tool ID는 tool_a / tool_b 규칙을 유지한다.
- ToolResult.success는 bool을 유지한다.
- Reliability score는 0.0~1.0 범위를 유지한다.
- Router는 RoutingDecision을 반환한다.
- Router 공개 진입점은 select_tool()을 유지한다.
- Agent 공개 실행 함수는 AgentCore.run_task()를 유지한다.
- ReliabilityManager의 update / get_score / get_all_scores / reset 인터페이스를 유지한다.
- 공통 실험 parameter는 가능하면 config.py에서 관리한다.
- parameter 또는 seed를 변경했다면 결과에 변경 조건을 기록한다.
- 기존 결과 CSV/JSON을 새로운 조건의 결과로 덮어써서 혼동하지 않는다.

---

## 21. 프로젝트 구조

~~~text
agentic_ai_test_member2/
├─ README.md
├─ .gitignore
└─ tool_reliability_agent/
   ├─ main.py
   ├─ config.py
   ├─ models.py
   │
   ├─ agent/
   │  ├─ __init__.py
   │  └─ agent_core.py
   │
   ├─ tools/
   │  ├─ __init__.py
   │  ├─ base_tool.py
   │  └─ simulated_tools.py
   │
   ├─ reliability/
   │  ├─ __init__.py
   │  └─ reliability_manager.py
   │
   ├─ routing/
   │  ├─ __init__.py
   │  └─ tool_router.py
   │
   ├─ evaluation/
   │  ├─ __init__.py
   │  └─ evaluator.py
   │
   ├─ tests/
   │  ├─ __init__.py
   │  ├─ test_reliability.py
   │  └─ test_integration.py
   │
   ├─ results/
   │  └─ integrated_summary.json
   │
   ├─ run_baseline_dryrun.py
   ├─ run_reliability_dryrun.py
   ├─ llm_router_prototype.py
   ├─ run_baseline_llm.py
   ├─ run_baseline_llm_full.py
   │
   ├─ baseline_provisional_results.csv
   ├─ baseline_llm_dryrun.csv
   ├─ baseline_llm_full.csv
   └─ reliability_dryrun_results.csv
~~~

---

## 22. 주요 파일 역할

| 파일 | 역할 |
|---|---|
| main.py | 공식 Baseline vs Proposed 1+2+3 통합 실험 실행 |
| config.py | Tool 환경, Reliability, Routing, 로그 설정 관리 |
| models.py | TaskInput, ToolResult, RoutingDecision 공통 데이터 구조 |
| agent/agent_core.py | Reliability 조회 → Routing → Tool 실행 → Reliability update → Evaluation 흐름 |
| tools/simulated_tools.py | Tool A 동적 성공률 / Tool B 고정 성공률 시뮬레이션 |
| reliability/reliability_manager.py | Cumulative / Sliding Window / EWMA Reliability Memory |
| routing/tool_router.py | ToolRouter, BaselineRouter, ReliabilityRouter |
| evaluation/evaluator.py | Task 로그, CSV 저장, metric 계산 |
| tests/test_reliability.py | ReliabilityManager 및 AgentCore 연결 테스트 |
| tests/test_integration.py | Routing, Evaluation, End-to-End 테스트 |
| results/integrated_summary.json | 현재 커밋된 공식 통합 결과 요약 |

---

## 23. 한 줄 요약

이 저장소의 공식 실험은 **“최근 Tool 성공/실패를 Reliability Memory로 저장하고 그 값을 Tool routing에 사용하면, 시간에 따라 Tool 상태가 바뀌는 환경에 더 잘 적응할 수 있는가?”**를 BaselineRouter와 ReliabilityRouter의 100 Task × 10 Run 비교로 검증한다.


---

## 24. Member 2 Reliability 비교 실험

9/25 일정 기준 Member 2 Tool Reliability 산출물은 공식 통합 실험과 분리된 다음 경로에서 재현한다.

~~~bash
python run_reliability_comparison.py
python plot_reliability_comparison.py
~~~

비교 조건은 다음과 같다.

| 조건 | 파라미터 |
|---|---|
| Cumulative | 전체 실행 이력 누적 |
| Sliding Window | window = 5, 10, 20 |
| EWMA | alpha = 0.1, 0.3, 0.5 |
| 공통 Router | exploration=0.10, forced probe=10, min switch gain=0.05 |
| 반복 | 각 조건 100 Task × 10 Run |
| Seed | 42~51, `RANDOM_SEED + run_id - 1` |

공식 `results/integrated_summary.json`은 덮어쓰지 않으며 새 결과는 다음 위치에 저장한다.

~~~text
results/reliability_comparison/
├─ baseline_reference/
├─ cumulative/
├─ sliding_w5/
├─ sliding_w10/
├─ sliding_w20/
├─ ewma_a01/
├─ ewma_a03/
├─ ewma_a05/
├─ summary.csv
├─ summary.json
└─ figures/
~~~

### 비교 실험 요약

| 조건 | Task Success | Failure Avoidance | Detection 성공률 | Detection Lag | Recovery 성공률 | Recovery Lag* | Switching |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0.673 | 0.500 | 0% | N/A | 0% | N/A | 0.000 |
| Cumulative | 0.774 | 0.546 | 100% | 8.1 | 40% | 9.0 | 0.242 |
| Sliding w5 | 0.791 | 0.617 | 100% | 4.0 | 50% | 15.2 | 0.260 |
| Sliding w10 | 0.777 | 0.570 | 100% | 3.9 | 10% | 15.0 | 0.265 |
| Sliding w20 | 0.780 | 0.562 | 100% | 6.9 | 30% | 14.0 | 0.254 |
| EWMA α=0.1 | 0.768 | 0.538 | 100% | 11.2 | 10% | 15.0 | 0.267 |
| EWMA α=0.3 | 0.788 | 0.639 | 100% | 3.5 | 70% | 11.57 | 0.288 |
| EWMA α=0.5 | 0.793 | 0.690 | 100% | 2.6 | 90% | 10.11 | 0.283 |

* Lag 평균은 해당 이벤트가 실제로 관측된 Run만 대상으로 계산한다. 따라서 반드시 `valid_detection_runs`, `valid_recovery_runs`, detection/recovery success rate와 함께 해석해야 한다. 예를 들어 Sliding w10의 Recovery Lag 15.0은 10 Run 전체 평균이 아니라 recovery가 관측된 1 Run의 값이다.

현재 설정에서는 EWMA α=0.5가 Task Success 0.793, Failure Avoidance 0.690, Detection 10/10 및 Recovery 9/10으로 가장 강한 적응 성능을 보였다. 다만 Tool A Reliability의 변동성도 가장 컸으므로, 이 선택은 **변화 감지와 회복 적응을 중시하는 현재 동적 Tool 환경**에 대한 결과이며 일반적인 최적값으로 해석하면 안 된다.

Cumulative는 평균 step 변화가 가장 작아 안정적이지만 오래된 이력의 영향으로 degradation 반응이 느렸다. Sliding Window는 작은 window일수록 추정값 변동성이 커지는 경향이 확인되었다. EWMA는 alpha가 커질수록 최근 결과에 더 민감해져 detection/recovery가 빨라졌지만 변동성도 증가했다.

### 그래프

`plot_reliability_comparison.py`는 다음 PNG를 생성한다.

- Tool A Reliability 방법별 변화
- Tool A 실제 성공확률 vs 추정 Reliability
- Detection / Recovery Lag
- Detection / Recovery Success Rate
- 방법별 Task Success Rate

그래프는 `results/reliability_comparison/figures/`에 저장된다. Matplotlib가 없는 환경에서는 `pip install matplotlib` 후 그래프 스크립트를 실행한다.

---

## 25. Member 2 재현 체크

아래 순서로 완료 상태를 검증할 수 있다.

~~~bash
python -m unittest discover -s tests -v
pytest -q
python main.py
python run_reliability_dryrun.py
python run_reliability_comparison.py
python plot_reliability_comparison.py
~~~

2026-09-24 검증에서는 31개 테스트가 모두 통과했고, 기존 공식 `main.py`의 Baseline 0.673 / Proposed 0.777이 동일 seed에서 그대로 재현되었다. Reliability 비교 실험은 Baseline 포함 8개 조건 × 10 Run × 100 Task = 총 80 Run / 8,000 Task를 실행한다.
