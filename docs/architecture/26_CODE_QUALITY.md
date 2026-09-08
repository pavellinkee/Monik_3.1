# MONIK — CODE QUALITY

## 1. Назначение

Этот документ определяет обязательные требования к качеству исходного кода Monik.

Цель:

- сохранить архитектуру;
- сделать код читаемым;
- уменьшить количество ошибок;
- упростить тестирование;
- обеспечить предсказуемое поведение;
- облегчить дальнейшее развитие проекта.

---

## 2. Главный принцип

Код должен быть:

- понятным;
- предсказуемым;
- тестируемым;
- минимально сложным;
- соответствующим утверждённой архитектуре.

Рабочий код, нарушающий архитектуру, не считается качественным кодом.

---

## 3. Architecture First

Перед реализацией новой functionality необходимо определить:

- к какой subsystem она относится;
- какой interface используется;
- какие dependencies разрешены;
- где должен находиться код.

---

## 4. Single Responsibility

Каждый module/class/function должен иметь ограниченную и понятную responsibility.

Не объединять unrelated functionality только ради уменьшения количества файлов.

---

## 5. Separation of Concerns

Не смешивать в одном module:

- business logic;
- HTTP;
- database;
- configuration;
- logging;
- presentation.

---

## 6. Business Logic

Business logic должна быть максимально независима от infrastructure.

---

## 7. Infrastructure

Infrastructure code отвечает за взаимодействие с внешними системами.

Например:

- HTTP;
- SQLite;
- Telegram;
- filesystem.

---

## 8. Provider Isolation

Provider-specific implementation должна находиться внутри Adapter.

---

## 9. No Provider Leakage

Provider-specific response fields не должны распространяться по application.

---

## 10. Explicit Dependencies

Dependencies должны передаваться явно.

Не использовать скрытые global dependencies.

---

## 11. Dependency Injection

Для critical services рекомендуется dependency injection.

Особенно для:

- HTTP client;
- clock;
- repositories;
- providers;
- Resource Manager;
- configuration.

---

## 12. Global State

Не использовать mutable global state для business logic.

---

## 13. Singleton Policy

Singleton допускается только для infrastructure components, если это действительно необходимо и lifecycle контролируется application.

---

## 14. Function Size

Functions должны оставаться достаточно небольшими для понимания.

Если function содержит несколько независимых responsibilities:

её следует разделить.

---

## 15. Class Size

Classes не должны становиться универсальными контейнерами всей subsystem.

---

## 16. Deep Nesting

Не допускать чрезмерной вложенности условных конструкций.

Предпочтительно использовать:

- early return;
- отдельные functions;
- explicit validation.

---

## 17. Complexity

Cyclomatic complexity должна оставаться контролируемой.

Сложную business logic необходимо разбивать на понятные этапы.

---

## 18. Duplication

Не дублировать одну и ту же business logic в разных modules.

---

## 19. Single Source of Truth

Каждая важная business rule должна иметь одну authoritative implementation.

Особенно:

- profitability;
- fee handling;
- freshness;
- capability;
- retry;
- scheduling.

---

## 20. No Duplicate Profit Formulas

Profit formula должна находиться только в Profit Calculator.

---

## 21. No Duplicate Fee Logic

Fee normalization и fee policy не должны независимо реализовываться в каждом provider adapter.

---

## 22. No Duplicate Retry Logic

Retry policy для external requests должна контролироваться Resource Manager/Error Handling architecture.

---

## 23. No Duplicate Scheduling

Subsystems не должны создавать собственные независимые scheduler loops.

---

## 24. Naming

Имена:

- functions;
- classes;
- variables;
- files;
- interfaces

должны отражать их actual responsibility.

---

## 25. Avoid Ambiguous Names

Не использовать имена вроде:

- `data`;
- `manager`;
- `helper`;
- `utils`;
- `process`;
- `thing`

без дополнительного контекста, если они скрывают конкретную responsibility.

---

## 26. Boolean Names

Boolean variables должны иметь понятный смысл.

Предпочтительно:

- `enabled`;
- `is_valid`;
- `is_expired`;
- `supports_quote`.

---

## 27. Status Names

Statuses должны использовать стабильные explicit identifiers.

---

## 28. Constants

Magic numbers и magic strings должны быть вынесены в соответствующую configuration или constants layer.

---

## 29. No Magic Financial Values

