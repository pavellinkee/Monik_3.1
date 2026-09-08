# MONIK — LEVEL 2 SCANNER

## 1. Назначение

Level 2 Scanner — финальный слой проверки потенциальной арбитражной возможности, созданной Level 1.

Его задача:

- получить свежие quotes;
- проверить актуальность route;
- проверить актуальные fees;
- проверить gas;
- выполнить окончательный profitability calculation;
- проверить все обязательные условия;
- исключить false positives;
- передать подтверждённую opportunity в Notification System.

Level 2 является последним аналитическим барьером перед уведомлением.

---

## 2. Главный принцип

Level 2 не доверяет предварительному результату Level 1 как окончательному.

Level 1 candidate используется как причина для повторной проверки.

Все критические данные должны быть получены или подтверждены заново согласно freshness policy.

---

## 3. Level 2 не выполняет swaps

Level 2 только анализирует и подтверждает opportunity.

Он не должен:

- подписывать transactions;
- отправлять transactions;
- выполнять swaps;
- управлять private keys.

---

## 4. Input

Level 2 получает Level 2 Job от Level 1.

Job должен содержать минимум:

- job ID;
- network;
- input token;
- output/intermediate token;
- amount;
- entry provider;
- exit provider;
- route;
- Level 1 references;
- creation timestamp;
- candidate fingerprint.

---

## 5. Job ID

Каждая Level 2 проверка должна иметь уникальный Job ID.

Job ID используется для:

- logging;
- diagnostics;
- deduplication;
- audit;
- recovery;
- notification correlation.

---

## 6. Candidate Fingerprint

Level 2 должен сохранить candidate fingerprint, созданный Level 1.

Fingerprint позволяет определить, является ли opportunity той же самой opportunity, которая уже проверялась ранее.

---

## 7. Immediate Execution

Level 2 Job должен обрабатываться немедленно после создания.

Он не должен ждать следующего Level 1 scan cycle.

---

## 8. Priority

Level 2 имеет более высокий priority, чем обычный Level 1 scan.

Resource Manager должен обеспечивать возможность обработки Level 2 requests с повышенным приоритетом.

---

## 9. Queue

Level 2 Jobs должны проходить через controlled queue.

Нельзя создавать неограниченное количество concurrent Level 2 Jobs.

---

## 10. Job States

Минимально поддерживать:

- QUEUED;
- RUNNING;
- CONFIRMED;
- REJECTED;
- EXPIRED;
- FAILED;
- CANCELLED.

---

## 11. Job Expiration

Каждый Job должен иметь maximum lifetime.

Если Job слишком долго находится в очереди или обработке:

он считается expired согласно configuration policy.

Expired Job не должен отправляться как актуальная opportunity.

---

## 12. Fresh Quotes

Level 2 должен получить свежие quotes непосредственно перед окончательным расчётом.

Level 1 quotes используются только как reference.

---

## 13. Level 1 Quote Reuse

Level 1 quote может быть использован для diagnostics и comparison.

Он не заменяет обязательный fresh quote.

---

## 14. Entry Quote

Level 2 должен получить актуальный entry quote для выбранного:

- provider;
- network;
- token;
- amount;
- route.

---

## 15. Exit Quote

Level 2 должен получить актуальный exit quote для соответствующей второй leg.

---

## 16. Route Consistency

Level 2 должен проверить, что полученные quotes соответствуют route из Job.

Если route изменился:

Job должен быть rejected либо обработан согласно explicit policy.

Level 2 не должен самостоятельно придумывать новый route.

---

## 17. Amount Consistency

Fresh quote должен соответствовать amount из Level 2 Job.

Нельзя использовать quote для другой суммы.

---

## 18. Token Consistency

Fresh quotes должны соответствовать:

- input token;
- intermediate token;
- output token.

Несоответствие приводит к rejection.

---

## 19. Network Consistency

Fresh quotes должны относиться к той же network, что указана в Job.

---

## 20. Provider Consistency

Fresh quotes должны быть получены от providers, указанных в Job.

Level 2 не должен молча менять provider pair.

---

## 21. Aggregator Adapters

Level 2 взаимодействует с providers только через Aggregator Adapters.

Provider-specific API logic запрещена внутри Level 2 Scanner.

---

