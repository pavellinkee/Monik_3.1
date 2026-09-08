# MONIK — CAPABILITY REGISTRY

## 1. Назначение

Capability Registry — централизованная подсистема, которая хранит информацию о том, какие операции Monik может выполнять для конкретных:

- агрегаторов;
- сетей;
- токенов;
- торговых пар;
- routing modes;
- fixed routes;
- fee mechanisms.

Registry используется Scanner, Scheduler, Adapters и Maintenance.

Главный принцип:

**Capability Registry определяет, что технически поддерживается, но не определяет, выгодна ли операция.**

---

## 2. Основные задачи

Capability Registry отвечает за:

- discovery;
- хранение capabilities;
- обновление capabilities;
- проверку актуальности;
- быстрый lookup;
- различение SUPPORTED / UNSUPPORTED / UNKNOWN;
- связь capabilities с Adapter;
- сохранение результатов maintenance;
- передачу capability information Scanner.

---

## 3. Не проверять capabilities перед каждым scan

Level 1 и Level 2 не должны выполнять полный capability discovery перед каждым сканированием.

Это является обязательным требованием.

Иначе количество API requests будет неоправданно большим.

---

## 4. Когда выполняется discovery

Capability discovery выполняется:

- при startup;
- при scheduled maintenance;
- при необходимости после обнаружения серьёзного изменения API;
- по явному административному запросу, если такая функция предусмотрена.

---

## 5. Startup

При startup Registry должен загрузить сохранённые capabilities и определить, требуется ли их обновление.

Если capability information отсутствует или критически устарела:

необходимо выполнить соответствующий discovery до начала операций, которым эта информация необходима.

---

## 6. Daily Maintenance

Capability discovery может выполняться через Maintenance.

Maintenance поддерживает:

- startup;
- daily.

Для daily используются:

- interval_days;
- time.

Например:

mode = daily
interval_days = 3
time = 03:00

означает выполнение discovery каждые три дня в установленное время.

---

## 7. Capability State

Минимальные состояния:

- SUPPORTED;
- UNSUPPORTED;
- UNKNOWN;
- STALE;
- CHECKING;
- FAILED.

---

## 8. SUPPORTED

SUPPORTED означает, что capability подтверждена.

Например:

Polygon + AAVE + 1inch + BUY

может иметь:

SUPPORTED

---

## 9. UNSUPPORTED

UNSUPPORTED означает, что capability подтверждённо отсутствует.

Например:

- агрегатор официально не поддерживает сеть;
- routing mode не существует;
- операция не поддерживается.

UNSUPPORTED не должно означать временную ошибку API.

---

## 10. UNKNOWN

UNKNOWN используется, если система не может надёжно определить capability.

Например:

- discovery не завершён;
- API недоступен;
- документация/ответ не позволяет сделать вывод.

UNKNOWN нельзя трактовать как UNSUPPORTED.

---

## 11. STALE

STALE означает, что ранее известная capability существует, но срок её актуальности истёк или policy требует повторной проверки.

STALE не означает автоматически UNSUPPORTED.

---

## 12. CHECKING

CHECKING означает, что discovery/update для capability сейчас выполняется.

Другие consumers должны знать, что информация находится в процессе обновления.

---

## 13. FAILED

FAILED означает, что обновление capability завершилось ошибкой.

Причина должна быть сохранена.

Если существует последняя подтверждённая capability, она может использоваться согласно freshness policy.

---

## 14. Capability Identity

Каждая capability должна иметь deterministic identity.

Минимально:

- aggregator;
- network;
- capability type.

При необходимости:

- token;
- token pair;
- routing mode;
- route fingerprint.

---

## 15. Не добавлять лишние параметры

Capability key должен содержать только параметры, которые действительно влияют на capability.

Например, если поддержка BUY зависит только от:

- aggregator;
- network;

не нужно добавлять amount.

---

## 16. Token Capability

Если поддержка зависит от конкретного токена:

ключ должен включать token address.

Например:

aggregator + network + token + BUY

---

## 17. Pair Capability

Если API отдельно ограничивает конкретные торговые пары:

использовать:

network + aggregator + input_token + output_token + operation

---

## 18. Routing Mode Capability

Если поддержка зависит от routing mode:

