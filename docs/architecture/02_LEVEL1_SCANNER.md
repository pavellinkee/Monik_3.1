# MONIK — LEVEL 1 SCANNER

## 1. Назначение

Level 1 Scanner — быстрый слой первичного поиска потенциально прибыльных арбитражных возможностей.

Его задача:

- систематически проверять заданные tokens;
- использовать заданные amounts;
- получать актуальные quotes;
- сравнивать результаты между aggregators;
- быстро отбрасывать заведомо неприбыльные варианты;
- формировать Level 2 Jobs только для потенциально интересных opportunities.

Level 1 не является окончательным подтверждением прибыльности.

---

## 2. Главный принцип

Level 1 должен быть максимально быстрым и дешёвым по количеству внешних requests.

Он должен находить кандидатов, а не выполнять максимально глубокую проверку каждого возможного варианта.

---

## 3. Level 1 не является Profit Calculator

Level 1 не должен содержать собственную альтернативную реализацию profitability calculation.

Для предварительной оценки он может использовать normalized calculation logic, предоставленную Profit Calculator.

---

## 4. Level 1 не является Level 2

Level 1:

- обнаруживает;
- фильтрует;
- создаёт candidate opportunity.

Level 2:

- повторно получает необходимые данные;
- подтверждает актуальность;
- выполняет окончательный profitability calculation;
- принимает решение об уведомлении.

---

## 5. Input Configuration

Level 1 получает из Configuration:

- enabled networks;
- enabled aggregators;
- enabled tokens;
- configured amounts;
- routes;
- scan interval;
- scan policies.

Никакие из этих параметров не должны hard-code в scanner logic.

---

## 6. Token Universe

На текущем этапе используется:

**Top 30 tokens.**

Scanner работает только с токенами, разрешёнными Token Registry и configuration.

---

## 7. Token Registry

Level 1 получает token metadata из Token Registry.

Минимально необходимы:

- symbol;
- address;
- decimals;
- network;
- enabled;
- provider availability.

---

## 8. Network

Level 1 должен работать только с enabled networks.

Если token отсутствует или не поддерживается на конкретной network:

соответствующая комбинация не должна сканироваться.

---

## 9. Aggregators

Level 1 использует только enabled aggregators.

Минимально:

- 1inch;
- 0x;
- Velora;
- Uniswap.

---

## 10. Aggregator Adapter Boundary

Scanner не должен знать provider-specific API details.

Каждый aggregator вызывается через соответствующий Adapter.

---

## 11. Resource Manager

Все внешние requests Level 1 должны проходить через Resource Manager.

Scanner не должен напрямую выполнять HTTP/RPC requests.

---

## 12. Request Priority

Level 1 requests имеют более низкий priority, чем Level 2 confirmation requests.

Resource Manager должен иметь возможность ограничивать Level 1 requests при необходимости.

---

## 13. Routes

Level 1 работает только с утверждёнными fixed routes.

Scanner не должен самостоятельно генерировать произвольные multi-hop routes.

---

## 14. Route Representation

Каждый route должен явно определять:

- input token;
- output token;
- provider;
- network;
- operation;
- route sequence.

---

## 15. Arbitrage Comparison

Level 1 ищет ситуации, в которых:

- один provider предоставляет выгодный entry;
- другой provider предоставляет выгодный exit;
- итоговый результат потенциально превышает input после известных preliminary costs.

---

## 16. Direction

Каждая проверка должна иметь явное направление.

Например:

    USDC → TOKEN → USDC

и противоположное направление рассматривается отдельно, если оно разрешено configuration.

---

## 17. Provider Pair

Для сравнения providers Level 1 должен рассматривать разрешённые provider pairs.

Например:

- 1inch → 0x;
- 1inch → Velora;
- 0x → Velora;
- Velora → Uniswap.

Необходимо исключать:

- disabled providers;
- одинаковый provider для обеих сторон, если это запрещено policy.

---

## 18. Same Provider

Использование одного provider для обеих legs допускается только если это явно разрешено configuration.

По умолчанию cross-provider arbitrage является основной моделью.

---

## 19. Amounts

Level 1 должен проверять все configured amounts.

Например:

- amount A;
- amount B;
- amount C.

Каждая сумма является отдельным candidate context.

---

## 20. Amount Independence

Результат для одной суммы не должен автоматически применяться к другой сумме.

Quote и profitability зависят от конкретного amount.

---

## 21. Quote Request

Для каждой необходимой проверки Level 1 должен получать актуальный quote.