## 22. Resource Manager

Все внешние requests Level 2 проходят через Resource Manager.

Это включает:

- quote requests;
- gas requests;
- fee requests;
- blockchain RPC;
- required external data.

---

## 23. Level 2 Request Priority

Level 2 requests получают высокий priority через Resource Manager.

Обычные Level 1 requests не должны бесконтрольно вытеснять Level 2.

---

## 24. Quote Validation

Каждый fresh quote должен пройти validation.

Минимально проверять:

- provider;
- network;
- input token;
- output token;
- input amount;
- output amount;
- timestamp;
- validity;
- required fields.

---

## 25. Invalid Quote

Если любой обязательный quote invalid:

Job получает REJECTED или FAILED согласно типу ошибки.

Notification не отправляется.

---

## 26. Quote Freshness

Freshness policy должна быть configurable.

Если quote старше допустимого возраста:

он не может использоваться для final confirmation.

---

## 27. Quote Expiration

Если provider предоставляет quote expiration:

Level 2 должен учитывать его.

---

## 28. Fee System

Все fee data Level 2 получает через Fee System.

Level 2 не должен самостоятельно определять provider-specific fees.

---

## 29. Fee Freshness

Для final confirmation обязательные fee data должны быть актуальными.

Stale critical fee не должна использоваться.

---

## 30. UNKNOWN Fee

UNKNOWN mandatory fee означает, что final profitability не может считаться достоверно подтверждённой.

По умолчанию Job должен быть REJECTED либо FAILED согласно policy.

---

## 31. Gas

Level 2 должен использовать актуальную gas estimate.

Gas является обязательным cost component, если он применим к операции.

---

## 32. Gas Freshness

Gas data должна соответствовать freshness policy.

Старая gas estimate не должна использоваться, если она может существенно изменить profitability.

---

## 33. Fee Inclusion

Level 2 должен учитывать статус:

included_in_quote.

Если fee уже включена в quote:

она не должна вычитаться повторно.

---

## 34. Double Counting Protection

Одна и та же cost component не должна учитываться дважды.

Profit Calculator получает normalized fee/cost components.

---

## 35. Profit Calculator

Final profitability рассчитывается только через Profit Calculator.

Level 2 не должен содержать отдельную profitability formula.

---

## 36. Calculation Inputs

Profit Calculator должен получить:

- input amount;
- final output amount;
- fees;
- gas;
- rebates;
- other confirmed costs;
- required market/conversion data.

---

## 37. Decimal

Все финансовые значения передаются как Decimal или equivalent exact arithmetic representation.

Float запрещён.

---

## 38. Final Profit

Final profit должен быть рассчитан после получения всех обязательных inputs.

---

## 39. Profit Threshold

Final profitability threshold применяется только на Level 2.

Level 1 preliminary threshold не является заменой final threshold.

---

## 40. Profit Percentage

Если policy требует:

Profit Calculator также рассчитывает profit percentage.

Формула и basis должны быть определены централизованно.

---

## 41. Negative Profit

Если final profit <= 0:

Job получает REJECTED.

Telegram notification не отправляется.

---

## 42. Threshold Failure

Если final profit ниже configured threshold:

Job получает REJECTED.

---

## 43. Positive Profit

Положительный preliminary result Level 1 не является достаточным основанием для notification.

Только положительный final result Level 2 может пройти дальше.

---

## 44. Rebate

Если применимый rebate подтверждён:

он передаётся в Profit Calculator как отдельный component.

Нельзя создавать предполагаемый rebate без подтверждённого source.

---

## 45. Other Costs

Все подтверждённые дополнительные costs должны передаваться в Profit Calculator.

---

## 46. Missing Cost

Если обязательный cost неизвестен:

нельзя считать его zero без explicit policy.

---

## 47. Final Confirmation Snapshot

После final calculation Level 2 должен создать confirmation snapshot.

Snapshot должен содержать:

- Job ID;
- timestamp;
- network;
- route;
- amount;
- fresh quotes;
- fee components;
- gas;
- calculation result;
- threshold result;
- status.

---

## 48. Calculation Version

Confirmation snapshot должен содержать версию Profit Calculator или calculation policy.

Это позволяет воспроизвести результат.

---

## 49. Fee Snapshot Reference

