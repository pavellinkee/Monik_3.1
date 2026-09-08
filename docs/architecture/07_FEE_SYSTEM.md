# MONIK — FEE SYSTEM

## 1. Назначение

Fee System — отдельная подсистема Monik, отвечающая за получение, нормализацию, хранение и предоставление информации о комиссиях.

Она должна изолировать правила комиссий конкретных агрегаторов от:

- Level 1;
- Level 2;
- Scheduler;
- Resource Manager;
- Profit Calculator;
- Telegram.

Главный принцип:

**изменение правил комиссии агрегатора не должно требовать переписывания Scanner или Calculator.**

---

## 2. Основные задачи

Fee System отвечает за:

- fee discovery;
- fee updates;
- fee normalization;
- fee policy;
- fee storage;
- fee freshness;
- batching;
- grouping;
- fee applicability;
- unknown fee handling;
- передачу normalized fee data Calculator.

---

## 3. Источники комиссий

Комиссия может быть получена:

- непосредственно из quote API;
- отдельным fee endpoint;
- из configuration;
- из официально определённого правила агрегатора;
- через комбинацию этих источников.

Источник каждой комиссии должен быть известен системе.

---

## 4. Fee Types

Минимально поддерживать:

- AGGREGATOR_FEE;
- PROTOCOL_FEE;
- INTEGRATOR_FEE;
- GAS;
- OTHER_COST;
- UNKNOWN.

Если конкретный агрегатор предоставляет собственный тип комиссии, он должен быть преобразован в совместимый normalized type.

---

## 5. Fee Model

Каждая комиссия должна иметь структурированное представление.

Минимально:

- fee ID;
- aggregator;
- network;
- token;
- fee type;
- amount;
- currency;
- source;
- status;
- effective timestamp;
- discovered timestamp;
- expiry/freshness information, если применимо.

---

## 6. Fee Amount

Raw blockchain amounts должны храниться как integer.

Для денежных расчётов использовать Decimal.

Не использовать float для расчёта комиссии.

---

## 7. Currency

Каждая комиссия должна явно указывать единицу измерения.

Например:

- USDT;
- USDC;
- ETH;
- MATIC;
- native token;
- basis points;
- percentage.

Нельзя передавать в Calculator число комиссии без указания единицы.

---

## 8. Percentage Fees

Если агрегатор предоставляет комиссию как процент:

хранить её в точном формате.

Например:

`0.5%`

не должен превращаться в неточное binary floating-point значение.

---

## 9. Basis Points

Если API использует basis points:

Fee System должна нормализовать их в единый внутренний формат.

Например:

`50 bps = 0.50%`

Конвертация должна выполняться точно.

---

## 10. Fixed Fees

Если агрегатор имеет фиксированную комиссию:

она должна храниться отдельно от percentage-based fee.

Calculator должен иметь возможность определить, является ли комиссия:

- fixed;
- percentage;
- dynamic;
- route-dependent;
- amount-dependent.

---

## 11. Dynamic Fees

Если комиссия зависит от:

- суммы;
- маршрута;
- сети;
- токена;
- API parameters;
- routing mode;

Fee System должна сохранять соответствующую зависимость.

Нельзя применять одну фиксированную комиссию ко всем операциям, если правила агрегатора этого не позволяют.

---

## 12. Route-dependent Fees

Если комиссия зависит от route:

Fee record должен быть связан с route fingerprint или необходимым route identity.

Комиссию одного маршрута нельзя автоматически применять к другому.

---

## 13. Network-dependent Fees

Если комиссия зависит от сети:

Fee data должна быть связана с network.

Например:

Polygon и Ethereum должны рассматриваться как разные fee contexts.

---

## 14. Token-dependent Fees

Если комиссия зависит от токена:

Fee data должна быть связана с соответствующим token context.

Нельзя использовать fee policy одного токена для другого без подтверждённого правила.

---

## 15. Unknown Fee

Если система не знает размер комиссии:

status:

`UNKNOWN`

Никогда не использовать:

`0`

в качестве значения по умолчанию.

---