routing mode должен быть частью capability identity.

Например:

Uniswap + Ethereum + V3

и:

Uniswap + Ethereum + V4

являются отдельными capabilities.

---

## 19. Fixed Route Capability

Registry должен отдельно хранить:

- FIXED_ROUTE_SUPPORTED;
- FIXED_ROUTE_UNSUPPORTED;
- UNKNOWN.

Это особенно важно для Level 2.

---

## 20. Level 2 Requirement

Если Level 1 создаёт Opportunity, а Level 2 требует проверки fixed route:

Registry должен позволять заранее определить, способен ли выбранный Adapter выполнить эту проверку.

Если fixed-route capability отсутствует:

Level 2 не должен молча менять маршрут.

---

## 21. Capability Types

Минимально поддерживать:

- NETWORK_SUPPORT;
- TOKEN_SUPPORT;
- PAIR_SUPPORT;
- BUY_SUPPORT;
- SELL_SUPPORT;
- FIXED_ROUTE_SUPPORT;
- ROUTING_MODE_SUPPORT;
- FEE_SUPPORT.

При необходимости могут добавляться другие capability types.

---

## 22. Aggregator Registry

Registry должен хранить список зарегистрированных Aggregator Adapters.

Для каждого:

- aggregator ID;
- adapter version;
- enabled;
- health;
- supported capabilities;
- configuration reference.

---

## 23. Adapter Registration

Новый Adapter должен регистрироваться централизованно.

Scanner не должен самостоятельно импортировать каждый агрегатор через отдельные hard-coded ветки.

---

## 24. Новый агрегатор

Добавление нового агрегатора должно включать:

1. новый Adapter;
2. регистрацию Adapter;
3. capability discovery;
4. configuration;
5. tests.

Core Scanner при этом не переписывается.

---

## 25. Network Registry

Registry должен поддерживать централизованный список известных сетей.

Для сети хранить:

- network ID;
- chain ID;
- native token;
- enabled;
- supported adapters.

---

## 26. Network Identity

Network identity должна быть deterministic.

Не использовать только display name.

Например:

polygon
ethereum
arbitrum

являются внутренними network IDs.

Chain ID хранится отдельно.

---

## 27. Token Identity

Token должен идентифицироваться как минимум:

network + contract address

Native asset должен иметь отдельный корректный representation.

---

## 28. Token Metadata

Registry может хранить:

- symbol;
- decimals;
- address;
- network;
- enabled;
- capability status.

Symbol не является уникальным идентификатором.

---

## 29. Contract Address

Для ERC-20 подобных токенов canonical identity — contract address в конкретной сети.

Нельзя определять токен только по:

USDT
AAVE
LINK

---

## 30. Address Normalization

Адреса должны нормализоваться в canonical form.

Сравнение адресов не должно зависеть от регистра, если blockchain semantics этого не требует.

---

## 31. Token List

Активный список токенов должен находиться в конфигурации/Registry.

Level 1 использует этот список.

Scanner не должен содержать собственный hard-coded список токенов.

---

## 32. Top Token Selection

Если используется ограничение top-N:

значение N должно находиться в конфигурации.

Например:

top_tokens = 30

Изменение top-N не должно требовать изменения Scanner code.

---

## 33. Capability Filtering

Перед созданием runtime scan tasks Scheduler/Scanner может использовать Registry для исключения явно неподдерживаемых комбинаций.

Например:

если:

1inch + Polygon + AAVE + BUY = UNSUPPORTED

не создавать BUY request для этой комбинации.

---

## 34. UNKNOWN Handling

Если capability:

UNKNOWN

нельзя автоматически считать:

UNSUPPORTED.

Поведение зависит от operation policy.

Для критической операции может потребоваться discovery перед использованием.

---

## 35. STALE Handling

Если capability:

STALE

система должна определить:

- можно ли временно использовать последнее подтверждённое состояние;
- или необходимо выполнить refresh.

Это определяется freshness policy.

---

## 36. Runtime API Error

Если quote API сообщает:

unsupported network/token/operation

Adapter должен передать это в Capability subsystem как сигнал.

Но один runtime error не должен автоматически менять capability на UNSUPPORTED без соответствующей validation policy.

---

## 37. Repeated Unsupported Signals