Если Fee System предоставляет snapshot version:

Level 2 должен сохранить reference на использованный fee snapshot.

---

## 50. Quote References

Level 2 должен сохранить ссылки/metadata на fresh quotes, использованные для confirmation.

---

## 51. Auditability

Для каждой подтверждённой opportunity должно быть возможно определить:

- какой Job;
- какой route;
- какие providers;
- какие quotes;
- какие fees;
- какой gas;
- какой calculation;
- какой threshold;
- какое время проверки

привели к подтверждению.

---

## 52. Notification Boundary

После успешной final confirmation Level 2 передаёт normalized confirmed opportunity в Notification System.

Level 2 не должен самостоятельно форматировать Telegram message.

---

## 53. Telegram

Level 2 не должен напрямую вызывать Telegram API.

Telegram отправляется отдельной Notification subsystem.

---

## 54. Notification Data

Confirmed opportunity должна содержать достаточно данных для notification:

- token pair;
- amount;
- entry provider;
- exit provider;
- route;
- input;
- output;
- fees;
- gas;
- final profit;
- profit percentage;
- timestamp.

---

## 55. Multiple Amounts

Каждый Level 2 Job относится к конкретному amount.

Если Level 1 обнаружил profitability для нескольких amounts:

каждая сумма должна пройти отдельную final confirmation.

---

## 56. No Amount Mixing

Нельзя использовать:

- quote одной суммы;
- fee другой суммы;
- gas estimate третьей суммы

в одном final calculation без explicit applicability.

---

## 57. Duplicate Job

Если один и тот же candidate был создан повторно:

deduplication policy должна предотвращать бессмысленные повторные confirmations.

---

## 58. Already Confirmed

Если candidate уже был подтверждён и notification отправлена в пределах deduplication policy:

новый duplicate Job не должен автоматически отправлять повторное notification.

---

## 59. Opportunity Identity

Opportunity identity должна учитывать существенные параметры:

- network;
- route;
- amount;
- token pair;
- entry provider;
- exit provider.

---

## 60. Confirmation Window

Для одинаковой opportunity может существовать configurable confirmation/deduplication window.

---

## 61. Revalidation

Если Job остаётся в очереди слишком долго:

он должен быть revalidated или rejected.

Нельзя подтверждать давно созданный candidate на основании его старых Level 1 data.

---

## 62. Provider Failure

Ошибка одного provider во время Level 2 confirmation должна приводить к failed/rejected Job согласно policy.

Нельзя считать отсутствующий quote прибыльным.

---

## 63. Timeout

Level 2 должен иметь configurable timeout.

Если confirmation не завершена в пределах timeout:

Job получает FAILED или EXPIRED согласно policy.

---

## 64. Retry

Retry выполняется согласно Resource Manager/task policy.

Не создавать бесконечный retry loop внутри Level 2.

---

## 65. Retry Safety

Повторная попытка не должна использовать неактуальные данные предыдущей попытки.

Критические quotes должны быть получены заново.

---

## 66. Provider Rate Limit

При rate limit Job не должен считаться подтверждённым.

Resource Manager применяет backoff/retry policy.

---

## 67. Partial Data

Неполный набор critical data не является достаточным для final confirmation.

---

## 68. Concurrency

Level 2 должен поддерживать controlled concurrency.

Количество одновременно выполняемых confirmations контролируется Resource Manager и Job queue policy.

---

## 69. Queue Backpressure

Если Level 2 queue достигает configured capacity:

новые candidates должны обрабатываться согласно backpressure policy.

Не создавать бесконечную очередь.

---

## 70. Priority Ordering

При наличии нескольких Jobs:

более высокий priority обрабатывается раньше низкого.

Внутри одинакового priority должна применяться deterministic ordering policy.

---

## 71. Fairness

Priority system не должна создавать бесконечный starvation для допустимых Jobs.

---

## 72. Cancellation

Level 2 должен поддерживать cancellation.

После cancellation:

- новые requests не создаются;
- queued work отменяется;
- active operations корректно завершаются;
- Job получает CANCELLED status.

---

## 73. Shutdown

При application shutdown:

- новые Level 2 Jobs не запускаются;
- queued jobs обрабатываются согласно shutdown policy;
- active jobs получают graceful cancellation.

---