## 16. Unknown Fee и Confirmation

Если неизвестная комиссия способна изменить profitability:

Level 2 не может получить полноценный:

`CONFIRMED`

только на основании результата без этой комиссии.

Статус определяется общей Confirmation Policy.

---

## 17. Zero Fee

`0` является допустимым значением только если:

- API явно сообщает zero fee;
- официальная policy агрегатора подтверждает отсутствие комиссии;
- или другое надёжное правило подтверждает zero fee.

Отсутствие информации не означает zero.

---

## 18. Fee Source

Каждая комиссия должна иметь source.

Например:

- QUOTE_API;
- FEE_API;
- CONFIG;
- OFFICIAL_POLICY;
- CALCULATED;
- UNKNOWN.

Источник необходим для диагностики и контроля достоверности.

---

## 19. Fee Confidence

Система должна позволять определить уровень достоверности fee data.

Минимально:

- CONFIRMED;
- DERIVED;
- UNKNOWN.

CONFIRMED означает, что fee data получена из надёжного источника для текущего контекста.

DERIVED означает, что значение рассчитано на основании подтверждённого правила.

UNKNOWN означает, что значение недостаточно надёжно для полноценного подтверждения.

---

## 20. Fee Discovery

Fee discovery выполняется отдельно от обычного scanning flow.

Основные моменты:

- startup;
- scheduled maintenance;
- controlled update.

Не выполнять полное fee discovery перед каждым Level 1 scan.

---

## 21. Startup Discovery

При startup Fee System должна определить необходимые fee rules для активных:

- агрегаторов;
- сетей;
- routing modes;
- других конфигурируемых contexts.

Если discovery невозможно завершить из-за временной ошибки:

система не должна автоматически считать fee равной нулю.

---

## 22. Scheduled Discovery

Fee rules должны обновляться во время Maintenance.

Maintenance поддерживает:

- startup;
- daily.

Для daily:

- interval_days;
- time.

Fee discovery должна использовать соответствующий Maintenance schedule.

---

## 23. Fee Freshness

Fee data должна иметь понятие freshness.

Если fee rule может измениться со временем:

система должна знать, когда она была получена и насколько долго её можно считать актуальной.

Не использовать бесконечно старые fee data.

---

## 24. Fee Expiration

Если конкретный API предоставляет TTL или время действия fee information:

использовать его.

Если TTL не предоставлен:

использовать policy, установленную для соответствующего fee source.

---

## 25. Expired Fee

Если fee data устарела:

она не должна автоматически использоваться как актуальная.

Система должна:

- обновить fee;
- либо обозначить её как stale/unknown;
- либо использовать безопасную policy.

---

## 26. Fee Update

При обновлении fee:

новое значение не должно уничтожать историческую информацию, если она нужна для diagnostics или audit.

Текущее значение должно быть однозначно определено.

---

## 27. Versioning

Fee rules должны иметь version или revision identifier.

Это позволяет определить:

- какая версия правила использовалась;
- когда она была получена;
- какой результат был рассчитан на её основе.

---

## 28. Fee Policy

Для каждого агрегатора может существовать отдельная Fee Policy.

Например:

`1inch Fee Policy`

`0x Fee Policy`

`Velora Fee Policy`

`Uniswap Fee Policy`

Policy отвечает за provider-specific interpretation.

---

## 29. Изоляция Fee Policy

Fee Policy не должна содержать:

- Level 1 logic;
- Level 2 scheduling;
- Telegram logic;
- resource locking;
- opportunity creation.

Она отвечает только за fee interpretation.

---

## 30. Изменение комиссии агрегатора

Если агрегатор изменил правила:

1. проверить актуальную официальную документацию;
2. определить, изменилось ли fee calculation;
3. изменить соответствующий Adapter/Fee Policy;
4. обновить tests;
5. выполнить fee discovery;
6. проверить Calculator integration.

Не переписывать Scanner.

---

## 31. Где должен происходить основной update

В нормальной ситуации изменение fee rules конкретного агрегатора должно локализоваться в:

- соответствующем Aggregator Adapter;
- соответствующем Fee Policy;
- тестах;
- configuration, если она используется.

Изменения в Core допускаются только если изменился общий контракт Fee System.

---

## 32. Batching

Если API позволяет получить несколько необходимых fee values одним request:

использовать batch.

Например, если для одного API request можно получить fee information для нескольких:

- tokens;
- networks;
- routes;
- operations;

не выполнять отдельный request для каждого элемента без технической необходимости.

---

## 33. Grouping

Если полноценный batch API отсутствует, Fee System должна группировать операции там, где это позволяет сократить количество requests без потери точности.

Grouping не должен создавать искусственные fee values.

---

## 34. Проверка batch

После batch response каждая fee должна пройти индивидуальную normalization/validation.

Ошибка одного элемента не должна автоматически превращать все остальные элементы batch в UNKNOWN, если API предоставляет корректные данные для них.

---

## 35. Resource Manager

Все fee API requests проходят через Resource Manager.

Это относится к:

- startup discovery;
- maintenance discovery;
- fee update;
- batch requests.

Fee System не должна открывать неконтролируемые внешние API requests.

---

## 36. Fee Discovery Priority

Fee discovery имеет более низкий priority, чем:

- Level 2;
- Level 1 SELL;
- Level 1 BUY.

Если fee discovery конкурирует за ресурс:

она должна ждать.

---

## 37. Fee Discovery и Scanner

Fee discovery не должна блокировать весь Scanner.

Если один fee request выполняется:

другие независимые scanning tasks должны продолжать работу, если Resource Manager позволяет это.

---

## 38. Fee Discovery Failure

Если fee discovery завершилась Temporary Error:

- выполнить retry согласно общей policy;
- не считать fee zero;
- не менять capability на unsupported.

---

## 39. Fee Discovery Permanent Error

Если fee API возвращает Permanent Error:

сохранить ошибку.

Не выполнять бесконечный retry.

Fee status может стать:

`UNKNOWN`

до исправления причины.

---

## 40. Fee API Rate Limits

Fee API requests подчиняются тем же ограничениям Resource Manager:

- concurrency;
- rate limits;
- Retry-After;
- cooldown;
- circuit breaker.

---

## 41. Fee API Unavailable

Если fee endpoint временно недоступен:

это не означает автоматически, что агрегатор не поддерживается.

Меняется только состояние fee source/resource.

---

## 42. Quote-provided Fees

Если quote API уже содержит актуальную комиссию:

Fee System должна уметь использовать её напрямую после validation.

Не делать отдельный fee request, если это не требуется для полноты или актуальности данных.

---

## 43. Avoid Duplicate Fee Requests

Если необходимая fee information уже получена в текущем допустимом context:

не выполнять повторный одинаковый запрос без необходимости.

Но нельзя использовать устаревшее значение только ради сокращения количества requests.

---

## 44. Fee Context

Каждая fee lookup должна иметь context.

Минимально:

- aggregator;
- network;
- token;
- route fingerprint, если требуется;
- routing mode;
- operation;
- amount, если комиссия amount-dependent.

---

## 45. Fee Key

Для хранения и поиска fee data использовать deterministic key.

Key должен учитывать все параметры, которые влияют на значение комиссии.

Например:

`aggregator + network + fee_type + routing_mode`

и дополнительные параметры при необходимости.

---

## 46. Нельзя чрезмерно обобщать Fee Key

Если fee зависит от amount:

amount должен участвовать в lookup context.

Если fee зависит от route:

route identity должен участвовать.

Если fee зависит только от aggregator:

не нужно искусственно добавлять irrelevant parameters.

---

## 47. Fee Applicability

Fee System должна определять, применяется ли конкретная комиссия к текущей операции.

Например:

- fee может применяться только к BUY;
- только к SELL;
- только к определённому routing mode;
- только к определённому token;
- только к определённой сети.

---

## 48. Fee Calculation

Fee System может выполнять provider-specific fee calculation.

Например:

percentage fee × amount.

Но итоговый financial aggregation выполняется Profit Calculator.