Если один и тот же unsupported signal повторяется и соответствует ожидаемому provider behavior:

Maintenance может обновить capability status.

Но обновление должно происходить контролируемо.

---

## 38. Temporary Errors

Следующие ошибки обычно не являются доказательством UNSUPPORTED:

- timeout;
- 429;
- 500;
- 502;
- 503;
- network failure;
- connection reset.

Они должны обрабатываться как runtime health/resource problems.

---

## 39. Authentication Error

Authentication failure не означает автоматически:

UNSUPPORTED.

Это отдельная проблема credentials/configuration.

---

## 40. Capability Freshness

Каждая capability должна иметь:

- discovered_at;
- updated_at;
- freshness/expiry information;
- source;
- version, если применимо.

---

## 41. Capability Source

Источник должен быть известен.

Например:

- OFFICIAL_API;
- ADAPTER_DISCOVERY;
- CONFIG;
- OFFICIAL_DOCUMENTATION;
- RUNTIME_SIGNAL.

---

## 42. Source Priority

При конфликте источников необходимо использовать deterministic priority.

Рекомендуемый порядок:

1. подтверждённый официальный API capability response;
2. актуальная Adapter discovery;
3. официальная documented policy;
4. configuration;
5. runtime signal.

Runtime signal не должен автоматически переопределять более надёжный источник без validation.

---

## 43. Versioning

Capability records должны иметь revision/version.

Это позволяет определить, какая версия capability использовалась при создании Opportunity.

---

## 44. Opportunity Snapshot

При создании Opportunity Level 1 должен сохранить capability context, который был использован для выбора route.

Это необходимо для diagnostics и воспроизводимости.

---

## 45. Level 2 Snapshot

Level 2 должен иметь доступ к capability snapshot Opportunity.

Но для фактической проверки может потребоваться актуальная runtime validation.

Старый snapshot не является гарантией текущего состояния API.

---

## 46. Capability Update и Existing Jobs

Если capability изменился после создания Opportunity:

существующий Level 2 Job не должен автоматически менять свой route.

Он должен:

- проверить возможность fixed-route;
- если невозможно — завершиться соответствующим status.

Нельзя автоматически заменить route.

---

## 47. Capability Update и Level 1

Если capability стала UNSUPPORTED:

новые Level 1 requests для этой комбинации не создаются.

Уже выполняющийся request не должен быть насильно прерван только из-за изменения Registry, если это небезопасно.

---

## 48. Capability Update и Level 2

Если capability стала UNSUPPORTED до запуска Level 2:

Level 2 не должен начинать невозможную проверку.

Если это обнаружено во время выполнения:

workflow должен получить соответствующий статус.

---

## 49. Discovery через Resource Manager

Все внешние capability requests проходят через Resource Manager.

Это относится к:

- startup;
- maintenance;
- manual refresh;
- health validation.

---

## 50. Discovery Priority

Capability discovery имеет низкий priority.

Порядок:

Level 2
>
Level 1 SELL
>
Level 1 BUY
>
Maintenance / Discovery

---

## 51. Discovery Batching

Если API позволяет определить capabilities для нескольких:

- tokens;
- networks;
- pairs;

одним request:

использовать batching.

---

## 52. Discovery Grouping

Если API не поддерживает batch endpoint:

можно группировать discovery tasks логически, чтобы Scheduler и Resource Manager эффективно управляли ими.

Нельзя объединять запросы, если это ухудшает точность или нарушает API contract.

---

## 53. Request Minimization

Registry должен минимизировать количество discovery requests.

Не выполнять:

- одинаковый discovery несколько раз;
- полный token discovery перед каждым scan;
- повторную network discovery без необходимости.

---

## 54. Discovery Deduplication

Если два workflow одновременно требуют обновить одну capability:

создаётся один active discovery operation.

Остальные consumers ожидают его результат.

---

## 55. Discovery Failure

Если discovery завершился Temporary Error:

- retry согласно Resource Manager policy;
- capability не становится UNSUPPORTED;
- старая valid capability может использоваться согласно freshness policy.

---

## 56. Discovery Permanent Error

Если discovery завершился Permanent Error:

- сохранить ошибку;
- не выполнять бесконечные retries;
- сохранить предыдущую valid capability, если она существует;
- установить соответствующий failure state.

