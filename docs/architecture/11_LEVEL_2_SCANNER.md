# MONIK — LEVEL 2 SCANNER

## 1. Назначение

Level 2 Scanner — второй этап проверки Opportunity, найденной Level 1.

Его задача — получить максимально свежие данные по тому же самому маршруту, который был найден на первом этапе, и определить, сохраняется ли возможность после актуальной проверки.

Главный принцип:

**Level 2 не ищет новый маршрут. Он проверяет только маршрут, зафиксированный Level 1.**

---

## 2. Основная задача

Level 2 должен:

1. получить Opportunity от Level 1;
2. проверить её актуальность;
3. использовать зафиксированный route;
4. получить свежие quotes;
5. получить необходимые актуальные fee data;
6. проверить все configured amounts;
7. пересчитать profitability;
8. определить итоговый status;
9. сохранить confirmation result.

---

## 3. Level 2 не выполняет swap

Level 2 является только verification stage.

Он не выполняет:

- on-chain swap;
- transaction;
- wallet operation;
- execution.

---

## 4. Source of Truth

Основным источником для Level 2 является Opportunity, созданная Level 1.

Она содержит:

- tokens;
- network;
- aggregators;
- route;
- route fingerprint;
- amounts;
- relevant provider parameters.

---

## 5. Route Immutability

Route Opportunity является immutable для Level 2.

Level 2 не может:

- заменить aggregator;
- заменить pool;
- заменить route;
- изменить routing mode;
- выбрать другой path;
- выбрать более выгодный quote route.

---

## 6. Route Mismatch

Если Adapter не может выполнить quote по зафиксированному route:

Level 2 не должен искать альтернативу.

Результат:

ROUTE_UNAVAILABLE

или другой соответствующий failure status.

---

## 7. Same Route для всех Amounts

Все amounts одной Opportunity должны проверяться по **одному и тому же route**, найденному Level 1.

Например:

50 USDT
100 USDT
500 USDT
1000 USDT

используют один route snapshot.

---

## 8. Разные Financial Results

Хотя route одинаковый:

каждая сумма получает собственные:

- BUY output;
- SELL output;
- fees;
- gas;
- net profit;
- ROI;
- status.

---

## 9. Amount Processing

Level 2 должен обработать все amounts, относящиеся к Opportunity, если Opportunity ещё актуальна и ресурсы позволяют выполнить проверку.

Нельзя произвольно выбрать только наиболее прибыльную сумму.

---

## 10. Priority

Level 2 имеет более высокий priority, чем Level 1.

При конкуренции за API resources:

Level 2 должен обслуживаться раньше новых Level 1 requests согласно Resource Manager policy.

---

## 11. SELL-ready Priority

Если Opportunity находится в состоянии, требующем ускоренной SELL verification:

Level 2 Job получает соответствующий повышенный priority.

---

## 12. Fresh Quote

Для Level 2 необходимо получать новый quote.

Level 1 quote не считается актуальным quote для подтверждения.

---

## 13. Level 1 Quote

Level 1 quote используется как:

- исходная точка сравнения;
- часть Opportunity snapshot;
- diagnostic information.

Он не используется как свежий Level 2 quote.

---

## 14. BUY Verification

Level 2 сначала проверяет BUY route.

Он должен использовать:

- тот же aggregator;
- ту же network;
- тот же input token;
- тот же intermediate token;
- тот же routing mode;
- тот же route.

---

## 15. SELL Verification

После получения актуального BUY result Level 2 проверяет SELL route.

SELL должен использовать route, зафиксированный Level 1.

---

## 16. BUY → SELL Dependency

SELL amount должен соответствовать актуальному BUY output.

Например:

Level 1:

100 USDT → 5.10 AAVE

Level 2 BUY:

100 USDT → 5.03 AAVE

SELL должен проверять именно:

5.03 AAVE

а не старые:

5.10 AAVE

---

## 17. No Stale Intermediate Amount