Fee System предоставляет Calculator точные normalized components.

---

## 49. Separation of Responsibilities

Fee System отвечает:

`Какова комиссия?`

Profit Calculator отвечает:

`Как эта комиссия влияет на прибыль?`

Scanner отвечает:

`Есть ли возможность?`

Scheduler отвечает:

`Когда её проверять?`

Resource Manager отвечает:

`Можно ли сейчас выполнить внешний request?`

---

## 50. Fee Aggregation

Если для одной операции существует несколько расходов:

Fee System должна вернуть их отдельными компонентами.

Например:

- aggregator fee;
- protocol fee;
- integrator fee.

Calculator может суммировать их в:

`total fees`

но исходные компоненты должны сохраняться.

---

## 51. Gas

Gas должен рассматриваться как отдельный cost component.

Не смешивать его с aggregator fee, если API предоставляет отдельную информацию.

Gas может быть передан Fee/Cost subsystem и затем Calculator.

---

## 52. Native Token Conversion

Если комиссия или gas выражены в native token, а profitability считается в другом token:

система должна использовать отдельный надёжный механизм conversion.

Нельзя произвольно считать:

`1 ETH = 1 USDT`

или другое фиктивное значение.

---

## 53. Conversion Failure

Если невозможно надёжно перевести fee/gas в единицу расчёта:

стоимость считается:

`UNKNOWN`

и соответствующий profitability result не должен считаться полностью подтверждённым.

---

## 54. Fee Snapshot

При Level 2 confirmation необходимо сохранять fee snapshot, использованный для расчёта.

Snapshot должен позволять определить:

- значение;
- тип;
- source;
- version;
- timestamp;
- applicability.

---

## 55. Historical Fee Data

Исторические fee records могут использоваться для:

- diagnostics;
- statistics;
- audit;
- анализа изменения правил.

Они не должны автоматически использоваться вместо актуальной fee information.

---

## 56. Fee Storage

SQLite должна хранить необходимые fee metadata.

Минимально:

- fee identity;
- provider;
- context;
- value;
- status;
- source;
- version;
- discovered_at;
- expires_at, если применимо.

---

## 57. Transactional Update

Обновление fee rule и её metadata должно быть атомарным.

Нельзя сохранить новое значение комиссии без соответствующего version/source metadata.

---

## 58. Concurrent Fee Update

Если startup и maintenance одновременно инициировали одну и ту же fee update:

должен существовать механизм deduplication.

Не выполнять два одинаковых discovery workflow одновременно без необходимости.

---

## 59. Fee Update Lock

Для одного fee context допускается только один активный update workflow, если параллельные обновления не дают технической выгоды.

---

## 60. Fee Request Deduplication

Если несколько Level 2 jobs одновременно требуют одинаковую fee information:

Fee System должна переиспользовать уже выполняющийся или недавно полученный допустимый fee update вместо запуска одинаковых requests.

---

## 61. Freshness vs Deduplication

Deduplication не должна приводить к использованию устаревшей информации.

Если текущий fee data ещё актуален:

использовать его.

Если устарел:

создать один update workflow и дать другим потребителям дождаться его результата.

---

## 62. Fee Update Failure with Multiple Consumers

Если один общий fee update завершился ошибкой:

все ожидающие consumers получают соответствующий failure/UNKNOWN status.

Не создавать десятки одинаковых retries.

Retry должен быть централизованным.

---

## 63. Fee System API

Внутренний интерфейс Fee System должен позволять:

- get_fee;
- get_fees;
- discover;
- refresh;
- validate;
- get_status;
- get_snapshot.

Конкретные названия методов могут отличаться.

---

## 64. get_fee

`get_fee` должен возвращать normalized fee result для одного context.

Результат должен указывать:

- value;
- status;
- source;
- timestamp;
- version.

---

## 65. get_fees

`get_fees` должен поддерживать получение нескольких fee values.

Если backend позволяет batching:

использовать его.

---

## 66. Fee Status

Минимально поддерживать:

- VALID;
- STALE;
- UNKNOWN;
- UPDATING;
- FAILED.

