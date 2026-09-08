# MONIK — LEVEL 1 SCANNER

## 1. Назначение

Level 1 Scanner — первый этап поиска арбитражных возможностей.

Он выполняет быстрый поиск потенциально прибыльных комбинаций между агрегаторами и формирует Opportunity для второго этапа проверки.

Главный принцип:

**Level 1 должен быть быстрым и экономным по количеству API requests, но не должен использовать неподтверждённые или заведомо устаревшие данные как реальные quotes.**

---

## 2. Основная задача

Level 1 должен:

1. получить актуальные quotes;
2. сравнить результаты;
3. определить потенциальную разницу;
4. рассчитать предварительную profitability;
5. выбрать наиболее перспективные возможности;
6. создать Level 2 Job;
7. передать ему маршрут, найденный на первом этапе.

---

## 3. Level 1 не подтверждает сделку

Результат Level 1 является:

POTENTIAL OPPORTUNITY

а не:

CONFIRMED OPPORTUNITY.

Окончательная проверка выполняется Level 2.

---

## 4. Источник токенов

Level 1 использует список активных токенов из Token Registry/Configuration.

Scanner не должен иметь собственный hard-coded список токенов.

---

## 5. Top-N

Количество токенов ограничивается configuration.

Default:

top_tokens = 30

Изменение этого значения не требует изменения Scanner code.

---

## 6. Сети

Scanner работает только с enabled networks.

Network availability определяется через:

- configuration;
- Capability Registry;
- Adapter availability.

---

## 7. Агрегаторы

Scanner работает только с enabled Aggregator Adapters.

Текущие production adapters:

- 1inch;
- 0x;
- Velora;
- Uniswap.

Добавление нового агрегатора не должно требовать переписывания основного Scanner loop.

---

## 8. Направления

Scanner должен поддерживать:

- BUY;
- SELL.

BUY и SELL являются отдельными operation contexts.

---

## 9. BUY

BUY означает:

input token → intermediate token.

Например:

USDT → AAVE.

---

## 10. SELL

SELL означает:

intermediate token → output token.

Например:

AAVE → USDT.

---

## 11. Арбитражный цикл

Базовый workflow:

USDT
  ↓ BUY
AAVE
  ↓ SELL
USDT

Результат SELL сравнивается с исходной суммой.

---

## 12. Aggregator Comparison

Level 1 ищет возможности за счёт различий между quotes разных агрегаторов.

Например:

Aggregator A:

100 USDT → 5.10 AAVE

Aggregator B:

5.10 AAVE → 101.50 USDT

Предварительная возможность:

101.50 - 100 = 1.50 USDT

---

## 13. Не считать quote execution

Level 1 только получает quote.

Он не выполняет:

- swap;
- transaction;
- on-chain execution.

---

## 14. Fresh Quotes

Каждый новый Level 1 scan должен использовать свежие API quotes.

Не использовать старые trading quotes вместо нового запроса.

---

## 15. Capability Filtering

До отправки quote request Scanner может использовать Capability Registry.

Явно UNSUPPORTED комбинации не должны отправляться во внешний API.

---

## 16. UNKNOWN Capability

UNKNOWN не следует автоматически считать UNSUPPORTED.

Если policy разрешает runtime проверку:

Scanner может выполнить quote request.

---

## 17. Resource Manager

Каждый внешний quote request должен проходить через Resource Manager.

Scanner не должен напрямую обходить Resource Manager.

---

## 18. Concurrency

Scanner может выполнять requests параллельно, если:

- Resource Manager разрешает;
- rate limits не нарушаются;
- API-specific concurrency limits соблюдаются.

---

## 19. Request Minimization

Scanner должен минимизировать количество requests.

Не выполнять:

- duplicate requests;
- unsupported requests;
- ненужные повторные capability checks;
- ненужные fee discovery requests.

---

## 20. Нет quote cache

Level 1 не должен использовать долгосрочный quote cache вместо fresh API request.

Каждый scan получает актуальные quotes.

---

## 21. Несколько сумм

Scanner должен поддерживать несколько configured amounts.

Например:

- 50 USDT;
- 100 USDT;
- 500 USDT;
- 1000 USDT.

---

## 22. Независимый расчёт сумм

Каждая сумма должна иметь отдельный profitability result.

Результат для одной суммы не переносится автоматически на другую.

---

## 23. Opportunity на сумму

Если одна и та же возможность существует для нескольких сумм:

можно сформировать одну Opportunity с несколькими amount contexts.

