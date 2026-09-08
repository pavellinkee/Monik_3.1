# MONIK — AGGREGATOR ADAPTERS

## 1. Назначение

Aggregator Adapter — изолированный модуль, который обеспечивает взаимодействие Monik с конкретным внешним агрегатором.

Для каждого агрегатора существует отдельный Adapter.

Текущие production adapters:

- 1inch;
- 0x;
- Velora;
- Uniswap.

Adapter скрывает API-specific детали от Core, Scanner, Scheduler и Calculator.

---

## 2. Главный принцип

Core должен работать с единым интерфейсом.

Он не должен знать:

- конкретные API endpoints;
- формат JSON конкретного агрегатора;
- названия специфичных API parameters;
- особенности authentication;
- особенности response parsing;
- конкретные правила комиссий.

Эти детали находятся внутри соответствующего Adapter.

---

## 3. Независимость Adapter

Каждый Adapter должен быть максимально независимым.

Изменение API 1inch не должно требовать изменения:

- Level 1 Scanner;
- Level 2 Scanner;
- Scheduler;
- Resource Manager;
- Calculator;
- Telegram.

В идеале изменяется только:

- 1inch Adapter;
- его тесты;
- при необходимости его configuration/policy.

---

## 4. Общий интерфейс

Все production adapters должны реализовывать общий интерфейс.

Интерфейс должен поддерживать необходимые операции:

- quote;
- route information;
- capabilities;
- fees;
- health;
- fixed-route validation/replay, если поддерживается.

Конкретные названия методов могут отличаться в реализации, но функциональная граница должна сохраняться.

---

## 5. Quote Request

Adapter получает normalized request от Core.

Request должен содержать необходимые данные:

- network;
- input token;
- output token;
- input amount;
- operation type;
- route, если требуется fixed-route;
- routing mode, если применимо;
- необходимые adapter-specific options.

Core не должен передавать raw HTTP parameters непосредственно в Adapter.

---

## 6. Quote Response

Adapter преобразует ответ API в единый normalized Quote.

Quote должен содержать как минимум:

- aggregator;
- network;
- input token;
- output token;
- input amount;
- output amount;
- route;
- route fingerprint;
- timestamp;
- request ID;
- status.

Дополнительные поля могут включать:

- gas;
- fees;
- price impact;
- routing mode;
- API metadata.

---

## 7. Raw API Response

Raw API response может сохраняться для diagnostics, если это необходимо.

Однако Core не должен зависеть от raw response.

Не передавать raw JSON дальше по архитектуре как основной источник данных.

---

## 8. Response Normalization

Adapter обязан преобразовать API-specific response в общий внутренний формат.

Например, если один API называет поле:

`amountOut`

а другой:

`toAmount`

Core в обоих случаях получает:

`output_amount`

Такая нормализация является обязанностью Adapter.

---

## 9. Amount Precision

Adapter обязан корректно преобразовывать token amounts.

Raw blockchain amounts должны сохраняться как integer.

Не использовать float при преобразовании финансовых значений.

Decimals должны определяться из token metadata/configuration.

---

## 10. Invalid Response

Если API response:

- malformed;
- неполный;
- содержит невозможные значения;
- не соответствует ожидаемой schema;

Adapter не должен создавать валидный Quote.

Он должен вернуть соответствующую Data Error.

---

## 11. API Error

Adapter должен нормализовать API errors.

Минимально необходимо различать:

- Temporary;
- Permanent;
- Data;
- Authentication;
- Rate Limit;
- Unsupported.

Если API предоставляет machine-readable error code, сохранять его.

---

## 12. HTTP Status

Adapter должен корректно обрабатывать:

- 2xx;
- 3xx, если применимо;
- 4xx;
- 429;
- 5xx.

HTTP 429 должен передаваться Resource Manager с информацией Retry-After, если она предоставлена.

---

## 13. Rate Limits

Adapter должен сообщать Resource Manager информацию о rate-limit особенностях API, если они известны.

Adapter не должен самостоятельно создавать бесконечный retry loop.

