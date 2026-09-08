# MONIK — ОБЩИЕ ТРЕБОВАНИЯ К ПРОЕКТУ

## 1. Назначение

Monik — production-ready система для автоматического поиска и проверки арбитражных возможностей между DEX aggregators.

Система должна:

- получать актуальные quotes;
- сравнивать цены между providers;
- находить потенциально прибыльные возможности;
- выполнять Level 2 confirmation;
- учитывать комиссии и gas;
- отправлять подтверждённые opportunities в Telegram;
- сохранять необходимую историю и состояние;
- работать непрерывно без ручного вмешательства.

---

## 2. Production-ready

Приложение должно проектироваться сразу как production system.

Нельзя создавать временную архитектуру, которую позже необходимо полностью переписывать.

Код должен быть:

- modular;
- testable;
- maintainable;
- fault-tolerant;
- deterministic;
- extensible.

---

## 3. Основные providers

Production adapters должны поддерживать:

- 1inch;
- 0x;
- Velora;
- Uniswap.

Каждый provider должен быть изолирован собственным adapter/module.

---

## 4. Provider Independence

Отказ одного provider не должен автоматически останавливать работу остальных.

Каждый adapter должен иметь собственные:

- API configuration;
- capability information;
- error handling;
- rate-limit handling;
- request logic.

---

## 5. Polygon

Первоначальная production network:

**Polygon.**

Архитектура должна позволять добавлять другие EVM networks без переписывания scanner architecture.

---

## 6. Multi-Network Architecture

Network не должна быть hard-coded внутри scanner logic.

Network должна определяться configuration/capability layer.

---

## 7. Token Universe

Основной scanner работает с ограниченным набором наиболее ликвидных токенов.

На первом этапе используется:

**Top 30 tokens.**

Необходимо избегать бессмысленного сканирования огромного количества токенов.

---

## 8. Token Registry

Все используемые токены должны находиться в едином Token Registry.

Registry должен хранить normalized token metadata.

Минимально:

- symbol;
- address;
- decimals;
- network;
- enabled;
- provider availability.

---

## 9. Token Address

Адрес токена должен быть network-specific.

Нельзя предполагать, что одинаковый symbol означает одинаковый token address на разных networks.

---

## 10. Token Decimals

Decimals должны храниться явно.

Финансовые расчёты не должны предполагать decimals по symbol.

---

## 11. Scanner Levels

Система имеет два уровня проверки:

- Level 1 Scanner;
- Level 2 Scanner.

Level 1 предназначен для быстрого поиска потенциальных возможностей.

Level 2 предназначен для подтверждения найденной возможности.

---

## 12. Level 1

Level 1 должен выполнять максимально дешёвое и быстрое обнаружение opportunities.

Level 1 не должен выполнять полный набор дорогостоящих проверок, если они не нужны для первичного отбора.

---

## 13. Level 2

Level 2 получает только отобранные Level 1 opportunities.

Level 2 выполняет повторную проверку непосредственно перед уведомлением.

---

## 14. Level 2 Priority

Level 2 confirmation имеет приоритет над новым Level 1 scan.

Если Level 2 opportunity ожидает проверки:

новый Level 1 scan не должен бесконтрольно вытеснять её.

---

## 15. Fixed Routes

На текущем этапе routes должны быть фиксированными и определёнными архитектурой.

Система не должна самостоятельно строить произвольные multi-hop routes.

---

## 16. Route Model

Route должен явно определять:

- input token;
- output token;
- provider;
- network;
- operation;
- route sequence.

---

## 17. Aggregator Comparison

Главная задача Monik:

сравнивать реальные executable quotes между поддерживаемыми aggregators.

Нельзя сравнивать абстрактные market prices вместо executable quotes.

---

## 18. Quote Freshness

Quote должен быть получен непосредственно перед использованием.

Нельзя использовать устаревший quote вместо нового запроса, если policy требует актуальный quote.

---

## 19. Quote Cache

Quote caching не используется как замена свежим trading quotes.

Monik не должен полагаться на старый quote для подтверждения прибыльности.

---

## 20. No Unnecessary Caching

Не создавать cache subsystem только ради уменьшения количества quote requests.

Оптимизация requests должна выполняться через:

- Resource Manager;
- batching;
- request deduplication;
- provider capabilities;
- fee reuse.

---

## 21. Multiple Amounts

Система должна проверять несколько заранее настроенных сумм одновременно.

Каждая сумма должна рассматриваться как отдельный calculation context.

---

## 22. Amount Configuration

Суммы должны задаваться через user configuration.

