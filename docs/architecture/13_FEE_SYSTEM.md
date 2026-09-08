# MONIK — FEE SYSTEM

## 1. Назначение

Fee System — единая подсистема получения, нормализации, обновления и предоставления информации обо всех комиссиях, необходимых для расчёта profitability.

Она отвечает за:

- aggregator fees;
- protocol fees;
- integrator fees;
- gas;
- rebates;
- другие подтверждённые расходы;
- fee applicability;
- fee freshness;
- fee caching;
- batch/grouped fee requests;
- нормализацию provider-specific fee formats.

Главный принцип:

**Fee System должна получать необходимые комиссии заранее и повторно использовать актуальные данные, чтобы не выполнять одинаковые fee requests при каждом сканировании.**

---

## 2. Основные потребители

Fee System используется:

- Level 1 Scanner;
- Level 2 Scanner;
- Profit Calculator;
- Scheduler;
- Maintenance;
- Aggregator Adapters.

---

## 3. Единая ответственность

Все внешние fee-related requests должны проходить через Fee System.

Scanner не должен самостоятельно определять комиссии.

---

## 4. Resource Manager

Все внешние requests Fee System выполняются через Resource Manager.

Это относится к:

- fee API;
- gas API;
- conversion API;
- provider-specific fee endpoints.

---

## 5. Fee Categories

Минимально поддерживать:

- AGGREGATOR_FEE;
- PROTOCOL_FEE;
- INTEGRATOR_FEE;
- GAS;
- REBATE;
- OTHER_COST.

---

## 6. Fee Component

Каждая комиссия должна быть представлена normalized Fee Component.

Минимально:

- type;
- amount;
- currency;
- source;
- applicability;
- status;
- timestamp;
- freshness;
- included_in_quote.

---

## 7. Fee Status

Минимально:

- AVAILABLE;
- UNKNOWN;
- UNSUPPORTED;
- EXPIRED;
- ERROR.

---

## 8. UNKNOWN

UNKNOWN означает:

система не располагает достоверным значением комиссии.

UNKNOWN не равняется zero.

---

## 9. UNSUPPORTED

UNSUPPORTED означает:

данный provider/network/operation не поддерживает соответствующий fee mechanism.

Если policy разрешает считать отсутствие комиссии подтверждённым отсутствием cost:

результат может быть нормализован как zero с явным статусом и source.

---

## 10. EXPIRED

EXPIRED означает:

ранее полученная fee больше не считается достаточно свежей.

Она не должна использоваться для confirmation, если policy требует актуальную fee.

---

## 11. ERROR

ERROR означает:

при получении fee произошла ошибка.

Это не означает:

fee = 0.

---

## 12. Fee Source

Каждая fee должна иметь источник.

Например:

- aggregator API;
- protocol data;
- blockchain RPC;
- configuration;
- external market data.

---

## 13. Fee Timestamp

Каждая fee должна иметь:

- fetched_at;
- effective_at, если provider предоставляет;
- expiration/freshness information.

---

## 14. Fee Freshness

Fee System должна определять, считается ли fee актуальной.

Freshness policy должна быть configurable.

---

## 15. Fee Reuse

Если актуальная fee уже существует:

**не выполнять повторный внешний request только потому, что начался новый scan.**

Это является обязательным правилом.

---

## 16. Проверка при запуске

При запуске приложения Fee System должна определить, какие fee data необходимы текущей конфигурации.

Необходимые данные должны быть получены заранее.

---

## 17. Scheduled Fee Refresh

Fee System должна поддерживать scheduled refresh.

Refresh выполняется по Scheduler.

Это позволяет обновлять комиссии независимо от каждого отдельного scan.

---

## 18. Startup + Daily

Для Fee System должна поддерживаться как минимум следующая политика:

- startup;
- daily.

Startup используется для первоначального получения необходимых fee data.

Daily используется для регулярного обновления.

---

## 19. Daily Interval

Daily refresh должен позволять задавать:

- период в днях;
- время запуска.

Например:

- каждые 1 день;
- каждые 2 дня;
- каждые 3 дня;
- выбранное время.

---

## 20. Ночное обновление

Время scheduled refresh должно быть configurable.

Пользователь должен иметь возможность выбрать ночное время.

Например:

02:00.

---

## 21. Scheduler Responsibility

Fee System не должна самостоятельно создавать бесконечный timer loop.

Scheduler запускает соответствующий Fee Refresh Task.

---

## 22. Startup Refresh

Startup refresh должен определить:

- enabled networks;
- enabled aggregators;
- configured tokens;
- required operations;
- required fee types.

После этого получить необходимые данные.

---

## 23. Daily Refresh

Daily refresh должен обновлять только те fee data, которые действительно необходимы текущей конфигурации.

Не запрашивать комиссии для отключённых:

- networks;
- aggregators;
- operations.

---

## 24. Fee Dependency Discovery

Fee System должна определить dependencies.

Например:

для конкретного aggregator/network/operation может потребоваться:

- aggregator fee;
- gas;
- protocol fee.

---

## 25. No Blind Full Discovery

Не выполнять полную fee discovery для всех существующих комбинаций, если они не используются Monik.

Discovery ограничивается активной configuration.

---

## 26. Grouping

Если provider API позволяет получить несколько fee values одним request:

Fee System должна использовать batch/grouped request.

Это необходимо для уменьшения количества внешних API requests.

---

## 27. Batch Preference

При прочих равных:

batch request предпочтительнее множества одинаковых individual requests.

---

## 28. Grouping Without Batch API

Если provider не поддерживает batch endpoint:

Fee System может логически группировать получение данных.

Но не создавать фиктивный batch request.

---

## 29. Fee Snapshot

Актуальные fee data должны храниться как snapshot.

Snapshot должен иметь version/revision.

---

## 30. Snapshot Contents

Fee snapshot должен содержать:

- provider;
- network;
- operation;
- token/context;
- fee components;
- fetched_at;
- freshness;
- source;
- version.

---

## 31. Fee Context

Fee context должен быть однозначно определён.

Например:

provider
+
network
+
operation
+
route/context

Конкретный набор ключей зависит от того, от чего реально зависит fee.

---

## 32. Route-dependent Fee

Если fee зависит от route:

fee data должна быть привязана к route fingerprint или соответствующему normalized route context.

---

## 33. Route-independent Fee

Если fee не зависит от route:

не привязывать её искусственно к каждому route.

Это позволяет повторно использовать одну fee data.

---

## 34. Amount-dependent Fee

Если fee зависит от amount:

она не может быть универсальной для всех amounts.

Fee System должна учитывать amount context.

---

## 35. Percentage Fee

Если fee является percentage:

Fee System должна хранить:

- rate;
- base type;
- source;
- applicability.

---

## 36. Fixed Fee

Если fee является fixed:

Fee System должна хранить:

- fixed amount;
- currency;
- applicability;
- source.

---

## 37. Fee Formula

Fee System не должна самостоятельно рассчитывать profitability.

Она только предоставляет normalized fee information.

Profitability рассчитывает Profit Calculator.

---

## 38. Included in Quote

Каждая fee должна иметь:

- included_in_quote = true;
- included_in_quote = false;
- included_in_quote = unknown.

---

## 39. Double Counting Prevention

Если fee уже включена в quote:

Profit Calculator не должен вычитать её повторно.

Fee System обязана передать корректный inclusion status.

---

## 40. Gas

Gas является отдельным cost component.

Fee System отвечает за получение:

- gas estimate;
- gas token;
- network;
- source;
- timestamp.

---

## 41. Gas Context

Gas context должен учитывать:

- network;
- operation;
- route, если gas зависит от route;
- amount, если gas зависит от amount.

---

## 42. Gas Estimate

Если provider предоставляет gas estimate непосредственно вместе с quote:

Fee System/Adapter должна сохранить его как соответствующий gas source.

---

## 43. Gas from Blockchain

Если gas необходимо получать через blockchain/RPC:

RPC request также проходит через Resource Manager.

---

## 44. Gas Conversion

Если gas выражен в native token, Fee System предоставляет необходимые данные для conversion.

Сам conversion выполняется соответствующей conversion/market-data subsystem.

---

## 45. Gas Freshness

Gas data должна иметь отдельную freshness policy.

Gas обычно может требовать более частого обновления, чем редко меняющиеся configuration fees.

---

## 46. Fee Cache