Нельзя писать в business logic:

    if profit > 0.01

если значение является configuration/policy parameter.

---

## 30. Financial Precision

Financial calculations должны использовать exact representation.

Binary Float запрещён.

---

## 31. Decimal Boundary

Conversion в Decimal/base units должна происходить до financial calculation.

---

## 32. Rounding

Rounding выполняется только согласно explicit financial/display policy.

---

## 33. No Display Logic in Calculator

Profit Calculator не должен форматировать результат для Telegram.

---

## 34. Validation

Input validation должна выполняться как можно ближе к boundary.

---

## 35. Defensive Programming

External data всегда считается потенциально invalid.

---

## 36. Provider Response

Provider response должен проходить:

- schema validation;
- type validation;
- semantic validation.

---

## 37. No Silent Fallback

Нельзя silently заменять invalid data безопасным на вид значением.

Особенно:

- missing fee → zero;
- missing gas → zero;
- invalid quote → previous quote;
- unknown capability → supported.

---

## 38. Explicit UNKNOWN

Unknown state должен быть представлен явно.

---

## 39. Exceptions

Exceptions должны использоваться для действительно exceptional conditions.

Expected business outcomes лучше представлять explicit result/status.

---

## 40. Error Handling

Errors должны быть normalized согласно Error Handling architecture.

---

## 41. No Raw Exceptions Across Boundaries

Не передавать provider-specific exceptions через subsystem boundaries.

---

## 42. Logging

Logging должен быть structured.

---

## 43. Log Levels

Использовать подходящий severity.

Не писать всё как ERROR.

---

## 44. No Secret Logging

Никогда не логировать:

- API keys;
- Telegram tokens;
- passwords;
- private keys;
- authentication headers.

---

## 45. Context Logging

Critical operations должны иметь correlation information:

- scan ID;
- Job ID;
- execution ID;
- notification ID.

---

## 46. No Excessive Logging

Не логировать каждый внутренний шаг без необходимости.

Особенно в high-frequency scanner loops.

---

## 47. Performance

Performance optimization должна основываться на измерениях.

Не усложнять architecture ради предполагаемой оптимизации.

---

## 48. Premature Optimization

Не оптимизировать код до появления подтверждённой performance problem.

---

## 49. Network Calls

Каждый external request должен иметь:

- timeout;
- Resource Manager control;
- normalized error handling.

---

## 50. Database Calls

Database operations должны проходить через repository layer.

---

## 51. Async/Concurrency

Concurrency model должна быть единообразной.

Не смешивать async и blocking operations без explicit boundary.

---

## 52. Blocking Calls

Blocking I/O не должен выполняться внутри event loop без соответствующего mechanism.

---

## 53. Cancellation

Long-running operations должны поддерживать cancellation, если architecture этого требует.

---

## 54. Resource Cleanup

External resources должны корректно освобождаться:

- HTTP connections;
- database connections;
- file handles;
- tasks.

---

## 55. Context Managers

Для ресурсов, поддерживающих context manager, использовать соответствующий lifecycle mechanism.

---

## 56. Mutable Data

Не передавать mutable objects между subsystems без необходимости.

---

## 57. Immutability

Snapshots и critical domain results должны по возможности быть immutable.

---

## 58. Opportunity Snapshot

Confirmed Opportunity snapshot после final confirmation не должен изменяться Notification System.

---

## 59. Job State

Level 2 Job state должен изменяться только через approved state transition logic.

---

## 60. State Machines

Для сложных lifecycle использовать explicit state transition rules.

---

## 61. Invalid Transitions

Нельзя silently принимать запрещённые state transitions.

---

## 62. Idempotency

Operations, которые могут повторно выполняться после retry/restart, должны быть idempotent.

---

## 63. Deduplication

Deduplication должна быть централизована согласно соответствующей subsystem policy.

---

## 64. Testing

Каждая новая business rule должна получать tests.

---

## 65. Testability

Нельзя делать code structure unnecessarily difficult to test.

---

## 66. Mocking

Mock использовать для external dependencies.

Не mock-ить внутреннюю business logic без необходимости.

---

## 67. Fixtures

Fixtures должны быть минимальными и понятными.

---

## 68. Determinism

Tests и core calculations должны быть deterministic.

---

## 69. Time

Time-dependent logic должна использовать injectable clock abstraction.

---

## 70. Randomness