Resource Manager является центральной точкой контроля request rate.

---

## 14. Authentication

Authentication должна быть полностью изолирована внутри Adapter/client layer.

API keys не должны:

- находиться в source code;
- передаваться через бизнес-логику;
- записываться в logs.

Credentials должны поступать через безопасную configuration/environment mechanism.

---

## 15. Network Support

Каждый Adapter должен явно предоставлять информацию о поддерживаемых сетях.

Например:

- Polygon;
- Ethereum;
- другие поддерживаемые сети.

Нельзя предполагать поддержку сети только потому, что API принимает соответствующий network ID.

Поддержка должна быть подтверждена актуальной официальной документацией.

---

## 16. Polygon

Polygon является обязательной поддерживаемой сетью Monik.

Для каждого Adapter необходимо отдельно проверить:

- поддерживает ли он Polygon;
- какой network identifier используется;
- какие endpoints используются;
- какие ограничения действуют;
- какие routing modes доступны.

---

## 17. Token Support

Adapter должен позволять определить поддержку токена в соответствующей сети.

Capability Registry использует эту информацию.

Не выполнять полную token discovery перед каждым Level 1 scan.

---

## 18. Operation Support

Adapter должен уметь определить поддержку:

- BUY;
- SELL;
- fixed-route;
- routing mode;
- fee model.

Если операция не поддерживается:

Adapter возвращает:

`UNSUPPORTED`

а не timeout.

---

## 19. Capabilities

Adapter должен предоставлять capability information в нормализованной форме.

Минимально:

- supported networks;
- supported tokens, если API позволяет определить;
- BUY support;
- SELL support;
- fixed-route support;
- routing modes;
- fee capabilities.

---

## 20. Capability Discovery

Capability discovery выполняется:

- при startup;
- или при scheduled maintenance.

Не выполнять полный capability discovery перед каждым scan.

Runtime errors могут служить сигналом для maintenance/health subsystem, но не должны автоматически запускать полный discovery перед каждым запросом.

---

## 21. Health Check

Adapter должен предоставлять health information.

Health check может проверять:

- доступность API;
- authentication;
- network endpoint;
- базовую корректность ответа.

Health failure не означает автоматически unsupported.

---

## 22. Fixed Route

Adapter должен явно сообщать:

поддерживает ли API воспроизведение или проверку конкретного маршрута.

Если fixed-route поддерживается:

Adapter обязан принимать route snapshot/route parameters.

Если fixed-route не поддерживается:

Adapter должен сообщить:

`FIXED_ROUTE_UNSUPPORTED`

Нельзя молча выбрать другой маршрут.

---

## 23. Route Extraction

Adapter отвечает за извлечение route из API response.

Route должен быть преобразован в нормализованный внутренний объект.

Не хранить route только как произвольную строку.

---

## 24. Route Snapshot

Route snapshot должен содержать достаточно информации для Level 2.

Минимально:

- aggregator;
- network;
- input token;
- output token;
- routing mode;
- pools/legs, если доступны;
- route parameters;
- relevant API parameters;
- route fingerprint.

---

## 25. Route Fingerprint

Adapter передаёт данные, необходимые для создания deterministic route fingerprint.

Fingerprint должен быть одинаковым для одинакового маршрута.

Изменение существенного параметра маршрута должно менять fingerprint.

---

## 26. Routing Mode

Routing mode должен быть частью route identity.

Например:

- Uniswap V2;
- Uniswap V3;
- Uniswap V4;
- UniswapX Dutch V2;
- UniswapX Dutch V3;
- UniswapX Priority.

Если конкретный mode недоступен у агрегатора:

не создавать фиктивный mode.

---

## 27. Uniswap Adapter

Uniswap Adapter должен отдельно учитывать доступные официальные routing mechanisms.

Classic и UniswapX не должны молча объединяться в один route type.

Если API различает routing modes:

это различие должно сохраняться в normalized model.

---

## 28. Quote Freshness

Adapter должен выполнять реальный API request для каждого нового quote, если Core требует свежую котировку.