Fee System должна поддерживать controlled fee cache/snapshot storage.

Это **не quote cache**.

Quote caching запрещено использовать для замены свежих trading quotes.

Fee data может переиспользоваться согласно freshness policy.

---

## 47. Fee Cache Key

Cache key должен учитывать все параметры, от которых зависит fee.

Например:

- provider;
- network;
- operation;
- token;
- route context;
- amount class, если применимо.

---

## 48. Stale Fee

Stale fee может использоваться только если соответствующая policy прямо разрешает это.

Для Level 2 confirmation stale critical fee не должна считаться актуальной.

---

## 49. Missing Fee

Если обязательная fee отсутствует:

Fee System возвращает UNKNOWN/ERROR.

Не создавать synthetic zero.

---

## 50. Rebate

Rebate является отдельным component.

Например:

aggregator_fee = 0.20
rebate = 0.05

Оба значения сохраняются отдельно.

---

## 51. Rebate Applicability

Rebate должен иметь:

- source;
- applicability;
- validity;
- timestamp.

---

## 52. Expired Rebate

Expired rebate не должна автоматически применяться к новой opportunity.

---

## 53. Protocol Fee

Protocol fee должна быть получена из надёжного source.

Она не должна быть hard-coded в Calculator.

---

## 54. Integrator Fee

Если Monik использует integrator fee:

Fee System должна передавать её явно.

Если Monik не использует такую fee:

не создавать скрытый cost.

---

## 55. Other Cost

Дополнительные расходы должны быть представлены как отдельные components.

Каждый component должен иметь source и applicability.

---

## 56. Currency

Каждая fee должна иметь currency.

Не использовать неявное предположение о currency.

---

## 57. Decimal

Все fee amounts должны передаваться как Decimal.

Float запрещён для финансовых значений.

---

## 58. Raw Amount

Blockchain raw fee amounts должны сохраняться как integer до conversion через decimals.

---

## 59. Token Decimals

Decimals берутся из Token Registry/normalized token metadata.

Не hard-code decimals внутри Fee System.

---

## 60. Normalization

Provider-specific fee formats должны быть преобразованы в единый normalized Fee Component.

---

## 61. Provider-specific Logic

Provider-specific parsing находится в Aggregator Adapter.

Fee System получает normalized result.

---

## 62. Fee Applicability

Каждая fee должна явно указывать:

к какой операции она применяется.

Например:

- BUY;
- SELL;
- both;
- route-specific;
- network-specific.

---

## 63. Fee Scope

Fee scope может быть:

- request;
- transaction;
- route;
- operation;
- amount;
- network.

Scope должен быть явно указан.

---

## 64. Fee Multiplication

Fixed fee нельзя автоматически умножать на:

- количество legs;
- количество tokens;
- количество amounts.

Множитель определяется только подтверждённой policy.

---

## 65. Multi-leg Route

Если разные legs имеют разные fees:

каждая fee сохраняется отдельно.

Profit Calculator агрегирует их согласно applicability.

---

## 66. Fee Request Deduplication

Одинаковые fee requests не должны отправляться повторно одновременно.

Использовать in-flight deduplication, если requests полностью совместимы.

---

## 67. Concurrent Consumers

Если Level 1 и Level 2 одновременно запрашивают одну актуальную fee:

они должны иметь возможность использовать один общий in-flight request.

---

## 68. Level 2 Priority

Если fee data нужна для Level 2 confirmation и её нет:

request получает Level 2-related priority через Resource Manager.

---

## 69. Level 1 Priority

Fee refresh для Level 1 имеет обычный scanner priority.

---

## 70. Scheduled Refresh Priority

Scheduled maintenance refresh имеет maintenance priority.

Он не должен вытеснять Level 2 confirmation.

---

## 71. Refresh Failure

Если scheduled refresh не удался:

предыдущая fee snapshot не должна автоматически удаляться.

Она сохраняется с соответствующим freshness/status.

---

## 72. Repeated Refresh Failure

При повторяющихся failures:

Resource Manager применяет retry/circuit-breaker policy.

Fee System не создаёт собственный бесконечный retry loop.

---

## 73. Provider Outage

Provider outage не означает:

fee = 0.

Если актуальная fee недоступна:

status остаётся UNKNOWN/ERROR.

---

