# MONIK

## DEX Arbitrage Scanner

Monik — система для автоматического поиска потенциальных арбитражных возможностей между DEX aggregators.

Основная задача системы:

**обнаружить потенциальную ценовую разницу → повторно проверить именно найденную комбинацию → учесть fees и gas → подтвердить opportunity только при наличии актуальных данных → сохранить результат → отправить уведомление.**

---

## 1. Основная идея

Monik не выполняет автоматическую торговлю.

Система предназначена для:

- поиска потенциальных arbitrage opportunities;
- сравнения цен между поддерживаемыми aggregators;
- повторной проверки найденных opportunities;
- расчёта потенциальной прибыли;
- учёта fees и gas;
- сохранения подтверждённых opportunities;
- отправки уведомлений.

---

## 2. Основной Workflow

Основной workflow:

Scheduler
    ↓
Level 1 Scanner
    ↓
Candidate
    ↓
Level 2 Job
    ↓
Fresh Quotes
    ↓
Fresh Fees + Gas
    ↓
Profit Calculator
    ↓
Confirmed Opportunity
    ↓
Database
    ↓
Notification System

---

## 3. Level 1 Scanner

Level 1 выполняет быстрый preliminary scan.

Он:

- перебирает configured networks;
- перебирает configured tokens;
- использует configured providers;
- получает quotes;
- сравнивает результаты;
- применяет preliminary filtering;
- создаёт Candidate.

Level 1 **не подтверждает opportunity**.

---

## 4. Level 2 Scanner

Level 2 выполняет detailed confirmation.

Он:

- получает Candidate;
- создаёт/обрабатывает Level 2 Job;
- проверяет expiration;
- проверяет capabilities;
- проверяет именно исходную комбинацию Level 1;
- получает fresh quotes;
- получает актуальные fees;
- получает актуальный gas;
- вызывает Profit Calculator;
- принимает решение о confirmation.

---

## 5. Exact Combination Rule

Level 2 обязан проверять именно ту комбинацию, которая была обнаружена Level 1:

- network;
- token pair;
- amount;
- provider pair;
- route.

Level 2 не должен автоматически заменять обнаруженный route другим route только потому, что другой вариант оказался более выгодным.

---

## 6. Profit Calculator

Profit Calculator отвечает только за financial calculation.

Он учитывает необходимые:

- input amount;
- output amount;
- fees;
- gas;
- conversion data;
- calculation rules.

Financial calculations должны использовать exact numeric representation.

Binary floating-point `float` запрещён для critical financial calculations.

---

## 7. False Positive Protection

Monik не должен подтверждать opportunity, если critical financial information неизвестна.

Например:

- missing fee;
- missing gas;
- stale quote;
- invalid route;
- invalid token;
- unavailable required provider.

Отсутствующее значение не должно автоматически превращаться в zero.

---

## 8. Provider Architecture

Каждый external aggregator подключается через отдельный Adapter.

Общий принцип:

Monik
  ↓
Aggregator Interface
  ↓
Provider Adapter
  ↓
Resource Manager
  ↓
Provider API

Provider-specific response преобразуется в normalized domain model.

Provider-specific implementation не должна проникать в business logic.

---

## 9. Resource Manager

Все external provider requests проходят через Resource Manager.

Resource Manager отвечает за:

- concurrency;
- rate limits;
- queue limits;
- timeout;
- retry;
- backoff;
- jitter;
- circuit breaker;
- cancellation.

Business logic не должна обходить Resource Manager.

---

## 10. Database

Persistent state хранится через Repository boundary.

Business logic не должна напрямую использовать SQLite или SQL implementation.

Database используется для хранения необходимого operational и historical state, включая:

- Candidates;
- Level 2 Jobs;
- Opportunities;
- Notifications;
- Fees;
- Capabilities;
- другие данные, предусмотренные architecture.

---

## 11. Notifications

После успешного Level 2 confirmation создаётся Opportunity.

Opportunity сохраняется в database **до начала notification delivery**.

Notification System:

- форматирует сообщение;
- выбирает configured destinations;
- выполняет delivery;
- обрабатывает retry;
- предотвращает duplicate notifications.

Notification System не пересчитывает profitability и не изменяет financial snapshot Opportunity.

---

## 12. Scheduler

Scheduler отвечает за запуск periodic tasks.

В зависимости от configuration он может запускать:

- Level 1 scans;
- fee refresh;
- capability refresh;
- notification retries;
- cleanup;
- health checks;
- maintenance.

Scheduler не содержит business logic.

---

## 13. Configuration

Configuration проходит:

Sources
    ↓
Parse
    ↓
Validate
    ↓
Normalize
    ↓
Resolve Secrets
    ↓
Application

Business logic не должна самостоятельно читать environment variables или configuration files.

Secrets не должны храниться в Git.

---