Не возвращать старый quote из внутреннего долгосрочного cache вместо fresh request.

---

## 29. No Long-term Quote Cache

Aggregator Adapter не должен создавать долгосрочный cache котировок для подмены свежих requests.

Исторические данные могут использоваться для:

- diagnostics;
- statistics;
- debugging.

Они не являются заменой fresh quote.

---

## 30. Request Metadata

Каждый API request должен иметь внутренний metadata/context.

Минимально:

- request ID;
- task ID;
- aggregator;
- network;
- operation;
- timestamp.

Это необходимо для tracing и diagnostics.

---

## 31. Resource Manager Integration

Adapter не должен самостоятельно открывать неконтролируемое HTTP соединение вне Resource Manager.

Перед request Adapter/client должен получить разрешение соответствующего Resource Manager flow.

Архитектура может реализовать это через отдельный API client layer, но внешний request всё равно должен проходить через Resource Manager.

---

## 32. HTTP Client

Каждый Adapter может использовать общий HTTP client infrastructure.

Общий client должен обеспечивать:

- timeout;
- headers;
- connection pooling;
- response handling;
- request IDs;
- error normalization.

API-specific parameters остаются внутри конкретного Adapter.

---

## 33. Timeout

Каждый request должен иметь ограниченный timeout.

Не использовать бесконечный timeout.

Timeout должен классифицироваться согласно общей Error Policy.

---

## 34. Response Validation

Adapter обязан проверять обязательные response fields до создания Quote.

Например:

- output amount;
- route;
- relevant token;
- network;
- request correlation.

Отсутствующие критические данные → Data Error.

---

## 35. Token Mismatch

Если API response содержит token, не соответствующий ожидаемому:

Adapter должен отклонить response.

Не пытаться автоматически исправить результат.

---

## 36. Network Mismatch

Если response относится к другой сети:

Adapter должен отклонить response.

Нельзя использовать quote из другой сети.

---

## 37. Amount Mismatch

Если response не соответствует requested input amount:

Adapter должен проверить, является ли это допустимым поведением API.

Если это не предусмотрено API:

response считается invalid.

---

## 38. Fees

Adapter отвечает за получение raw fee information.

Он не должен самостоятельно рассчитывать итоговую profitability.

Fee subsystem получает normalized fee data.

---

## 39. Fee Types

Adapter должен по возможности различать:

- aggregator fee;
- protocol fee;
- integrator fee;
- gas;
- other known costs.

Если API предоставляет только aggregate fee:

сохранять aggregate fee с соответствующим type.

Не придумывать отсутствующие компоненты.

---

## 40. Fee Unknown

Если API не предоставляет необходимую комиссию:

Adapter должен вернуть:

`UNKNOWN`

а не:

`0`.

---

## 41. Fee Policy

Aggregator-specific fee rules должны находиться в отдельном Fee Policy/Adapter layer.

Scanner не должен содержать:

`if aggregator == ...`

для расчёта комиссии.

---

## 42. Изменение комиссии

Если агрегатор изменит правила комиссии:

необходимо иметь возможность изменить соответствующую policy без переписывания:

- Level 1;
- Level 2;
- Scheduler;
- Resource Manager;
- Calculator.

В типичном случае изменение должно затрагивать только:

- соответствующий Adapter;
- Fee Policy;
- tests;
- configuration, если это необходимо.

---

## 43. Fee Discovery

Если API позволяет получить fee information отдельным запросом:

этот запрос выполняется через Resource Manager.

Fee discovery выполняется:

- при startup;
- при scheduled maintenance;
- или при необходимости согласно policy.

---

## 44. Fee Batching

Если API позволяет получить несколько fee values одним request:

Adapter/Fee subsystem должен использовать batching.

Не выполнять несколько отдельных requests, если один официальный API request способен безопасно предоставить ту же информацию.

---

## 45. Batch Accounting

Если API считает каждый элемент batch как отдельный rate-limit unit:

Resource Manager должен учитывать это.