Level 2 не должен использовать Level 1 intermediate token amount для текущего SELL quote, если новый BUY quote уже получен.

---

## 18. Route Fingerprint

Level 2 должен сравнить route fingerprint актуального response с route fingerprint Opportunity.

Если provider response не позволяет подтвердить соответствие:

route считается неподтверждённым.

---

## 19. Route Validation

Route validation должна проверять минимум:

- aggregator;
- network;
- input token;
- output token;
- routing mode;
- route structure;
- route fingerprint.

---

## 20. Adapter Responsibility

Aggregator Adapter отвечает за provider-specific interpretation route.

Level 2 не должен знать внутренний формат route каждого агрегатора.

---

## 21. Fixed Route API

Если API агрегатора поддерживает explicit fixed-route parameters:

Adapter должен использовать их.

Это предпочтительный способ проверки.

---

## 22. Fixed Route Capability

Перед Level 2 request может использоваться Capability Registry.

Если:

FIXED_ROUTE_UNSUPPORTED

Level 2 не должен молча выбирать новый route.

---

## 23. Fixed Route UNKNOWN

Если capability UNKNOWN:

поведение определяется policy.

Если безопасная runtime validation возможна:

можно выполнить её.

Если невозможно гарантировать route consistency:

confirmation не выполняется как полностью подтверждённая.

---

## 24. Quote Without Route Confirmation

Если provider API возвращает только общий quote и не позволяет подтвердить исходный route:

Level 2 не должен считать route автоматически совпадающим.

Необходим explicit policy для такого Adapter.

---

## 25. Aggregator Independence

Если BUY выполняется через Aggregator A, а SELL через Aggregator B:

Level 2 проверяет оба зафиксированных Aggregator Adapters.

Он не сравнивает их заново для выбора альтернативы.

---

## 26. Opportunity Expiration

Перед началом проверки Level 2 должен проверить Opportunity freshness/expiration.

Если Opportunity устарела:

Job получает:

EXPIRED

или соответствующий status.

---

## 27. Level 2 Timeout

Каждый Level 2 Job должен иметь общий timeout.

Отдельные API requests также имеют individual timeout.

---

## 28. Cancellation

Level 2 Job должен поддерживать cancellation.

При cancellation:

- queued requests снимаются;
- активные requests корректно завершаются;
- locks освобождаются;
- Job не становится CONFIRMED.

---

## 29. Resource Manager

Все внешние requests Level 2 проходят через Resource Manager.

Это относится к:

- BUY quote;
- SELL quote;
- fee requests;
- route validation requests;
- conversion requests.

---

## 30. Request Priority

Resource Manager должен знать, что request относится к Level 2.

Level 2 requests имеют priority выше Level 1.

---

## 31. Fee Data

Level 2 должен использовать актуальные fee data.

Fee System отвечает за:

- fee discovery;
- fee normalization;
- fee freshness;
- fee applicability.

---

## 32. Fee Requests

Level 2 не должен самостоятельно определять, когда и как обращаться к fee API.

Он запрашивает normalized fee data через Fee System.

---

## 33. Fee Reuse

Если актуальная fee data уже существует:

не выполнять ненужный повторный fee request.

---

## 34. Fee Update

Если fee data устарела:

Fee System должна выполнить необходимый update.

Level 2 получает результат после обновления.

---

## 35. Fee Unknown

UNKNOWN fee не должна считаться zero.

Если неизвестная fee может изменить profitability:

Opportunity не подтверждается как полностью прибыльная.

---

## 36. Gas

Gas должен учитываться через Fee System/Profit Calculator.

Level 2 не реализует собственную gas formula.

---

## 37. Profit Calculator

Все financial calculations выполняются через Profit Calculator.

Level 2 не содержит собственной формулы:

- profit;
- ROI;
- fees;
- gas.

---

## 38. Level 2 Calculation

Для каждой суммы Calculator получает:

- original input;
- current BUY output;
- current SELL output;
- applicable fees;
- gas;
- rebates;
- conversions.

---

## 39. Current BUY Output

Current BUY output должен использоваться для SELL verification.

---

## 40. Current SELL Output

Current SELL output является final output текущей Level 2 verification.

---

## 41. Net Profit

Level 2 использует актуальный normalized net profit.

---

## 42. Net ROI

Level 2 использует актуальный normalized net ROI.

---

## 43. Threshold

Default threshold:

1% net ROI

Threshold берётся из configuration/Profit Calculator.

---

## 44. Threshold Boundary

Если:

net ROI = 1%

при:

threshold = 1%

результат проходит threshold.

---

## 45. Confirmation

Opportunity может перейти в CONFIRMED только если:

- Opportunity актуальна;
- route подтверждён;
- BUY quote актуален;
- SELL quote актуален;
- fees достаточно известны;
- gas достаточно известен;
- calculation COMPLETE;
- profitability threshold выполнен.

---

## 46. Partial Confirmation

Если часть amounts подтверждена, а часть нет:

Opportunity не должна скрывать этот факт.

Каждый amount context получает собственный status.

---

## 47. Opportunity Status

Минимально поддерживать:

- CREATED;
- VERIFYING;
- CONFIRMED;
- PARTIAL;
- UNPROFITABLE;
- EXPIRED;
- ROUTE_UNAVAILABLE;
- FAILED;
- CANCELLED.

---

## 48. Amount Status

Каждая сумма может иметь:

- VERIFIED_PROFITABLE;
- VERIFIED_UNPROFITABLE;
- UNKNOWN;
- FAILED;
- EXPIRED;
- ROUTE_UNAVAILABLE.

---

## 49. CONFIRMED

CONFIRMED означает:

Opportunity успешно прошла Level 2 verification согласно утверждённой Confirmation Policy.

---

## 50. UNPROFITABLE

Если актуальный net ROI ниже threshold:

amount получает:

VERIFIED_UNPROFITABLE.

Opportunity не подтверждается для этой суммы.

---

## 51. Route Unavailable

Если исходный route невозможно воспроизвести:

amount не считается unprofitable.

Это отдельная причина:

ROUTE_UNAVAILABLE.

---

## 52. Unknown

Если невозможно определить результат из-за недостатка данных:

status:

UNKNOWN.

---

## 53. API Temporary Error

Temporary API error не должен превращать Opportunity в UNPROFITABLE.

Он должен обрабатываться через retry/error policy.

---

## 54. API Permanent Error

Permanent Error должен приводить к соответствующему failure status.

Не считать такую Opportunity автоматически прибыльной или неприбыльной.

---

## 55. Rate Limit

429 и аналогичные rate-limit responses не являются:

UNPROFITABLE.

Они обрабатываются Resource Manager.

---

## 56. Retry

Retries выполняются через общую Resource Manager policy.

Level 2 не должен самостоятельно создавать бесконечный retry loop.

---

## 57. Retry Safety

Retry не должен менять:

- route;
- aggregator;
- network;
- amount.

Retry повторяет проверку того же контекста.

---

## 58. Request Deduplication

Если несколько внутренних процессов требуют одну и ту же Level 2 verification:

не выполнять duplicate verification без необходимости.

---

## 59. Multiple Amounts и Requests

Если amounts используют один route, каждый amount должен быть проверен с соответствующим amount-specific quote.

Нельзя считать результат одной суммы результатом другой.

---

## 60. Same Route Invariant

Даже если для другого amount API предлагает более выгодный route:

Level 2 не может использовать его.

Он обязан проверить route Opportunity.

---

## 61. No Route Optimization

Level 2 не выполняет:

- route optimization;
- aggregator comparison;
- pool comparison;
- alternative route discovery.

Это запрещено архитектурой.

---

## 62. Opportunity Snapshot

Level 2 должен использовать immutable snapshot:

- route;
- tokens;
- network;
- aggregators;
- routing modes;
- provider parameters.