## 14. State Machines

Critical entities используют explicit state machines.

В частности:

- Level 2 Job;
- Candidate;
- Opportunity;
- Notification;
- Scheduler Task;
- Provider Health;
- Application Health.

Invalid state transitions должны быть отклонены.

---

## 15. Recovery

Monik должен быть устойчив к restart и controlled recovery.

После restart необходимо корректно восстановить необходимое persistent state.

Особенно важно предотвращать duplicate:

- Jobs;
- Opportunities;
- Notifications.

RUNNING Job после crash не считается автоматически successful.

---

## 16. Security

Основные security principles:

- secrets не хранятся в Git;
- secrets не логируются;
- production и test environments изолированы;
- external URLs валидируются;
- SSRF protection обязательна;
- SQL queries должны быть parameterized;
- filesystem operations должны защищаться от path traversal;
- external requests имеют timeout и controlled limits.

---

## 17. Testing

Monik использует несколько уровней тестирования:

- Unit Tests;
- Contract Tests;
- Integration Tests;
- Security Tests;
- Recovery Tests;
- End-to-End Tests;
- Performance Tests.

Особое внимание уделяется:

- financial calculations;
- state transitions;
- provider failures;
- stale data;
- retries;
- concurrency;
- restart recovery;
- duplicate prevention.

---

## 18. Architecture Documentation

Полная архитектура проекта находится в:

docs/architecture/

Основные документы включают:

- Project Requirements;
- Level 1 Scanner;
- Level 2 Scanner;
- Aggregator Architecture;
- Fee System;
- Resource Manager;
- Scheduler;
- Token Registry;
- Capability Registry;
- Profit Calculator;
- Database;
- Error Handling;
- Configuration;
- Security;
- API Contracts;
- Testing;
- State Machines;
- Data Models;
- System Workflows;
- Interfaces;
- Implementation Plan;
- Acceptance Criteria;
- Development Rules.

Эти документы являются частью architecture contract проекта.

---

## 19. Development Rules

Перед изменением кода необходимо:

1. прочитать `CLAUDE.md`;
2. определить relevant architecture documents;
3. проверить существующую implementation;
4. проверить существующие interfaces и models;
5. определить impact изменения;
6. внести минимально необходимое изменение;
7. добавить/update tests;
8. проверить architecture boundaries;
9. обновить документацию при необходимости.

---

## 20. Claude Code

Claude Code используется как исполнитель утверждённой архитектуры.

Claude Code не должен самостоятельно:

- менять architecture;
- менять financial formulas;
- менять state machines;
- менять route policy;
- добавлять providers;
- добавлять networks;
- расширять project scope;
- создавать альтернативные sources of truth.

Если requirements или architecture documents противоречат друг другу, Claude Code должен остановиться и запросить решение.

---

## 21. Project Structure

Основная структура проекта должна соответствовать approved architecture.

Ожидаемые logical layers:

domain
application
infrastructure
providers
repositories
scanners
services
scheduler
notifications
configuration
observability
tests
docs

Конкретная структура файлов должна определяться существующей implementation и architecture documents.

Не создавать новые directories или layers без необходимости и approval.

---

## 22. Development Environment

Разработка выполняется в GitHub repository.

Claude Code должен работать непосредственно с repository и использовать существующие документы архитектуры как источник требований.

---

## 23. Git

Изменения должны быть:

- небольшими;
- логически завершёнными;
- проверяемыми;
- без temporary/debug files;
- без secrets.

Перед завершением работы необходимо проверить Git diff.

---

## 24. Production Readiness

Monik считается production-ready только если:

- requirements выполнены;
- architecture соблюдена;
- financial calculations проверены;
- tests проходят;
- security checks проходят;
- recovery проверен;
- observability работает;
- configuration validated;
- documentation соответствует implementation;
- acceptance criteria выполнены.

---

## 25. Important Safety Rules

Никогда не:

- использовать stale critical data для confirmation;
- превращать missing fee/gas в zero;
- подтверждать Candidate без Level 2;
- заменять Level 1 route без explicit rule;
- обходить Resource Manager;
- обходить Repository;
- отправлять notification до persistence Opportunity;
- изменять confirmed financial snapshot обычным workflow;
- создавать unlimited retries;
- создавать hidden scheduler loops;
- хранить secrets в source code;
- использовать production database в tests.

---

## 26. Source of Truth

При реализации необходимо использовать architecture documentation как единый набор утверждённых правил.

Если implementation и документация расходятся, нельзя молча выбирать implementation.

Сначала необходимо определить intended behavior и синхронизировать документы и код.

---

## 27. Current Project Goal

Главная цель Monik:

**создавать качественные, проверенные и актуальные сигналы о потенциальных DEX arbitrage opportunities, минимизируя false positives и сохраняя строгие архитектурные, финансовые и security boundaries.**
