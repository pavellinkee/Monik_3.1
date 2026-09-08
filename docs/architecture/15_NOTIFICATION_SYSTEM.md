# MONIK — NOTIFICATION SYSTEM

## 1. Назначение

Notification System — отдельная подсистема доставки подтверждённых результатов пользователю.

Она получает только уже подтверждённые opportunities и отвечает за их доставку через Telegram.

Notification System не выполняет поиск, повторную проверку или расчёт прибыльности.

---

## 2. Главный принцип

Notification System отвечает только за:

**что отправить и доставить сообщение.**

Она не отвечает за:

**найти opportunity, проверить opportunity или рассчитать opportunity.**

---

## 3. Источник данных

Основным источником для notification является подтверждённый Level 2 confirmation snapshot.

Notification System не должна самостоятельно получать новые quotes.

---

## 4. Notification Boundary

Поток данных:

Level 1
→ Level 2
→ Profit Calculator
→ Confirmed Opportunity
→ Notification System
→ Telegram

Notification System находится только после final confirmation.

---

## 5. No Business Logic

Notification System не должна:

- получать quotes;
- рассчитывать profitability;
- получать fees;
- получать gas;
- выбирать routes;
- выбирать providers;
- создавать opportunities.

---

## 6. No Direct Scanner Access

Notification System не должна напрямую обращаться к:

- Level 1 Scanner;
- Level 2 Scanner;
- Aggregator APIs;
- blockchain RPC.

Она получает normalized confirmed opportunity.

---

## 7. Confirmed Opportunity

Notification System принимает только объект, имеющий статус:

CONFIRMED

Неподтверждённые opportunities не должны отправляться пользователю.

---

## 8. Confirmation Snapshot

Confirmed Opportunity должна содержать минимум:

- opportunity ID;
- Job ID;
- timestamp;
- network;
- token pair;
- amount;
- route;
- entry provider;
- exit provider;
- input amount;
- output amount;
- fees;
- gas;
- final profit;
- profit percentage;
- calculation version.

---

## 9. Telegram

На текущем этапе основным notification provider является Telegram.

Telegram API должен быть изолирован отдельным adapter.

---

## 10. Telegram Adapter

Notification System не должна содержать Telegram-specific API logic в business layer.

Необходимо иметь отдельный Telegram Adapter.

---

## 11. Telegram Credentials

Telegram credentials должны находиться только в configuration/secrets.

Никогда не хранить:

- bot token;
- chat ID;
- API credentials

в исходном коде.

---

## 12. Message Generation

Формирование текста сообщения должно выполняться отдельным Message Formatter.

Telegram Adapter отвечает только за доставку.

---

## 13. Message Formatter

Formatter получает normalized confirmed opportunity и преобразует её в пользовательское сообщение.

Formatter не должен заново рассчитывать значения.

---

## 14. No Recalculation

Notification System никогда не должна пересчитывать:

- profit;
- profit percentage;
- fees;
- gas;
- output amount.

Она использует значения из final confirmation snapshot.

---

## 15. Multiple Amounts

Если несколько amounts прошли Level 2 confirmation:

каждая подтверждённая сумма должна быть представлена отдельно.

Нельзя смешивать результаты разных amounts.

---

## 16. Notification Identity

Каждое notification должно иметь уникальный notification ID.

---

## 17. Opportunity Identity

Notification должна сохранять связь с:

- opportunity ID;
- Job ID;
- candidate fingerprint.

Это необходимо для deduplication и diagnostics.

---

## 18. Duplicate Notifications

Одна и та же подтверждённая opportunity не должна бесконтрольно отправляться несколько раз.

Необходима deduplication policy.

---

## 19. Notification Fingerprint

Notification fingerprint должен быть основан на существенных параметрах opportunity.

Минимально:

- network;
- route;
- amount;
- token pair;
- entry provider;
- exit provider;
- confirmation identity.

---

## 20. Deduplication Window

Deduplication window должна быть configurable.

Одинаковая opportunity в пределах установленного окна не должна создавать duplicate notification без explicit policy.

---

## 21. Message Status

Каждое notification должно иметь status.

Минимально:

- PENDING;
- SENDING;
- SENT;
- FAILED;
- CANCELLED;
- DUPLICATE.

---

## 22. Delivery Attempt

Каждая попытка отправки должна иметь собственный attempt ID.

---

## 23. Delivery Metadata

Необходимо сохранять:

- notification ID;
- attempt ID;
- opportunity ID;
- provider;
- started_at;
- finished_at;
- status;
- error code.

---

## 24. Telegram Failure

Ошибка Telegram не должна отменять уже подтверждённую opportunity.

Confirmation остаётся CONFIRMED.