Не использовать старый quote вместо свежего, если policy требует актуальность.

---

## 22. Quote Normalization

Provider-specific responses должны быть преобразованы Aggregator Adapter в единый normalized quote model.

Scanner работает только с normalized model.

---

## 23. Quote Validation

Перед использованием quote Level 1 должен проверить:

- provider;
- network;
- input token;
- output token;
- input amount;
- output amount;
- quote timestamp;
- validity status.

---

## 24. Invalid Quote

Invalid quote не должен участвовать в profitability comparison.

Scanner должен зафиксировать причину invalid result в diagnostics.

---

## 25. Zero Output

Quote с zero output не должен считаться валидной прибыльной opportunity.

---

## 26. Missing Output

Если provider не вернул необходимый output amount:

candidate не создаётся.

---

## 27. Quote Timestamp

Каждый normalized quote должен иметь timestamp.

Level 1 должен учитывать freshness policy.

---

## 28. Quote Freshness

Если quote слишком старый согласно policy:

он не используется для candidate generation.

---

## 29. Fees

Level 1 может использовать доступные fee data для preliminary filtering.

Но Level 1 не должен самостоятельно реализовывать provider-specific fee logic.

---

## 30. Fee System

Fee data должна поступать через Fee System.

Если актуальная fee уже существует:

не выполнять отдельный duplicate fee request только ради текущего scan.

---

## 31. Gas

Level 1 может использовать актуальную gas estimate для preliminary profitability calculation.

Gas не должен игнорироваться только потому, что Level 1 является быстрым.

---

## 32. UNKNOWN Fee

UNKNOWN mandatory fee не должна считаться zero.

Если невозможно безопасно оценить candidate:

он должен быть отброшен либо передан в Level 2 согласно explicit policy.

---

## 33. Preliminary Profitability

Level 1 выполняет preliminary profitability assessment.

Она используется только для отбора кандидатов.

---

## 34. Final Profitability

Final profitability выполняется на Level 2 через Profit Calculator.

Level 1 result не является окончательным подтверждением.

---

## 35. Candidate Threshold

Level 1 может иметь configurable preliminary threshold.

Threshold используется только для уменьшения количества Level 2 candidates.

---

## 36. No Final Threshold Decision

Level 1 threshold не должен считаться окончательным profitability decision.

Final decision принимает Level 2 согласно утверждённой Profitability Policy.

---

## 37. Candidate Creation

Если opportunity проходит Level 1 preliminary policy:

создаётся Level 2 Job.

---

## 38. Candidate Data

Level 2 Job должен содержать минимум:

- job ID;
- network;
- input token;
- intermediate/output token;
- amount;
- entry provider;
- exit provider;
- route;
- Level 1 quote references;
- detected preliminary result;
- creation timestamp.

---

## 39. Level 1 Quote References

Level 2 должен иметь возможность понять, на основании каких Level 1 quotes candidate был создан.

Но Level 2 не должен использовать эти quotes как замену свежим confirmation quotes.

---

## 40. Candidate Timestamp

Каждый candidate получает creation timestamp.

Это необходимо для freshness и diagnostics.

---

## 41. Candidate Expiration

Candidate должен иметь configurable maximum lifetime.

Если Level 2 не успел обработать candidate в допустимое время:

candidate считается expired и не должен уведомляться как актуальный.

---

## 42. Duplicate Candidates

Одинаковые opportunities не должны бесконтрольно создавать множество Level 2 Jobs.

Необходима deduplication policy.

---

## 43. Candidate Fingerprint

Candidate должен иметь deterministic fingerprint, учитывающий существенные параметры.

Минимально:

- network;
- route;
- amount;
- entry provider;
- exit provider;
- token pair.

---

## 44. Deduplication Window

Deduplication может использовать configurable time window.

Одинаковый candidate в пределах этого окна не должен создавать бесконечные duplicate Level 2 Jobs.

---

## 45. Level 2 Priority

Созданный Level 2 Job получает более высокий priority, чем новый Level 1 scan.

---

## 46. Immediate Handoff

После создания candidate Level 1 должен немедленно передать его в Level 2 processing.

Не ждать следующего scanner cycle.

---

## 47. Queue Backpressure

Если Level 2 queue перегружена:

Level 1 должен учитывать backpressure policy.

Не создавать бесконечное количество candidates.

---

## 48. Candidate Limit

Должен существовать configurable limit на количество candidates, создаваемых одним scan cycle.

---

## 49. Candidate Ranking

Если candidates больше доступной capacity Level 2:

они должны быть ранжированы по предварительной ожидаемой привлекательности.

---

## 50. Ranking Factors

Ranking может учитывать:

- preliminary profit;
- profit percentage;
- amount;
- quote freshness;
- estimated gas;
- confidence;
- provider reliability.

---

## 51. No Opportunity Loss by Provider Failure

Ошибка одного provider не должна автоматически прекращать весь Level 1 cycle.

Другие доступные provider combinations должны продолжать проверяться.

---

## 52. Provider Timeout

Provider timeout должен обрабатываться Resource Manager.

Scanner должен получить normalized failure result.

---

## 53. Provider Rate Limit

При rate limit Level 1 должен:

- зафиксировать failure;
- не создавать false opportunity;
- продолжить работу с доступными resources.

Retry выполняется через Resource Manager policy.

---

## 54. Partial Scan

Если часть requests завершилась ошибкой:

scan может завершиться как partial, если policy это допускает.

Partial scan не должен считаться полностью успешным.

---

## 55. Scan Result

Каждый scan cycle должен иметь status.

Минимально:

- COMPLETED;
- PARTIAL;
- FAILED;
- CANCELLED.

---

## 56. Scan ID

Каждый Level 1 cycle получает unique scan ID.

---

## 57. Scan Metadata

Scan metadata должна содержать:

- scan ID;
- started_at;
- finished_at;
- network;
- tokens checked;
- amounts checked;
- providers checked;
- candidates created;
- errors;
- status.

---

## 58. Scan Isolation

Ошибки одного token/amount/provider combination не должны автоматически останавливать весь scan cycle.

---

## 59. Concurrency

Level 1 должен поддерживать controlled concurrency.

Количество одновременно выполняемых requests определяется Resource Manager.

---

## 60. No Unbounded Async Tasks

Scanner не должен создавать бесконечное количество asynchronous tasks для всех комбинаций сразу.

Необходим controlled scheduling/batching.

---

## 61. Scan Batching

Если provider API поддерживает batch quote requests:

Level 1 должен использовать batch, когда это уменьшает request overhead и не ухудшает актуальность данных.

---

## 62. Request Ordering

Порядок requests не должен нарушать Level 2 priority.

Если Resource Manager ограничивает capacity:

Level 2 requests имеют приоритет.

---

## 63. Scan Interval

Level 1 запускается Scheduler.

Scanner не должен самостоятельно создавать собственный infinite timer.

---

## 64. Default Scan Interval

Текущий production policy:

**каждые 5 минут.**

Значение должно оставаться configurable.

---

## 65. Overlap

Если предыдущий Level 1 scan ещё выполняется в момент следующего scheduled запуска:

по умолчанию применяется:

SKIP.

Не запускать второй полный scan параллельно без explicit policy.

---

## 66. Manual Scan

Архитектура должна позволять manual Level 1 scan.

Manual scan не должен менять scheduled interval.

---

## 67. Manual Scan Overlap

Если scheduled scan уже выполняется:

manual scan подчиняется overlap policy.

Не создавать duplicate full scan без необходимости.

---

## 68. Scan Scope

Один scan cycle должен иметь чётко определённый scope.

Scope определяется:

- networks;
- tokens;
- amounts;
- providers;
- routes.

---

## 69. Configuration Changes

Если configuration изменена:

следующий scan должен использовать актуальную configuration.

Не продолжать использовать устаревший configuration snapshot бесконечно.

---

## 70. Disabled Token

Disabled token не должен сканироваться.

---

## 71. Disabled Provider

Disabled provider не должен получать requests.

---

## 72. Disabled Network

Disabled network не должна участвовать в scan.

---

## 73. Unsupported Combination

Если token/provider/network combination не поддерживается:

request не выполняется.

Capability information должна использоваться до создания ненужного request.

---

## 74. Capability Registry

Level 1 должен использовать Capability Registry для предварительного определения доступности:

- provider;
- network;
- token;
- operation;
- route.

---

## 75. Capability Refresh

Изменения capability должны учитываться следующими scan cycles.

---

## 76. No Blind Requests

Level 1 не должен систематически отправлять requests для заранее известных unsupported combinations.

---

## 77. Profit Calculation Inputs

Preliminary calculation должен использовать:

- input amount;
- output amount;
- known fees;
- known gas;
- other confirmed costs.

---

## 78. Slippage

Если provider quote содержит slippage-related information:

она должна сохраняться в normalized quote.

Level 1 не должен игнорировать существенные ограничения quote.

---