Batch не считается автоматически одним request для rate-limit accounting.

---

## 46. Gas

Adapter должен предоставлять gas estimate, если соответствующий API его предоставляет.

Если gas рассчитывается отдельной subsystem:

Adapter передаёт необходимые данные этой subsystem.

---

## 47. Gas Currency

Если gas указан в native token:

Adapter должен явно сообщать:

- gas amount;
- gas token;
- network.

Не смешивать gas в разных единицах.

---

## 48. Price Impact

Если API предоставляет price impact:

Adapter может сохранять его в normalized Quote.

Price impact не должен самостоятельно считаться причиной отказа, если это не установлено отдельной business policy.

---

## 49. Slippage

Если API требует slippage parameter:

Adapter должен корректно передавать его согласно официальной документации.

Не применять произвольное значение внутри Scanner.

---

## 50. Fixed Route Validation

Для Level 2 Adapter должен уметь:

- воспроизвести fixed route;
- или проверить route согласно официальным возможностям API.

Если это невозможно:

вернуть:

`FIXED_ROUTE_UNSUPPORTED`

или соответствующий normalized error.

---

## 51. Route Mismatch

Если API возвращает маршрут, отличающийся от requested fixed route:

Adapter должен сообщить:

`ROUTE_MISMATCH`

Не считать такой результат подтверждением исходного route.

---

## 52. Alternative Route

Если API при fixed-route request предлагает другой маршрут:

Adapter не должен молча принимать его.

Он может сохранить информацию для diagnostics.

Основной Level 2 result остаётся неподтверждённым для исходного маршрута.

---

## 53. API Version

Adapter должен быть изолирован от конкретной версии API настолько, насколько это возможно.

Если API version меняется:

не менять общий Quote model без необходимости.

Добавить соответствующее преобразование внутри Adapter.

---

## 54. Official API Verification

Перед production implementation каждого Adapter необходимо проверить официальную документацию.

Нужно подтвердить:

- endpoint;
- authentication;
- supported networks;
- network IDs;
- token support;
- quote endpoint;
- routing model;
- fixed-route capability;
- fee model;
- rate limits;
- response schema.

Нельзя строить production Adapter на предположении.

---

## 55. 1inch

1inch Adapter должен быть отдельным production module.

Не смешивать его API logic с другими агрегаторами.

Все 1inch-specific:

- endpoints;
- parameters;
- authentication;
- response parsing;
- route parsing;
- fee logic;

должны находиться внутри 1inch Adapter/Policy layer.

---

## 56. 0x

0x Adapter должен быть отдельным production module.

Все 0x-specific API details должны находиться внутри соответствующего Adapter/Policy layer.

Core не должен знать формат 0x response.

---

## 57. Velora

Velora Adapter должен быть отдельным production module.

Все Velora-specific:

- endpoints;
- parameters;
- authentication;
- route handling;
- response parsing;
- fee handling;

должны быть изолированы.

---

## 58. Uniswap

Uniswap Adapter должен быть отдельным production module.

Он должен сохранять различия между поддерживаемыми routing modes.

Core получает normalized route information.

---

## 59. Adapter Contract Tests

Все adapters должны проходить общий contract test suite.

Contract tests должны проверять:

- quote interface;
- error normalization;
- capability interface;
- route normalization;
- fee normalization;
- fixed-route behavior;
- request metadata.

---

## 60. Adapter Unit Tests

Каждый Adapter должен иметь собственные unit tests.

Тестировать:

- request building;
- response parsing;
- malformed responses;
- API errors;
- rate limits;
- fees;
- route extraction;
- route mismatch;
- unsupported network;
- unsupported token;
- authentication failure.

---

## 61. Mock Responses

Mock API responses разрешены в tests.

Mocks должны соответствовать реальным documented response schemas.

Не создавать mock fields, которых не существует в production API, если тест не предназначен специально для проверки malformed response handling.

---

## 62. Integration Tests

Для production API должны существовать integration tests, где это возможно и безопасно.

Integration tests должны проверять:

- authentication;
- network support;
- quote request;
- response normalization;
- route extraction;
- fee extraction.

Не выполнять реальные swap transactions.

---

## 63. API Availability

Если внешний API временно недоступен во время integration test:

test должен корректно завершиться как external dependency failure, а не изменять production code для обхода проблемы.

---

## 64. No Fake Production Success

Запрещено считать Adapter production-ready только потому, что mock tests проходят.

Production readiness требует проверки реального API или документированного ограничения, если live verification невозможно.

---

## 65. Adapter Errors

Adapter должен возвращать структурированную ошибку.

Ошибка должна содержать по возможности:

- category;
- provider;
- provider code;
- HTTP status;
- message;
- request ID;
- retryable;
- retry-after.

Не включать secrets.

---

## 66. Adapter Logging

Логи Adapter должны содержать:

- aggregator;
- network;
- operation;
- request ID;
- task ID;
- duration;
- response status;
- normalized result/error.

Не записывать:

- API key;
- authorization header;
- private key;
- Telegram token;
- другие secrets.

---

## 67. Adapter Configuration

Конфигурация Adapter должна содержать только соответствующие ему параметры.

Например:

- enabled;
- API base URL, если configurable;
- credentials reference;
- supported networks;
- request timeout;
- provider-specific options.

Не помещать в Adapter configuration бизнес-логику Level 1.

---

## 68. Base URL

Production base URL должен быть взят из официальной документации или официальной конфигурации.

Не использовать случайные или непроверенные endpoints.

---

## 69. Environment

Adapter должен поддерживать как минимум:

- production;
- test/mock environment.

Environment selection должен выполняться через configuration.

Production credentials нельзя использовать в tests без явного безопасного механизма.

---

## 70. Adapter Lifecycle

Adapter должен иметь управляемый lifecycle:

- initialize;
- health check;
- ready;
- degraded;
- shutdown.

HTTP clients и connection pools должны корректно закрываться.

---

## 71. Startup

При startup Adapter:

1. загружает configuration;
2. проверяет credentials;
3. инициализирует HTTP client;
4. регистрирует capabilities;
5. выполняет необходимые health/capability checks;
6. сообщает readiness.

---

## 72. Shutdown

При shutdown Adapter:

- прекращает создание новых requests;
- завершает или отменяет допустимые operations;
- закрывает HTTP resources;
- освобождает connections.

---

## 73. Adapter Isolation

Один неисправный Adapter не должен автоматически останавливать остальные.

Например:

1inch Adapter DEGRADED

не означает:

0x Adapter DEGRADED.

Supervisor получает независимое состояние каждого Adapter.

---

## 74. Adapter Health State

Каждый Adapter должен иметь состояние:

- STARTING;
- READY;
- DEGRADED;
- DISABLED;
- FAILED;
- SHUTTING_DOWN.

FAILED одного Adapter не должен автоматически переводить всю систему в SAFE_STOP, если Core всё ещё способен работать корректно.

---

## 75. Unsupported vs Failed

Очень важно различать:

`UNSUPPORTED`

и:

`FAILED`.

UNSUPPORTED означает:

API/сеть/операция действительно не поддерживается.

FAILED означает:

поддержка существует, но runtime operation не удалась.

Не смешивать эти состояния.

---

## 76. Unsupported vs Rate Limited

RATE_LIMITED означает временное ограничение.

Это не:

UNSUPPORTED.

После cooldown ресурс может снова использоваться.

---

## 77. Unsupported vs Temporary Error

Timeout, 429, 5xx и connection failure не должны автоматически переводить capability в unsupported.

---

## 78. Data Integrity

Adapter обязан проверять:

- network;
- tokens;
- amounts;
- route;
- response consistency.

При сомнении использовать Data Error.

Не исправлять подозрительный response молча.

---

## 79. Security

Adapter должен соблюдать:

- secret isolation;
- safe logging;
- TLS verification;
- timeout;
- controlled redirects;
- input validation.

Не отключать TLS verification для production.

---