Notification получает FAILED status.

---

## 25. Retry

Telegram delivery может иметь retry policy.

Retry должен быть ограниченным.

Бесконечные retry loops запрещены.

---

## 26. Retry Backoff

Retry должен использовать controlled backoff.

Не выполнять постоянные мгновенные повторные requests.

---

## 27. Retry Limit

Количество delivery attempts должно иметь configurable limit.

После достижения лимита notification получает окончательный FAILED status.

---

## 28. Rate Limit

Telegram rate limits должны обрабатываться Notification System.

При rate limit применяется backoff/retry policy.

---

## 29. Resource Manager

Если архитектурная политика требует централизованного контроля внешних requests:

Telegram requests должны проходить через Resource Manager или утверждённый notification-specific resource policy.

Notification System не должна создавать неконтролируемые requests.

---

## 30. Queue

Notifications должны проходить через controlled delivery queue.

Это позволяет отделить confirmation от фактической доставки.

---

## 31. Queue Backpressure

Queue должна иметь configurable capacity.

Нельзя создавать бесконечное количество pending notifications.

---

## 32. Priority

Подтверждённые opportunities должны иметь priority согласно Notification Policy.

Critical/high-value notifications могут иметь более высокий priority.

---

## 33. Ordering

Если несколько notifications имеют одинаковый priority:

используется deterministic ordering.

По умолчанию:

старые confirmed opportunities отправляются раньше новых.

---

## 34. Expiration

Notification должна иметь возможность иметь expiration policy.

Если opportunity потеряла актуальность до отправки:

Notification System не должна выдавать её как новую актуальную opportunity.

---

## 35. Confirmation Timestamp

Message Formatter должен использовать timestamp final confirmation, а не timestamp создания Level 1 candidate.

---

## 36. Message Timestamp

При необходимости сообщение может дополнительно содержать время отправки.

Но время confirmation должно оставаться доступным отдельно.

---

## 37. Network

Сообщение должно явно указывать network.

Например:

Network: Polygon

---

## 38. Token Pair

Сообщение должно содержать token pair.

Например:

USDC → AAVE → USDC

---

## 39. Amount

Сообщение должно содержать amount, для которого была выполнена final confirmation.

---

## 40. Providers

Сообщение должно содержать:

- entry provider;
- exit provider.

---

## 41. Route

Если route важен для понимания opportunity:

он должен отображаться в сообщении.

---

## 42. Profit

Сообщение должно содержать final confirmed profit.

Не preliminary Level 1 profit.

---

## 43. Profit Percentage

Если значение доступно в confirmation snapshot:

сообщение должно содержать final profit percentage.

---

## 44. Fees

Сообщение может содержать breakdown fees.

Если fee breakdown не нужен пользователю:

он всё равно должен оставаться доступным в underlying confirmation data.

---

## 45. Gas

Gas должен быть доступен в notification data.

Он может отображаться в сообщении согласно Message Policy.

---

## 46. Calculation Version

Для diagnostics должна сохраняться calculation version.

Её отображение пользователю является configuration option.

---

## 47. Message Template

Формат сообщения должен быть централизованным.

Не создавать разные hard-coded message formats внутри разных частей приложения.

---

## 48. Configuration

Message configuration должна позволять управлять:

- enabled;
- template;
- precision;
- displayed fields;
- formatting;
- language;
- destination.

---

## 49. Precision

Количество отображаемых decimal places должно быть configurable.

При этом изменение отображения не должно менять исходный финансовый результат.

---

## 50. Formatting Only

Rounding для display не должен использоваться для financial calculation.

Расчёт выполняется до formatting.

---

## 51. Language

Язык сообщения должен быть configuration parameter.

---

## 52. Default Language

Основной язык notification должен определяться утверждённой configuration.

Не hard-code язык внутри Telegram Adapter.

---

## 53. Destination

Telegram destination должен задаваться configuration.

Не hard-code chat ID в application code.

---

## 54. Multiple Destinations

Архитектура может поддерживать несколько Telegram destinations.

Каждый destination должен иметь собственную configuration.

---

## 55. Destination Failure Isolation

Ошибка доставки в один destination не должна автоматически блокировать другие destinations.

---

## 56. Notification Fan-out

Если одна opportunity должна быть отправлена в несколько destinations:

каждая delivery operation должна иметь отдельный status.

---

## 57. No Duplicate Fan-out

Одна destination не должна получить duplicate notification только из-за ошибки другого destination.

---

## 58. Idempotency

Delivery operation должна быть idempotent насколько это позволяет Telegram API.

Повторный execution не должен бесконтрольно создавать duplicate message.

---

## 59. Persistent State

Notification state может храниться в SQLite.