Scanner не должен hard-code суммы внутри Python code.

---

## 23. Profitability

Profitability определяется только после учёта всех известных расходов.

Минимально:

profit = output - input - fees - gas - other confirmed costs.

---

## 24. Profit Calculator

Все расчёты profitability должны находиться в отдельном Profit Calculator.

Scanner не должен содержать собственную копию profitability formulas.

---

## 25. Decimal Arithmetic

Все финансовые расчёты должны использовать Decimal или эквивалентную exact arithmetic model.

Использование binary floating point для финансовых расчётов запрещено.

---

## 26. Gas

Gas является обязательной частью profitability calculation.

Gas должен учитываться отдельно от aggregator/protocol fees.

---

## 27. Fees

Система должна учитывать:

- aggregator fees;
- protocol fees;
- integrator fees;
- gas;
- rebates;
- другие подтверждённые costs.

---

## 28. Unknown Fees

UNKNOWN fee не должна автоматически считаться равной zero.

Если обязательная комиссия неизвестна:

opportunity должна быть обработана согласно safety policy.

---

## 29. Double Counting

Одна и та же fee не должна учитываться дважды.

Если provider уже включил fee в quote:

Profit Calculator не должен вычитать её повторно.

---

## 30. Fee System

Получение и нормализация fees должны выполняться через отдельную Fee System.

Scanner не должен самостоятельно реализовывать provider-specific fee logic.

---

## 31. Fee Reuse

Если fee data получена ранее и всё ещё актуальна:

необходимо использовать её повторно.

Не выполнять одинаковый fee request при каждом scanner cycle.

---

## 32. Startup Fee Refresh

При запуске приложения необходимые fee data должны быть получены заранее согласно Fee System policy.

---

## 33. Scheduled Fee Refresh

Fee data должна поддерживать scheduled refresh.

Минимально:

- startup;
- daily.

Период и время должны быть configurable.

---

## 34. Resource Manager

Все внешние requests должны проходить через централизованный Resource Manager.

Это относится к:

- aggregator APIs;
- gas APIs;
- blockchain RPC;
- external data APIs;
- fee APIs.

---

## 35. Rate Limits

Resource Manager отвечает за:

- rate limits;
- concurrency;
- retries;
- backoff;
- provider availability;
- request prioritization.

---

## 36. Priority

Resource Manager должен поддерживать priority requests.

Минимально Level 2 requests имеют более высокий priority, чем обычные Level 1 requests.

---

## 37. Retry

Retry policy должна быть централизованной.

Каждый adapter не должен самостоятельно создавать бесконтрольные retry loops.

---

## 38. Provider Failure

Ошибка одного provider не должна останавливать всю систему.

Система должна продолжать работать с доступными providers.

---

## 39. Circuit Protection

При длительном provider outage Resource Manager должен предотвращать бесконтрольное количество requests.

---

## 40. Concurrency

Количество одновременно выполняемых внешних requests должно контролироваться.

Не допускать неограниченного создания async tasks.

---

## 41. Request Deduplication

Одинаковые одновременно выполняющиеся requests должны иметь возможность объединяться, если это безопасно.

Это особенно важно для:

- fee requests;
- capability requests;
- metadata requests.

---

## 42. Batch Requests

Если provider поддерживает batch endpoint:

Monik должен использовать batch, когда это действительно уменьшает количество requests.

---

## 43. Scheduler

Scheduler является централизованной системой запуска scheduled tasks.

Он отвечает за:

- startup;
- daily;
- configurable interval;
- exact time;
- timezone;
- maintenance.

---

## 44. Level 1 Schedule

Level 1 Scanner должен запускаться с заданным interval.

Interval должен быть configurable.

---

## 45. Level 2 Immediate Execution

Level 2 не должен ждать следующего Level 1 interval.

После обнаружения подходящей opportunity Level 2 Job должен запускаться немедленно через соответствующую queue/scheduler mechanism.

---

## 46. SQLite

SQLite используется как локальное persistent storage.

Она может использоваться для:

- state;
- confirmed opportunities;
- fee snapshots;
- diagnostics;
- recovery information;
- approved history.

---

## 47. SQLite не является источником live quotes

SQLite не должна использоваться для хранения старых quotes с целью замены свежих API requests.

---

## 48. Recovery

После перезапуска приложение должно восстановить необходимое состояние.

Необходимо обеспечить recovery для:

- scheduler state;
- relevant jobs;
- confirmed opportunities;
- critical runtime state.

---

## 49. In-flight Jobs