---

## 67. Fee Validation

Перед использованием fee необходимо проверить:

- context;
- currency;
- value;
- source;
- freshness;
- applicability.

Невалидная fee не передаётся Calculator как valid.

---

## 68. Negative Fee

Отрицательная комиссия не должна приниматься автоматически.

Если API действительно поддерживает rebate/negative fee:

это должно быть явно определено соответствующей Fee Policy.

В остальных случаях отрицательное значение является Data Error.

---

## 69. Rebate

Если агрегатор предоставляет rebate:

он должен быть представлен отдельно от обычной комиссии.

Calculator должен знать, является ли компонент:

- cost;
- rebate.

Не скрывать rebate внутри отрицательной комиссии без явного normalized type.

---

## 70. Fee Currency Mismatch

Если fee currency не соответствует ожидаемой:

Fee System не должна автоматически конвертировать её без надёжного conversion mechanism.

---

## 71. Precision

Fee calculations должны сохранять необходимую точность.

Не округлять fee раньше времени.

Округление выполняется только на presentation layer или в месте, где это требуется официальными правилами.

---

## 72. Rounding Rules

Если конкретный агрегатор использует специальные rounding rules:

они должны находиться в его Fee Policy.

Не распространять provider-specific rounding на остальные агрегаторы.

---

## 73. Fee Tests

Каждая Fee Policy должна иметь tests для:

- zero fee;
- fixed fee;
- percentage fee;
- dynamic fee;
- route-dependent fee;
- network-dependent fee;
- unknown fee;
- malformed fee;
- negative/rebate;
- rounding;
- precision.

---

## 74. Provider Fee Tests

Для каждого агрегатора необходимо тестировать:

- получение fee;
- normalization;
- source;
- applicability;
- version;
- fee update;
- изменённые правила.

---

## 75. Integration Tests

Где возможно, Fee System должна иметь integration tests с реальным API.

Проверять:

- текущую fee model;
- актуальные response fields;
- реальные units;
- fee availability;
- rate limits.

Не выполнять реальные swap transactions.

---

## 76. Документирование изменений

Если обнаружено изменение fee rules:

не изменять архитектурный документ автоматически.

Изменение должно быть отражено в:

- Adapter;
- Fee Policy;
- tests;
- configuration;

а утверждённая архитектура остаётся неизменной, если общий контракт не изменился.

---

## 77. Logging

Fee System должна логировать:

- fee lookup;
- discovery;
- update;
- source;
- context;
- duration;
- success/failure.

Не логировать secrets.

---

## 78. Metrics

Собирать:

- fee lookups;
- cache-like valid reuse count, если применяется;
- discovery requests;
- batch requests;
- duplicate requests prevented;
- unknown fees;
- stale fees;
- fee update failures;
- average discovery time.

---

## 79. No Hidden Defaults

Запрещено использовать скрытые значения:

- fee = 0;
- gas = 0;
- unknown currency = default currency;
- missing percentage = 0%.

Все отсутствующие критические значения должны быть явно обозначены.

---

## 80. Production Safety

Если Fee System не может надёжно определить обязательную комиссию:

лучше не подтвердить возможность.

Нельзя создавать ложную прибыльность за счёт предположения:

`fee = 0`.

---

## 81. Critical Invariants

Fee System никогда не должна:

1. превращать UNKNOWN fee в zero;

2. использовать stale fee как свежую без policy;

3. смешивать комиссии разных contexts;

4. применять route-specific fee к другому route;

5. обходить Resource Manager;

6. выполнять бесконечные retries;

7. скрывать provider-specific fee rules внутри Calculator;

8. менять Scanner при обычном изменении комиссии;

9. терять источник и version fee data;

10. использовать float для финансовых значений.

---

## 82. Главный принцип

Fee System должна обеспечить:

**актуальное, точное и однозначное представление всех известных расходов без ложного предположения, что неизвестная комиссия равна нулю.**

Если невозможно надёжно определить стоимость:

**Monik должен предпочесть не подтвердить возможность, чем подтвердить её с заниженными расходами.**