## 74. Provider Recovery

После восстановления provider:

Fee System должна обновить соответствующие snapshots согласно Scheduler/priority policy.

---

## 75. Fee Data Version

Каждый snapshot должен иметь version/revision.

Это позволяет определить, какая именно fee data использовалась при расчёте.

---

## 76. Calculation Reference

Profit Calculator должен иметь возможность ссылаться на fee snapshot/version, использованный при расчёте.

---

## 77. Audit

Для Level 2 confirmation должна сохраняться возможность восстановить:

- fee source;
- fee amount;
- fee currency;
- fee timestamp;
- fee snapshot version;
- applicability;
- inclusion status.

---

## 78. Database

SQLite может хранить fee snapshots согласно утверждённой retention policy.

Не требуется хранить бесконечную историю каждой одинаковой fee.

---

## 79. Retention

Fee history должна храниться только в объёме, необходимом для:

- audit;
- diagnostics;
- confirmed calculations;
- debugging;
- approved history policy.

---

## 80. No Telegram Logic

Fee System не форматирует Telegram notifications.

---

## 81. No Scanner Logic

Fee System не:

- создаёт Opportunities;
- выбирает routes;
- запускает Level 1;
- запускает Level 2.

---

## 82. No Profitability Logic

Fee System не определяет:

- profitable;
- unprofitable;
- threshold passed.

Это responsibility Profit Calculator.

---

## 83. Scheduler Integration

Scheduler должен уметь запускать:

- startup fee refresh;
- daily fee refresh;
- manual fee refresh, если предусмотрено.

---

## 84. Manual Refresh

Архитектура должна позволять принудительно обновить fee data.

Manual refresh также проходит Resource Manager.

---

## 85. Configuration

Configuration должна позволять задавать:

- startup enabled/disabled;
- daily enabled/disabled;
- interval_days;
- refresh_time;
- freshness policy;
- provider-specific fee policies.

---

## 86. Night Refresh

Пользователь должен иметь возможность установить refresh_time на ночное время.

Например:

02:00.

---

## 87. Disabled Provider

Если provider отключён:

Fee System не должна обновлять его fee data.

---

## 88. Disabled Network

Если network отключена:

Fee System не должна выполнять для неё scheduled refresh.

---

## 89. Disabled Operation

Если operation не используется:

не выполнять fee discovery для неё.

---

## 90. Metrics

Fee System должна собирать:

- refresh started;
- refresh completed;
- refresh failed;
- fee requests;
- grouped/batch requests;
- reused snapshots;
- cache hits;
- cache misses;
- stale data;
- unknown fees;
- fee request latency.

---

## 91. Efficiency Metrics

Отдельно измерять:

- сколько внешних requests было предотвращено reuse;
- сколько requests объединено в batch;
- сколько duplicate requests предотвращено;
- сколько fee values получено одним request.

---

## 92. Testing

Обязательно тестировать:

- startup refresh;
- daily refresh;
- interval days;
- refresh time;
- fee freshness;
- fee reuse;
- batch;
- grouping;
- in-flight deduplication;
- unknown fee;
- expired fee;
- provider outage;
- gas;
- rebates;
- route-dependent fees;
- amount-dependent fees;
- included-in-quote;
- double-count prevention;
- Decimal precision.

---

## 93. Critical Invariants

Fee System никогда не должна:

1. считать UNKNOWN fee равной zero;

2. выполнять одинаковый fee request при каждом scan, если актуальная data уже существует;

3. использовать stale critical fee для Level 2 confirmation;

4. дважды учитывать fee;

5. выполнять requests в обход Resource Manager;

6. самостоятельно рассчитывать profitability;

7. самостоятельно выбирать route;

8. выполнять swap;

9. создавать Opportunity;

10. логировать secrets;

11. считать provider outage отсутствием комиссии;

12. удалять последнюю валидную snapshot только из-за неудачного refresh.

---

## 94. Главный принцип

Fee System должна обеспечить:

**актуальные, нормализованные и повторно используемые данные о комиссиях при минимальном количестве внешних запросов.**

Особенно важно:

**не получать все комиссии заново при каждом Level 1 или Level 2 scan, если необходимые данные уже были получены при startup или scheduled refresh и всё ещё считаются актуальными.**