После restart старые in-flight jobs не должны автоматически считаться успешно завершёнными.

Они должны быть восстановлены согласно explicit recovery policy.

---

## 50. Telegram

Telegram используется как notification channel.

Telegram не должен содержать бизнес-логику scanner.

---

## 51. Notifications

Уведомление должно отправляться только после прохождения необходимой проверки profitability.

Для Level 2 opportunity Telegram notification должен использовать данные подтверждённого расчёта.

---

## 52. Multiple Amount Notifications

Если opportunity прибыльна для нескольких настроенных сумм:

Telegram notification должна содержать информацию по каждой соответствующей сумме.

---

## 53. No False Positives

Главная цель Level 2:

минимизировать false positive notifications.

Opportunity не должна отправляться как profitable только на основании устаревших или неполных данных.

---

## 54. Operating Modes

Система должна поддерживать как минимум два режима работы:

**Mode A**

поиск и уведомление о возможностях;

**Mode B**

расширенный production workflow согласно утверждённой configuration.

Конкретное поведение каждого режима должно быть определено отдельной configuration policy.

---

## 55. No Automatic Trading

На текущем этапе Monik не выполняет автоматические swaps.

Система только:

- получает quotes;
- анализирует;
- подтверждает;
- уведомляет.

---

## 56. Safety Boundary

Наличие profitability opportunity не является разрешением на автоматическое выполнение transaction.

Trading execution должен рассматриваться как отдельная будущая subsystem.

---

## 57. Watchdog

Отдельный самостоятельный watchdog daemon не требуется.

Health monitoring и recovery должны находиться внутри общей архитектуры приложения.

---

## 58. Health

Система должна иметь health/diagnostic mechanisms.

Они должны позволять определить:

- состояние providers;
- состояние Resource Manager;
- состояние Scheduler;
- состояние database;
- состояние scanners;
- последние ошибки.

---

## 59. Logging

Logging должен быть structured.

Минимально логировать:

- task;
- provider;
- network;
- request type;
- status;
- latency;
- error code;
- execution ID.

Secrets не должны попадать в logs.

---

## 60. Configuration

Пользовательские настройки должны быть отделены от внутренней configuration.

User configuration должна позволять изменять параметры без изменения application code.

---

## 61. Hard-coded Restrictions

Не hard-code в business logic:

- token lists;
- amounts;
- intervals;
- provider API keys;
- Telegram credentials;
- network configuration;
- fee rates.

---

## 62. Testing

Каждая subsystem должна иметь automated tests.

Минимально должны тестироваться:

- Token Registry;
- Aggregator Adapters;
- Resource Manager;
- Fee System;
- Profit Calculator;
- Level 1 Scanner;
- Level 2 Scanner;
- Scheduler;
- Database;
- Telegram notifications;
- recovery;
- configuration validation.

---

## 63. Integration Tests

Необходимо иметь integration tests для взаимодействия основных subsystems.

Минимально:

Level 1 → Level 2 → Profit Calculator → Telegram.

Также:

Scanner → Resource Manager → Aggregator Adapter.

---

## 64. Failure Tests

Необходимо тестировать:

- provider timeout;
- provider error;
- rate limit;
- invalid response;
- missing fee;
- stale fee;
- database failure;
- Telegram failure;
- restart;
- duplicate requests;
- concurrent requests.

---

## 65. Determinism

При одинаковых входных данных Profit Calculator должен возвращать одинаковый результат.

Не должно существовать скрытого состояния, влияющего на финансовый расчёт.

---

## 66. Финальный критерий

Monik считается соответствующим архитектуре только если:

1. поддерживает утверждённые aggregators;
2. работает с утверждёнными networks;
3. использует Token Registry;
4. использует Level 1 и Level 2;
5. использует фиксированные routes;
6. получает реальные актуальные quotes;
7. использует Resource Manager;
8. корректно учитывает fees и gas;
9. использует Profit Calculator;
10. поддерживает несколько сумм;
11. использует Scheduler;
12. сохраняет необходимое состояние в SQLite;
13. корректно восстанавливается после restart;
14. отправляет подтверждённые opportunities в Telegram;
15. не выполняет автоматические swaps;
16. не использует отдельный watchdog daemon;
17. имеет automated tests;
18. не содержит архитектурных обходов утверждённых subsystem boundaries.

**Главный принцип проекта:**

**Monik должен находить реальные, актуальные и подтверждённые арбитражные возможности с минимальным количеством внешних запросов, сохраняя строгие границы между подсистемами и не допуская ложной оценки прибыльности.**