---

## 57. Manual Refresh

Registry должен поддерживать контролируемый manual refresh.

Manual refresh должен:

- создавать отдельный maintenance task;
- проходить через Resource Manager;
- не запускать параллельные duplicate discovery;
- сохранять результат.

---

## 58. Full Refresh

Должна существовать возможность полного refresh всех необходимых capabilities.

Full refresh не должен выполняться автоматически перед каждым scan.

Он используется для:

- startup;
- maintenance;
- диагностики;
- изменения configuration;
- добавления нового aggregator/network/token.

---

## 59. Partial Refresh

Также должен поддерживаться refresh конкретного:

- aggregator;
- network;
- token;
- pair;
- routing mode.

Partial refresh предпочтительнее полного refresh, если известна конкретная изменившаяся capability.

---

## 60. Refresh Deduplication

Если одновременно запрошены:

full refresh

и:

partial refresh

Registry должен использовать механизм deduplication, чтобы не создавать ненужные одинаковые API requests.

---

## 61. Capability Storage

SQLite должна хранить:

- capability identity;
- status;
- source;
- version;
- discovered_at;
- updated_at;
- expires_at;
- error information;
- adapter reference.

---

## 62. Atomic Capability Update

Обновление capability должно быть атомарным.

Нельзя сохранить:

SUPPORTED

без соответствующих:

- source;
- timestamp;
- version;
- context.

---

## 63. Historical Capability

Исторические capability records могут сохраняться для:

- diagnostics;
- audit;
- анализа изменений;
- debugging.

Но runtime lookup должен использовать актуальную valid revision.

---

## 64. Capability Lookup

Lookup должен быть быстрым и не требовать внешнего API request.

Обычный Scanner lookup должен обращаться к локальному Registry/SQLite state.

---

## 65. External API Independence

Обычный:

get capability

не должен обращаться к внешнему API.

Внешний запрос выполняется только в рамках:

- discovery;
- refresh;
- maintenance;
- explicit validation.

---

## 66. Capability Cache

Registry фактически является локальным persistent source of truth для capability state.

Это не quote cache.

Capability data может сохраняться между запусками.

---

## 67. Не путать Capability и Quote Cache

Capability Registry может хранить:

- поддерживается ли token;
- поддерживается ли network;
- поддерживается ли routing mode.

Он не должен использоваться для хранения актуальных trading quotes.

---

## 68. Token Availability

Если token явно UNSUPPORTED:

Scanner не должен создавать runtime quote request для этого token/aggregator combination.

---

## 69. Pair Availability

Если pair явно UNSUPPORTED:

соответствующий scan task не создаётся.

---

## 70. Unknown Pair

Если pair UNKNOWN:

поведение определяется policy.

Если quote API способен безопасно проверить pair непосредственно в рамках обычного quote request:

можно выполнить quote.

Если для безопасности необходим отдельный discovery:

Scheduler может создать соответствующий discovery task.

---

## 71. Network Availability

Если network UNSUPPORTED:

никакие runtime quote requests для этого Adapter/network не создаются.

---

## 72. Routing Mode Availability

Если routing mode UNSUPPORTED:

route с этим mode не должен использоваться.

---

## 73. Fixed Route Availability

Если fixed route UNSUPPORTED:

Level 2 не должен считать такую проверку возможной.

Он не должен заменять route.

---

## 74. Fee Capability

Если fee capability UNKNOWN:

Fee System определяет, можно ли получить fee другим разрешённым способом.

Если нет:

profitability confirmation может быть невозможна.

---

## 75. Capability Conflict

Если два источника дают разные результаты:

Registry не должен молча выбирать случайный результат.

Он должен:

- применить source priority;
- сохранить conflict information;
- при необходимости запустить refresh.

---

## 76. Capability Conflict Safety

При неразрешённом конфликте:

не выбирать UNSUPPORTED только потому, что это более безопасно для API usage.

Также нельзя выбирать SUPPORTED без достаточного подтверждения.

Использовать:

UNKNOWN

до разрешения конфликта.

---

## 77. Capability Drift

Система должна позволять обнаруживать capability drift:

- API изменил network support;
- token перестал поддерживаться;
- routing mode изменился;
- fixed route стал недоступен;
- fee capability изменилась.