Randomness должна быть injectable/controllable в tests.

---

## 71. Documentation

Public interfaces должны иметь понятную documentation.

---

## 72. Comments

Комментарии должны объяснять:

**почему** код работает именно так.

Не нужно комментировать очевидный syntax.

---

## 73. No Dead Comments

Не оставлять устаревшие комментарии, которые противоречат текущему коду.

---

## 74. TODO

TODO допускается только если:

- есть реальная задача;
- понятно, что требуется сделать;
- TODO не скрывает критический defect.

---

## 75. Dead Code

Unused code должен удаляться.

Не сохранять старые implementations «на всякий случай».

---

## 76. Deprecated Code

Если старый API временно сохраняется:

он должен иметь explicit deprecation policy.

---

## 77. Imports

Imports должны быть:

- deterministic;
- минимальными;
- без циклических dependencies.

---

## 78. Dependency Direction

Imports должны соответствовать утверждённой архитектурной dependency direction.

---

## 79. Forbidden Imports

Architecture tests должны предотвращать запрещённые imports.

Например:

Scanner → Telegram

или:

Domain → SQLite.

---

## 80. Type Checking

Проект должен использовать static type checking, если это поддерживается выбранным языком.

---

## 81. Type Safety

Не использовать `Any`/аналогичные unrestricted types без необходимости.

---

## 82. External Data Types

External responses должны преобразовываться в validated types как можно раньше.

---

## 83. Return Types

Public functions и interfaces должны иметь explicit return types, где это поддерживается языком.

---

## 84. Optional Values

Optional/nullable values должны обрабатываться явно.

---

## 85. No Implicit None

Не считать отсутствие результата успешным результатом.

---

## 86. API Contracts

Internal interfaces должны соответствовать API Contracts document.

---

## 87. Interface Stability

Не менять public interface без анализа всех consumers.

---

## 88. Backward Compatibility

При изменении public interface необходимо:

- обновить consumers;
- обновить tests;
- обновить documentation;
- проверить migration/compatibility.

---

## 89. Code Formatting

Проект должен использовать единый formatter.

---

## 90. Linting

Проект должен использовать linting tool.

---

## 91. Static Analysis

По возможности использовать:

- type checker;
- linter;
- formatter;
- security scanner;
- dependency scanner.

---

## 92. CI

Code quality checks должны запускаться в CI.

Минимально:

- formatting;
- lint;
- type checking;
- unit tests;
- architecture tests.

---

## 93. Pre-Commit

По возможности critical checks должны запускаться до commit.

---

## 94. Commit Safety

Не commit-ить:

- secrets;
- database;
- logs;
- temporary files;
- generated local state.

---

## 95. Dependency Management

Не добавлять dependency без необходимости.

Перед добавлением dependency проверить:

- functionality;
- maintenance;
- security;
- license;
- compatibility;
- package size.

---

## 96. Standard Library First

Если functionality надёжно реализуется стандартной библиотекой:

не добавлять dependency без практической причины.

---

## 97. Dependency Isolation

Infrastructure dependencies не должны проникать в domain layer.

---

## 98. Refactoring

Refactoring не должен менять business behavior без explicit intent.

---

## 99. Small Changes

По возможности изменения должны быть небольшими и логически связанными.

---

## 100. Final Quality Gate

Перед merge/release необходимо проверить:

- architecture;
- tests;
- formatting;
- lint;
- types;
- security;
- dependencies;
- documentation.

---

## 101. Critical Invariants

Code Quality никогда не должна позволять:

1. нарушать architecture boundaries ради удобства;

2. дублировать critical business logic;

3. использовать Float для financial calculations;

4. silently заменять UNKNOWN на zero;

5. обходить Resource Manager;

6. обходить repository layer;

7. создавать hidden global mutable state;

8. логировать secrets;

9. оставлять dead code без причины;

10. добавлять dependencies без необходимости;

11. игнорировать type/validation errors;

12. создавать circular dependencies;

13. делать critical code untestable;

14. смешивать provider-specific implementation с domain logic;

15. изменять business behavior под видом обычного refactoring.

---

## 102. Главный принцип

Code Quality должна обеспечить:

**читаемый, тестируемый, предсказуемый и архитектурно дисциплинированный код, в котором business logic остаётся независимой от infrastructure, critical rules имеют единственный источник истины, а каждое изменение можно безопасно проверить автоматическими тестами.**