## 79. Price Impact

Если provider предоставляет price impact:

он должен быть доступен для preliminary filtering.

---

## 80. Liquidity Signals

Если provider предоставляет liquidity-related information:

она может использоваться для ranking/filtering.

Но отсутствие такой информации не должно автоматически считаться нулевой ликвидностью.

---

## 81. Confidence

Candidate может иметь confidence score.

Confidence должен быть основан на доступных данных.

Не использовать случайные или произвольные значения.

---

## 82. Candidate Quality

Candidate должен содержать достаточно информации для Level 2 confirmation без необходимости повторно определять:

- route;
- provider pair;
- amount;
- network;
- token pair.

---

## 83. Telegram

Level 1 не отправляет Telegram notifications.

Даже если preliminary profit положительный.

---

## 84. Database

Level 1 может сохранять необходимые scan/candidate metadata в SQLite согласно retention policy.

Не требуется сохранять каждый raw quote навсегда.

---

## 85. History

История Level 1 должна использоваться только для:

- diagnostics;
- deduplication;
- audit;
- approved statistics.

---

## 86. No Full Quote History

Не хранить бесконечную историю всех quotes только потому, что они были получены.

---

## 87. Logging

Structured logging должен содержать:

- scan ID;
- provider;
- network;
- token pair;
- amount;
- request status;
- latency;
- candidate result.

Secrets запрещены.

---

## 88. Metrics

Level 1 должен собирать:

- scan duration;
- requests;
- successful requests;
- failed requests;
- partial scans;
- candidates;
- duplicates;
- skipped combinations;
- provider latency;
- queue wait;
- Level 2 handoffs.

---

## 89. Efficiency Metrics

Отдельно измерять:

- количество проверенных combinations;
- количество внешних requests;
- количество batch requests;
- количество skipped unsupported combinations;
- количество prevented duplicate requests;
- количество candidates на scan.

---

## 90. Error Isolation

Ошибка в одном:

- token;
- amount;
- provider;
- route;
- network

не должна без необходимости останавливать весь scanner.

---

## 91. Cancellation

Level 1 должен корректно поддерживать cancellation.

При cancellation:

- новые requests не создаются;
- queued scanner tasks отменяются;
- active requests корректно завершаются согласно Resource Manager policy;
- scan получает CANCELLED status.

---

## 92. Shutdown

При application shutdown Scheduler прекращает создание новых Level 1 scans.

Active scan должен получить graceful cancellation.

---

## 93. Recovery

После restart старый Level 1 scan не должен восстанавливаться как RUNNING.

Новый scan начинается согласно Scheduler policy.

---

## 94. Determinism

Для одинаковой configuration и одинаковых normalized inputs preliminary calculation должен быть deterministic.

---

## 95. Testing

Обязательно тестировать:

- token filtering;
- network filtering;
- provider filtering;
- capability filtering;
- amount handling;
- quote normalization;
- quote validation;
- freshness;
- fee integration;
- gas integration;
- preliminary profitability;
- candidate creation;
- candidate fingerprint;
- deduplication;
- candidate expiration;
- queue backpressure;
- ranking;
- partial scan;
- provider failure;
- timeout;
- rate limit;
- cancellation;
- restart;
- overlap;
- batch requests.

---

## 96. Critical Invariants

Level 1 Scanner никогда не должен:

1. выполнять swaps;

2. отправлять Telegram notification напрямую;

3. обходить Resource Manager;

4. выполнять provider-specific HTTP logic вне Adapter;

5. самостоятельно создавать infinite timer;

6. использовать устаревшие quotes вместо обязательных fresh quotes;

7. считать UNKNOWN mandatory fee равной zero;

8. считать Level 1 result окончательным подтверждением;

9. самостоятельно создавать произвольные routes;

10. сканировать disabled tokens;

11. отправлять requests для заранее известных unsupported combinations;

12. создавать бесконечную очередь Level 2 Jobs;

13. запускать duplicate full scans без overlap policy;

14. использовать Float для финансовых расчётов;

15. выполнять окончательное решение о Telegram notification.

---

## 97. Главный принцип

Level 1 Scanner должен:

**быстро и систематически находить потенциально прибыльные opportunities среди утверждённых tokens, amounts, routes, networks и aggregators, используя актуальные quotes и минимальное необходимое количество внешних requests, после чего немедленно передавать качественные candidates на Level 2 confirmation.**

Level 1 отвечает за:

**найти кандидата.**

Level 2 отвечает за:

**подтвердить кандидата.**