Drift должен быть виден через diagnostics.

---

## 78. Maintenance Report

После discovery Maintenance должен формировать результат:

- checked;
- supported;
- unsupported;
- unknown;
- failed;
- changed.

Этот результат может использоваться Supervisor и Telegram.

---

## 79. Changed Capabilities

Если capability изменилась:

система должна сохранить:

- previous state;
- new state;
- timestamp;
- source;
- reason.

---

## 80. No Automatic Route Migration

Изменение capability не должно автоматически переводить существующую Opportunity на другой route.

Route migration не является задачей Capability Registry.

---

## 81. Adapter Health vs Capability

Health и capability должны храниться отдельно.

Например:

Adapter:

DEGRADED

Capability:

SUPPORTED

Это допустимое состояние.

---

## 82. Resource State vs Capability

Resource Manager может сообщить:

RATE_LIMITED

при этом Registry остаётся:

SUPPORTED.

Не смешивать эти состояния.

---

## 83. Configuration vs Discovery

Configuration может ограничивать использование capability.

Например:

aggregator.enabled = false

Даже если Registry знает:

SUPPORTED.

В таком случае runtime Scanner не использует capability.

Но это не означает:

UNSUPPORTED.

---

## 84. Enabled State

Для Aggregator, Network и Token должны существовать независимые состояния:

- enabled;
- capability;
- health.

Например:

enabled = false
capability = SUPPORTED
health = READY

означает, что ресурс технически поддерживается, но пользователь его отключил.

---

## 85. Disabled State

DISABLED — это configuration state, а не capability state.

Не смешивать:

DISABLED

с:

UNSUPPORTED.

---

## 86. Registry API

Внутренний API Registry должен позволять:

- get;
- list;
- check;
- refresh;
- refresh_partial;
- register;
- update;
- get_history;
- get_status.

Конкретные названия методов могут отличаться.

---

## 87. Check

`check` должен выполнять локальный lookup.

Он не должен автоматически обращаться к внешнему API.

---

## 88. Refresh

`refresh` создаёт контролируемую discovery operation.

Она проходит через Scheduler и Resource Manager.

---

## 89. Register

`register` используется для:

- нового Adapter;
- нового Network;
- нового Token;
- нового Routing Mode.

Регистрация не должна автоматически означать SUPPORTED.

После регистрации состояние может быть:

UNKNOWN.

---

## 90. Update

`update` должен быть ограничен соответствующим authority/policy.

Runtime Scanner не должен самостоятельно изменять capability.

---

## 91. Security

Registry не должен хранить:

- API keys;
- private keys;
- Telegram tokens;
- другие secrets.

Он хранит только capability metadata.

---

## 92. Logging

Registry должен логировать:

- discovery;
- refresh;
- state changes;
- conflicts;
- errors;
- duration.

Не логировать secrets.

---

## 93. Metrics

Собирать:

- total capabilities;
- supported;
- unsupported;
- unknown;
- stale;
- failed;
- discovery duration;
- discovery requests;
- batch requests;
- duplicate discoveries prevented;
- changed capabilities.

---

## 94. Testing

Обязательно тестировать:

- capability lookup;
- registration;
- discovery;
- refresh;
- partial refresh;
- full refresh;
- deduplication;
- batching;
- stale state;
- unknown state;
- unsupported state;
- conflicts;
- source priority;
- persistence;
- recovery;
- runtime error signals.

---

## 95. Critical Invariants

Capability Registry никогда не должен:

1. выполнять полный discovery перед каждым scan;

2. считать UNKNOWN равным UNSUPPORTED;

3. считать temporary API error доказательством unsupported;

4. хранить quote cache вместо quote subsystem;

5. менять route существующей Opportunity;

6. обходить Resource Manager;

7. создавать duplicate discovery requests без необходимости;

8. смешивать capability с health;

9. смешивать capability с rate-limit state;

10. хранить secrets.

---

## 96. Главный принцип

Capability Registry должен обеспечить:

**быстрый локальный ответ на вопрос, поддерживается ли конкретная операция, без необходимости повторно обращаться к внешнему API при каждом сканировании.**

Актуальность capabilities поддерживается через:

**startup + scheduled maintenance + controlled refresh.**