Минимально необходимо сохранять данные, требуемые для:

- deduplication;
- retry;
- diagnostics;
- recovery.

---

## 60. Recovery

После restart:

- SENT notifications не должны отправляться повторно;
- PENDING notifications могут быть восстановлены;
- SENDING notifications должны быть проверены согласно recovery policy;
- FAILED notifications могут быть retried согласно policy.

---

## 61. Crash During Sending

Если приложение завершилось во время Telegram request:

notification не должна автоматически считаться SENT без подтверждения delivery.

Recovery policy должна учитывать неопределённый delivery state.

---

## 62. Delivery Confirmation

После успешного ответа Telegram Adapter notification получает:

SENT

и сохраняет необходимые Telegram response metadata.

---

## 63. Telegram Message ID

Если Telegram API возвращает message ID:

его необходимо сохранять.

---

## 64. Error Classification

Ошибки должны классифицироваться.

Минимально:

- RATE_LIMIT;
- NETWORK_ERROR;
- AUTH_ERROR;
- INVALID_REQUEST;
- DESTINATION_ERROR;
- PROVIDER_ERROR;
- UNKNOWN_ERROR.

---

## 65. Permanent Errors

Permanent errors не должны бесконечно retry.

Например:

- invalid credentials;
- invalid destination;
- invalid message format.

---

## 66. Temporary Errors

Temporary errors могут retry:

- network timeout;
- temporary Telegram outage;
- rate limit.

---

## 67. Authentication Failure

Если Telegram credentials invalid:

Notification System должна зафиксировать AUTH_ERROR.

Не выполнять бесконечные retry.

---

## 68. Message Validation

Перед отправкой необходимо проверить:

- destination;
- message length;
- required fields;
- encoding;
- template validity.

---

## 69. Invalid Message

Invalid message не должен отправляться.

Notification получает FAILED status с соответствующим error code.

---

## 70. Security

Notification System не должна логировать:

- bot token;
- private keys;
- secrets;
- authentication headers.

---

## 71. User Data

Notification должна передавать только необходимые данные.

Не включать в сообщение внутренние secrets или sensitive infrastructure data.

---

## 72. Logging

Structured logs должны содержать:

- notification ID;
- opportunity ID;
- destination ID;
- attempt ID;
- status;
- latency;
- error code.

---

## 73. Metrics

Notification System должна собирать:

- notifications created;
- notifications sent;
- notifications failed;
- duplicates;
- retries;
- rate limits;
- delivery latency;
- queue depth.

---

## 74. Delivery Success Rate

Необходимо измерять процент успешной доставки.

---

## 75. Retry Metrics

Необходимо измерять:

- количество retry;
- среднее количество attempts;
- максимальное количество attempts;
- причины retry.

---

## 76. Testing

Обязательно тестировать:

- confirmed opportunity input;
- formatter;
- templates;
- precision;
- language;
- destination configuration;
- duplicate detection;
- queue;
- retry;
- backoff;
- rate limits;
- temporary errors;
- permanent errors;
- Telegram success;
- Telegram failure;
- authentication failure;
- message validation;
- recovery;
- crash during sending;
- multiple destinations.

---

## 77. Integration Tests

Обязательно тестировать:

Level 2
→ Notification System
→ Telegram Adapter

Также:

Notification System
→ SQLite

и:

Notification System
→ Resource Manager

если Resource Manager используется для Telegram requests.

---

## 78. No False Confirmation

Notification System никогда не должна превращать:

- preliminary opportunity;
- Level 1 candidate;
- failed Level 2 Job;
- expired Job

в confirmed notification.

---

## 79. No Revalidation

Notification System не должна самостоятельно выполнять Level 2 revalidation.

Если opportunity требует повторной проверки:

она должна вернуться в Level 2 workflow.

---

## 80. Critical Invariants

Notification System никогда не должна:

1. получать quotes;

2. рассчитывать profitability;

3. получать fees для самостоятельного расчёта;

4. выбирать routes;

5. выбирать providers;

6. выполнять swaps;

7. подписывать transactions;

8. хранить private keys;

9. отправлять неподтверждённые opportunities;

10. считать Level 1 result окончательным;

11. бесконечно retry Telegram requests;

12. логировать secrets;

13. менять final confirmed profit;

14. создавать duplicate notifications без policy;

15. использовать display rounding для financial calculation.

---

## 81. Главный принцип

Notification System должна:

**получать только подтверждённые Level 2 opportunities, преобразовывать их в понятное пользователю сообщение и надёжно доставлять его через Telegram с контролируемыми retries, deduplication и recovery.**

Level 2 отвечает за:

**подтвердить opportunity.**

Notification System отвечает за:

**доставить подтверждённый результат пользователю.**