---

## 63. Capability Snapshot

Opportunity также может содержать capability snapshot Level 1.

Он используется для diagnostics.

Но текущая route validation должна учитывать актуальное состояние.

---

## 64. Capability Change

Если capability изменилась после Level 1:

Level 2 не меняет route.

Если route больше недоступен:

Opportunity получает соответствующий status.

---

## 65. Fee Snapshot

Level 2 должен сохранять fee snapshot:

- type;
- amount;
- currency;
- source;
- version;
- timestamp;
- applicability.

---

## 66. Calculation Snapshot

Level 2 должен сохранять calculation snapshot:

- input;
- BUY output;
- SELL output;
- costs;
- rebates;
- conversions;
- formula version;
- threshold;
- result.

---

## 67. Confirmation Snapshot

Итоговый Confirmation Result должен позволять восстановить:

почему Opportunity была:

- CONFIRMED;
- UNPROFITABLE;
- PARTIAL;
- FAILED;
- ROUTE_UNAVAILABLE.

---

## 68. Database

SQLite должна сохранять Level 2 result согласно утверждённой History Policy.

Для подтверждённых/значимых результатов сохранять необходимые snapshots.

---

## 69. No Full Quote History

Не сохранять полный поток всех Level 2 quotes без отдельной утверждённой необходимости.

Хранить только необходимые данные для:

- confirmed opportunity;
- diagnostics;
- audit;
- approved history.

---

## 70. Idempotency

Повторная обработка одного Level 2 Job не должна создавать duplicate business result.

Использовать:

- Job ID;
- Opportunity ID;
- verification revision.

---

## 71. Verification Revision

Каждая Level 2 verification должна иметь revision/version.

Это позволяет отличать:

первую проверку

от:

повторной проверки.

---

## 72. Logging

Structured logs должны содержать:

- Job ID;
- Opportunity ID;
- scan ID;
- amount;
- aggregator;
- network;
- route fingerprint;
- status;
- duration;
- error code.

Secrets запрещены.

---

## 73. Metrics

Собирать:

- Level 2 jobs;
- confirmations;
- unprofitable results;
- route unavailable;
- expired;
- failed;
- partial;
- average verification duration;
- requests per verification;
- fee requests;
- retry count.

---

## 74. Confirmation Latency

Система должна измерять время:

Opportunity created
→ Level 2 started
→ BUY verified
→ SELL verified
→ calculation complete
→ final status

Это необходимо для анализа качества и скорости системы.

---

## 75. Testing

Обязательно тестировать:

- same-route verification;
- fixed-route parameters;
- route mismatch;
- multiple amounts;
- current BUY output;
- current SELL output;
- fee update;
- unknown fee;
- gas;
- threshold;
- expiration;
- retry;
- cancellation;
- rate limit;
- temporary error;
- permanent error;
- idempotency;
- partial results.

---

## 76. Critical Invariants

Level 2 Scanner никогда не должен:

1. выбирать новый route;

2. заменять route Opportunity;

3. использовать разные routes для разных amounts одной Opportunity;

4. использовать старый Level 1 quote вместо свежего quote;

5. использовать старый BUY output для нового SELL quote;

6. считать UNKNOWN fee равной zero;

7. обходить Resource Manager;

8. выполнять swap;

9. самостоятельно реализовывать profitability formula;

10. подтверждать Opportunity при неизвестном критическом cost;

11. считать API error признаком unprofitability;

12. менять aggregator;

13. выполнять route optimization.

---

## 77. Главный принцип

Level 2 должен отвечать только на один вопрос:

**сохраняется ли найденная Level 1 возможность сейчас, при актуальных данных, на точно том же маршруте и с учётом всех известных расходов?**

Если да — Opportunity может быть подтверждена.

Если route изменился или его невозможно подтвердить — **route не заменяется**.

Если profitability не подтверждается — Opportunity не считается подтверждённой.