## 74. Recovery

После restart старые Level 2 Jobs не должны автоматически считаться CONFIRMED.

Они должны быть:

- revalidated;
- expired;
- rejected;
- либо восстановлены согласно explicit recovery policy.

---

## 75. Database

Level 2 должен сохранять необходимую confirmation metadata в SQLite согласно retention policy.

---

## 76. Confirmed Opportunities

Подтверждённые opportunities должны иметь persistent record.

Record должен позволять восстановить результат final confirmation.

---

## 77. Rejected Opportunities

Не обязательно хранить каждый rejected Job навсегда.

Retention policy должна определять необходимый объём diagnostics/history.

---

## 78. Logging

Structured logging должен содержать:

- Job ID;
- candidate fingerprint;
- provider;
- network;
- route;
- amount;
- status;
- failure reason;
- confirmation duration.

Secrets запрещены.

---

## 79. Metrics

Level 2 должен собирать:

- jobs received;
- jobs confirmed;
- jobs rejected;
- jobs expired;
- jobs failed;
- jobs cancelled;
- confirmation latency;
- quote failures;
- fee failures;
- gas failures;
- profitability failures;
- duplicate jobs;
- notification handoffs.

---

## 80. Confirmation Quality Metrics

Необходимо измерять:

- долю Level 1 candidates, прошедших Level 2;
- долю false positives;
- среднее время confirmation;
- количество rejected из-за stale data;
- количество rejected из-за missing fees;
- количество rejected из-за negative profit.

---

## 81. Notification Failure

Если final confirmation успешна, но Notification System не смогла отправить сообщение:

это не должно превращать уже подтверждённую opportunity в unconfirmed.

Notification failure должен иметь отдельный status/error.

---

## 82. No Recalculation in Notification

Notification System не должна заново рассчитывать profitability.

Она использует final confirmation snapshot.

---

## 83. No Scanner Logic

Level 2 не должен:

- запускать Level 1;
- выбирать новые routes;
- менять provider pair;
- менять amount;
- создавать произвольные opportunities.

---

## 84. No Trading Logic

Level 2 не должен содержать:

- wallet management;
- private key management;
- transaction signing;
- transaction broadcasting;
- swap execution.

---

## 85. Testing

Обязательно тестировать:

- Job validation;
- fresh quote requests;
- quote freshness;
- route consistency;
- token consistency;
- network consistency;
- provider consistency;
- fee freshness;
- unknown fees;
- gas;
- rebates;
- included-in-quote;
- double counting;
- final profitability;
- thresholds;
- duplicate jobs;
- expiration;
- timeout;
- retry;
- provider failures;
- rate limits;
- cancellation;
- shutdown;
- recovery;
- notification handoff.

---

## 86. Integration Tests

Обязательно иметь integration tests:

Level 1 → Level 2

Level 2 → Fee System

Level 2 → Profit Calculator

Level 2 → Notification System

Level 2 → Resource Manager

---

## 87. Critical Invariants

Level 2 Scanner никогда не должен:

1. выполнять swaps;

2. подписывать transactions;

3. отправлять Telegram API requests напрямую;

4. обходить Resource Manager;

5. использовать Level 1 quote вместо обязательного fresh quote;

6. считать UNKNOWN mandatory fee равной zero;

7. использовать stale critical fee;

8. использовать stale gas при отсутствии разрешающей policy;

9. рассчитывать profitability собственной альтернативной формулой;

10. дважды учитывать одну и ту же fee;

11. менять route без explicit policy;

12. менять provider pair без explicit policy;

13. менять amount без explicit policy;

14. подтверждать opportunity при неполных critical data;

15. создавать бесконечные retries;

16. считать notification failure отменой уже подтверждённой opportunity;

17. использовать Float для финансовых расчётов;

18. автоматически восстанавливать старый Job как CONFIRMED после restart.

---

## 88. Главный принцип

Level 2 Scanner должен:

**получить Level 1 candidate, немедленно перепроверить его на свежих данных, учесть актуальные fees и gas, выполнить окончательный profitability calculation и только после успешного подтверждения передать opportunity в Notification System.**

Level 1 отвечает за:

**найти кандидата.**

Level 2 отвечает за:

**подтвердить, что возможность действительно существует сейчас.**