## 80. SSRF и URL Safety

Если API возвращает URL, который затем должен использоваться системой:

нельзя автоматически выполнять запрос по произвольному URL.

Разрешённые hosts должны контролироваться соответствующей configuration/policy.

---

## 81. Input Validation

Adapter должен валидировать:

- token addresses;
- network;
- amounts;
- route parameters;
- API-specific parameters.

Invalid input должен быть отклонён до отправки request, если это возможно.

---

## 82. Output Validation

Normalized Quote должен проходить validation перед передачей Core.

Не передавать потенциально повреждённые данные дальше.

---

## 83. Deterministic Normalization

Одинаковые API responses должны преобразовываться в одинаковый normalized model.

Normalization не должна зависеть от случайного порядка JSON fields.

---

## 84. No Business Logic Leakage

Adapter не должен решать:

- создавать ли Opportunity;
- проходить ли threshold;
- подтверждать ли Level 2;
- отправлять ли Telegram.

Adapter только предоставляет данные и технический статус операции.

---

## 85. No Scheduler Logic

Adapter не должен:

- создавать Scheduler tasks;
- менять priority;
- управлять очередью;
- выполнять retry loops самостоятельно.

---

## 86. No Resource Policy

Adapter может сообщать технические требования ресурса.

Но он не должен самостоятельно обходить или переопределять Resource Manager.

---

## 87. Adapter Update Policy

При изменении API агрегатора:

1. проверить официальную документацию;
2. определить affected Adapter;
3. обновить только необходимые provider-specific components;
4. обновить tests;
5. проверить contract tests;
6. выполнить integration tests;
7. проверить, что Core architecture не изменилась.

---

## 88. Изменение Fee Rules

При изменении комиссии агрегатора:

в первую очередь изменяется соответствующий:

- Fee Policy;
- Adapter fee extraction;
- configuration, если требуется.

Не переписывать Scanner.

---

## 89. Изменение Network Support

При добавлении новой сети:

в первую очередь обновляются:

- Adapter capabilities;
- network configuration;
- соответствующие tests.

Core Scanner не должен требовать отдельной ветки:

`if network == ...`

для каждой новой сети.

---

## 90. Изменение Routing Mode

При добавлении нового routing mode:

добавляется новый normalized routing mode и соответствующая Adapter logic.

Не изменять Core business logic, если новый mode соответствует существующему Adapter contract.

---

## 91. Общий принцип расширения

Добавление нового агрегатора должно требовать:

- новый Adapter;
- регистрация Adapter;
- provider-specific tests;
- provider-specific configuration;
- capability discovery.

Не должно требоваться переписывать:

- Level 1;
- Level 2;
- Scheduler;
- Resource Manager;
- Calculator;
- Telegram.

---

## 92. Новый агрегатор

Для нового Aggregator Adapter обязательный порядок:

1. изучить официальную документацию;
2. определить capabilities;
3. определить quote API;
4. определить route model;
5. определить fee model;
6. определить rate limits;
7. определить fixed-route support;
8. реализовать Adapter;
9. реализовать tests;
10. подключить Capability Registry;
11. проверить integration;
12. проверить взаимодействие с Resource Manager.

---

## 93. Critical Invariants

Aggregator Adapter никогда не должен:

1. выдавать invalid response как valid Quote;

2. превращать UNKNOWN fee в zero;

3. скрывать API errors;

4. менять route без явного разрешения;

5. обходить Resource Manager;

6. создавать uncontrolled retries;

7. записывать secrets в logs;

8. менять Capability Registry из-за временной ошибки;

9. выполнять бизнес-расчёт прибыли;

10. создавать Level 2 Job самостоятельно.

---

## 94. Главный принцип

Aggregator Adapter должен быть:

**единственной изолированной точкой, где Monik знает конкретные технические особенности внешнего агрегатора.**

Изменение API, комиссий, endpoints, response format или provider-specific routing rules должно локализоваться внутри соответствующего Adapter и его технических policy-модулей, не разрушая общую архитектуру Monik.