При этом каждая сумма сохраняет отдельный result.

---

## 24. Один маршрут для всех сумм

Если Opportunity создана на первом этапе:

**все суммы этой Opportunity используют тот же маршрут, который был найден на первом этапе.**

Разные суммы не могут получить разные маршруты.

Это обязательное архитектурное правило.

---

## 25. Route Snapshot

При создании Opportunity Scanner обязан сохранить:

- aggregator;
- network;
- input token;
- output token;
- routing mode;
- route data;
- route fingerprint;
- relevant provider parameters.

---

## 26. Route Ownership

Route выбирается Level 1.

Level 2 не должен самостоятельно выбирать новый route вместо исходного.

---

## 27. Route Fingerprint

Для каждой Opportunity должен существовать deterministic route fingerprint.

Он используется для:

- идентификации;
- сравнения;
- diagnostics;
- Level 2 fixed-route validation.

---

## 28. BUY Route

BUY route должен быть сохранён отдельно.

Например:

USDT → AAVE
Aggregator: 1inch
Route: ...

---

## 29. SELL Route

SELL route также должен быть сохранён отдельно.

Например:

AAVE → USDT
Aggregator: 0x
Route: ...

---

## 30. Full Opportunity Route

Opportunity должна содержать полный маршрут:

input token
→ BUY route
→ intermediate token
→ SELL route
→ output token

---

## 31. Level 2 Route Rule

Level 2 получает именно этот route.

Он не должен:

- искать другой aggregator;
- выбирать другой pool;
- менять routing mode;
- выбирать более выгодный route.

---

## 32. Route Mismatch

Если Level 2 не может воспроизвести исходный route:

Opportunity не считается подтверждённой по этому route.

Не заменять route автоматически.

---

## 33. BUY Aggregator

Opportunity должна хранить aggregator, использованный для BUY.

---

## 34. SELL Aggregator

Opportunity должна хранить aggregator, использованный для SELL.

---

## 35. Same Aggregator

BUY и SELL могут выполняться через один агрегатор, если это разрешено architecture/configuration.

---

## 36. Cross-Aggregator

BUY и SELL могут использовать разные агрегаторы.

Это является одним из основных сценариев поиска арбитража.

---

## 37. Token Pair

Каждая Opportunity должна содержать:

- input token;
- intermediate token;
- output token.

Для базового round-trip:

input token = output token.

---

## 38. Network

BUY и SELL в одной Opportunity должны относиться к одной сети.

Cross-chain arbitrage не является частью текущего workflow, если отдельная architecture policy не будет утверждена позднее.

---

## 39. Amount

Каждый amount context должен содержать:

- raw amount;
- Decimal amount;
- token;
- calculation currency.

---

## 40. Quote Validation

Перед использованием quote Scanner должен убедиться:

- input token совпадает;
- output token совпадает;
- network совпадает;
- amount совпадает;
- response корректен;
- quote не содержит критических ошибок.

---

## 41. Invalid Quote

Invalid quote не должен участвовать в profitability comparison.

---

## 42. Quote Errors

Scanner должен различать:

- Temporary Error;
- Rate Limit;
- Permanent Error;
- Unsupported;
- Data Error.

Ошибка одного quote не должна автоматически останавливать весь scan.

---

## 43. Partial Scan

Если один агрегатор не ответил:

остальные независимые quotes могут использоваться.

Scan может завершиться как PARTIAL.

---

## 44. Full Scan

FULL scan означает, что все необходимые requests завершились успешно и результаты доступны.

---

## 45. Scan Status

Минимально:

- RUNNING;
- COMPLETE;
- PARTIAL;
- FAILED;
- CANCELLED.

---

## 46. Opportunity Detection

Opportunity создаётся только если найден потенциально выгодный цикл.

Scanner использует Profit Calculator.

Не создавать отдельную profitability formula внутри Scanner.

---

## 47. Gross vs Net

Scanner должен ориентироваться на normalized financial result.

Если все необходимые fees известны:

использовать net profitability.

Если критический cost unknown:

не считать opportunity подтверждённо прибыльной.

---

## 48. Threshold

Default:

1% net ROI.

Threshold берётся из configuration/Profit Calculator.

Scanner не должен hard-code значение threshold.

---

## 49. Threshold Boundary

Если:

net ROI = 1%

при threshold:

1%

возможность проходит threshold.

---

## 50. Unknown Fee

UNKNOWN fee не равна zero.

Если неизвестная комиссия способна изменить результат:

Opportunity не должна считаться подтверждённо прибыльной.

---

## 51. Gas

Gas учитывается через Fee System/Profit Calculator.

Scanner не должен самостоятельно вычислять gas cost.

---

## 52. Duplicate Opportunities

Scanner не должен создавать множество одинаковых Opportunities в рамках одного scan.

Для deduplication использовать deterministic opportunity identity.

---

## 53. Opportunity Identity

Identity должна учитывать как минимум:

- network;
- input token;
- intermediate token;
- output token;
- BUY aggregator;
- SELL aggregator;
- BUY route fingerprint;
- SELL route fingerprint.

Если amount-specific identity требуется business policy:

amount добавляется отдельно.

---

## 54. Same Opportunity, Multiple Amounts

Если route и pair одинаковы, разные amounts могут принадлежать одной Opportunity.

Amount results хранятся внутри Opportunity как отдельные contexts.

---

## 55. Opportunity Timestamp

Каждая Opportunity должна иметь:

- detected_at;
- scan_id.

---

## 56. Scan ID

Каждый scan должен иметь unique scan ID.

Все requests и Opportunities этого scan должны быть связаны с ним.

---

## 57. Request ID

Каждый внешний request имеет собственный request ID.

Он должен быть связан с:

- scan ID;
- task ID;
- aggregator;
- network;
- operation.

---

## 58. Level 2 Job Creation

После обнаружения Opportunity Scanner создаёт Level 2 Job.

Job содержит:

- Opportunity ID;
- route snapshot;
- amounts;
- relevant quote context;
- timestamps;
- priority.

---

## 59. Level 2 Priority

Level 2 Job получает более высокий priority, чем новые Level 1 scans.

Resource Manager обеспечивает соответствующее преимущество при конфликте ресурсов.

---

## 60. SELL-ready

Если Opportunity уже соответствует условиям SELL-ready policy:

Level 2 Job должен получить соответствующий высокий приоритет.

---

## 61. Scanner не исполняет Level 2

Level 1 Scanner не должен сам выполнять Level 2 confirmation.

Он только создаёт Job.

---

## 62. Scanner не отправляет Telegram

Scanner не должен самостоятельно формировать Telegram notifications.

Notification layer получает Opportunity/Level 2 result.

---

## 63. Scanner не хранит историю

Историческое хранение является отдельной responsibility Database/History subsystem.

Scanner только создаёт normalized records/events.

---

## 64. Profitable History

Сохраняться должны только результаты, соответствующие утверждённой policy хранения profitable opportunities.

Не хранить полный поток всех quotes.

---

## 65. Scan Frequency

Периодичность Level 1 scan определяется Scheduler/Configuration.

Scanner не должен самостоятельно запускать бесконечный loop с hard-coded interval.

---

## 66. Manual Scan

Архитектура должна позволять выполнить manual scan через Scheduler/Supervisor.

Manual scan не должен обходить Resource Manager.

---

## 67. Cancellation

Scan должен поддерживать cancellation.

При cancellation:

- queued requests снимаются;
- активные requests корректно обрабатываются;
- locks освобождаются;
- partial results не должны считаться COMPLETE.

---

## 68. Timeout

Каждый scan имеет общий timeout согласно configuration.

Отдельные API requests также имеют собственные timeout.

---

## 69. Backpressure

Если предыдущий scan ещё выполняется:

Scheduler/Scanner policy должна предотвращать неконтролируемое создание новых overlapping scans.

Не создавать бесконечную очередь одинаковых scans.

---

## 70. Scan Deduplication

Если два одинаковых scan requests поступили одновременно:

Scheduler/Scanner должен использовать deduplication policy.

Не выполнять один и тот же полный scan дважды без необходимости.

---

## 71. Parallel Aggregators

Независимые агрегаторы могут проверяться параллельно.

Например:

1inch и 0x могут одновременно получать quotes, если Resource Manager позволяет.

---

## 72. Parallel Networks

Разные сети могут сканироваться параллельно, если:

- они enabled;
- capabilities позволяют;
- Resource Manager разрешает;
- API limits не нарушаются.

---

## 73. Network Isolation

Проблема одного network не должна автоматически останавливать другие сети.

---

## 74. Aggregator Isolation

Проблема одного aggregator не должна автоматически останавливать остальные.

---

## 75. Token Isolation

Если один token имеет invalid response:

не прекращать весь scan остальных tokens.

---

## 76. Scan Result

Scan result должен содержать:

- scan ID;
- started_at;
- finished_at;
- status;
- requests count;
- successful quotes;
- failed quotes;
- opportunities found.

---

## 77. Metrics

Scanner должен собирать:

- scans started;
- scans completed;
- scans partial;
- scans failed;
- requests;
- successful requests;
- failed requests;
- opportunities found;
- opportunities per network;
- opportunities per aggregator;
- scan duration.

---

## 78. Logging

Structured logs должны содержать:

- scan ID;
- task ID;
- opportunity ID;
- network;
- tokens;
- aggregator;
- route fingerprint;
- duration;
- result.

Secrets запрещены.

---

## 79. Performance

Scanner должен минимизировать:

- duplicate API requests;
- unnecessary capability checks;
- unnecessary fee requests;
- serial execution там, где возможна безопасная parallel execution.

---

## 80. Но скорость не важнее корректности

Запрещено уменьшать количество requests способом, который:

- использует stale quote;
- меняет route;
- нарушает API limits;
- игнорирует fee;
- создаёт ложную profitability.

---

## 81. Quote Pairing

BUY и SELL quotes должны сравниваться только если:

- intermediate token совпадает;
- network совпадает;
- amount context корректен;
- route context валиден.

---

## 82. Intermediate Token

BUY output token должен точно совпадать с SELL input token.

Например:

BUY:

USDT → AAVE

SELL должен начинаться:

AAVE → ...

а не:

ETH → ...

---

## 83. Final Token

Для round-trip opportunity final output token должен совпадать с исходным input token.

---

## 84. Route Consistency

Route snapshot должен соответствовать quote, на основании которого создана Opportunity.

Нельзя сохранять route от одного quote, а amounts/output от другого.

---

## 85. Atomic Opportunity Creation

Opportunity и её amount contexts должны создаваться атомарно.

Не должно существовать Opportunity без обязательных route/context data.

---

## 86. Opportunity Expiration

Opportunity должна иметь expiration/freshness policy.

Level 2 не должен бесконечно пытаться подтвердить старую Opportunity.

---

## 87. Level 2 Freshness

Перед Level 2 confirmation необходимо проверить, что Opportunity ещё допустима для проверки.

Если срок истёк:

Job должен быть отменён/expired согласно policy.

---

## 88. No Route Optimization in Level 2

Level 2 не выполняет оптимизацию исходного route.

Он проверяет именно найденный route.

---

## 89. No Cross-Amount Route Selection

Для разных amounts:

не выбирать отдельные routes.

Все amounts используют route snapshot Opportunity.

---

## 90. Amount-specific Result

Несмотря на общий route:

каждая сумма получает собственные:

- BUY output;
- SELL output;
- fees;
- gas;
- net profit;
- ROI;
- status.

---

## 91. Level 1 Output

Основной output Level 1:

Opportunity + Level 2 Job.

---

## 92. Failure Policy

Если Opportunity creation не удалась:

ошибка должна быть logged и обработана Supervisor.

Не продолжать workflow с неполной Opportunity.

---

## 93. Testing

Обязательно тестировать:

- quote acquisition;
- capability filtering;
- multiple aggregators;
- multiple networks;
- multiple tokens;
- multiple amounts;
- BUY/SELL pairing;
- route capture;
- route fingerprint;
- opportunity deduplication;
- threshold;
- unknown fees;
- partial scan;
- timeout;
- cancellation;
- Level 2 Job creation;
- same-route rule.

---

## 94. Critical Invariants

Level 1 Scanner никогда не должен:

1. выполнять swap transactions;

2. подтверждать Opportunity окончательно;

3. выбирать разные routes для разных amounts одной Opportunity;

4. позволять Level 2 автоматически менять найденный route;

5. использовать UNKNOWN fee как zero;

6. обходить Resource Manager;

7. выполнять полный capability discovery перед каждым scan;

8. использовать stale quotes вместо fresh requests;

9. самостоятельно реализовывать profitability formula;

10. создавать бесконечную очередь scans;

11. смешивать разные networks;

12. смешивать разные intermediate tokens;

13. записывать secrets в logs.

---

## 95. Главный принцип

Level 1 Scanner должен:

**как можно быстрее находить потенциальные арбитражные возможности на свежих quotes, используя только допустимые capabilities и ресурсы, фиксируя конкретный маршрут, который затем будет проверен Level 2.**

Самое важное правило:

**Level 1 находит Opportunity и фиксирует route. Level 2 проверяет именно этот route.**
