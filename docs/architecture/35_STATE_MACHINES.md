# MONIK — STATE MACHINES

## 1. Назначение

Этот документ определяет обязательные state machines для Monik.

Цель:

- сделать lifecycle критических объектов явным;
- запретить invalid state transitions;
- обеспечить recovery после restart;
- обеспечить idempotency;
- упростить testing;
- предотвратить false-positive состояния.

---

## 2. Главный принцип

Каждый объект с несколькими lifecycle states должен иметь:

- определённый набор states;
- разрешённые transitions;
- запрещённые transitions;
- условия перехода;
- side effects;
- recovery behavior.

Нельзя изменять critical state произвольным присваиванием.

---

## 3. State Machine Boundary

State transition должен выполняться через соответствующий domain/application service.

Другие subsystems не должны напрямую изменять persistent status.

---

## 4. State Immutability

Текущий state может изменяться только через explicit transition operation.

---

## 5. Invalid Transition

Любой запрещённый transition должен приводить к explicit error.

Нельзя silently игнорировать invalid transition.

---

## 6. Persistent State

Для critical state transition изменение state и необходимые связанные database changes должны выполняться atomic transaction.

---

## 7. Main State Machines

Monik должен иметь explicit state machines как минимум для:

- Level 2 Job;
- Candidate;
- Opportunity;
- Notification;
- Scheduler Task;
- Provider Health;
- Application Health.

---

## 8. Level 2 Job States

Level 2 Job использует:

- QUEUED;
- RUNNING;
- CONFIRMED;
- REJECTED;
- FAILED;
- EXPIRED;
- CANCELLED.

---

## 9. Job Initial State

Новый valid Level 2 Job создаётся в:

`QUEUED`

---

## 10. QUEUED

QUEUED означает:

Job существует и ожидает execution.

---

## 11. QUEUED → RUNNING

Переход разрешён, если:

- Job не expired;
- Job не cancelled;
- required resources доступны;
- Scheduler/worker начинает execution.

---

## 12. QUEUED → EXPIRED

Разрешено, если `expires_at` достигнут до начала execution.

---

## 13. QUEUED → CANCELLED

Разрешено при explicit cancellation.

---

## 14. QUEUED → CONFIRMED

Запрещено.

Job должен пройти validation/execution.

---

## 15. QUEUED → REJECTED

Допускается только если Job validation обнаружила невозможность выполнения до начала execution.

---

## 16. QUEUED → FAILED

Допускается при unrecoverable failure до execution.

---

## 17. RUNNING

RUNNING означает:

Job в данный момент выполняется.

---

## 18. RUNNING → CONFIRMED

Разрешено только если все Level 2 confirmation requirements выполнены.

---

## 19. RUNNING → REJECTED

Разрешено, если fresh validation показала отсутствие valid opportunity.

---

## 20. RUNNING → FAILED

Разрешено при unrecoverable operational/internal failure.

---

## 21. RUNNING → EXPIRED

Разрешено, если Job expiration наступил и operation больше не может безопасно продолжаться.

---

## 22. RUNNING → CANCELLED

Разрешено при explicit cancellation, если operation безопасно отменить.

---

## 23. RUNNING → QUEUED

Не выполнять автоматически без explicit retry/requeue policy.

Если retry реализован:

должен существовать explicit transition mechanism.

---

## 24. CONFIRMED

CONFIRMED означает:

Level 2 подтвердил opportunity на основании актуальных данных.

---

## 25. CONFIRMED Immutability

После CONFIRMED critical financial snapshot не должен изменяться.

---

## 26. CONFIRMED Terminal State

CONFIRMED является terminal state для Job.

---

## 27. CONFIRMED → FAILED

Запрещено.

Notification failure не превращает confirmed Job в FAILED.

---

## 28. CONFIRMED → REJECTED

Запрещено.

---

## 29. CONFIRMED → EXPIRED

Запрещено после успешной confirmation.

Expiration относится к pending Job, а не к уже подтверждённому snapshot.

---

## 30. REJECTED

REJECTED означает:

Level 2 завершил validation и не подтвердил opportunity.

---

## 31. REJECTED Terminal State

REJECTED является terminal state.

---

## 32. FAILED

FAILED означает:

Job завершился из-за unrecoverable failure.

---

## 33. FAILED Terminal State

FAILED является terminal state, если не существует explicit recovery/requeue operation.

---

## 34. EXPIRED

EXPIRED означает:

Job больше не может безопасно выполняться из-за истечения validity window.

---

## 35. EXPIRED Terminal State

EXPIRED является terminal state.

---

## 36. CANCELLED

CANCELLED означает:

Job был явно отменён.

---

## 37. CANCELLED Terminal State

CANCELLED является terminal state.

---

## 38. Job Retry

Retry не должен изменять terminal state произвольно.

Для retry должна существовать explicit policy.

Например:

FAILED
→ QUEUED

только через controlled requeue operation.

---

## 39. Job Retry Conditions

Requeue разрешается только если:

- failure retryable;
- retry budget не исчерпан;
- Job не expired;
- candidate всё ещё valid;
- operation безопасна.

---

## 40. Job Expiration Priority

Если Job одновременно:

- retryable;
- expired;

expiration имеет приоритет над retry.

---

## 41. Job Recovery After Restart

Если application остановился во время RUNNING:

при restart Job не должен автоматически считаться CONFIRMED.

---

## 42. RUNNING Recovery

RUNNING Job после restart должен перейти в controlled recovery path.

Возможные результаты:

- requeue;
- failed;
- expired;
- cancelled;

в зависимости от persisted state и policy.

---

## 43. Candidate States

Candidate может использовать:

- CREATED;
- QUEUED;
- PROCESSING;
- CONFIRMED;
- REJECTED;
- EXPIRED;
- CANCELLED.

---

## 44. Candidate CREATED

CREATED означает:

Level 1 создал Candidate после preliminary validation.

---

## 45. Candidate CREATED → QUEUED

Переход означает передачу Candidate в Level 2 workflow.

---

## 46. Candidate CREATED → REJECTED

Разрешено, если дальнейшая validation обнаружила invalid candidate до queueing.

---

## 47. Candidate QUEUED

QUEUED означает:

Candidate ожидает создания/обработки Level 2 Job.

---

## 48. Candidate QUEUED → PROCESSING

Разрешено при начале Level 2 processing.

---

## 49. Candidate PROCESSING

PROCESSING означает:

Candidate находится в active confirmation workflow.

---

## 50. Candidate PROCESSING → CONFIRMED

Разрешено только после успешного Level 2 confirmation.

---

## 51. Candidate PROCESSING → REJECTED

Разрешено при failed profitability/validation checks.

---

## 52. Candidate PROCESSING → EXPIRED

Разрешено при истечении candidate validity.

---

## 53. Candidate PROCESSING → FAILED

Разрешено при unrecoverable processing failure, если Candidate lifecycle предусматривает FAILED state.

---

## 54. Candidate CONFIRMED

CONFIRMED означает:

Candidate успешно привёл к confirmed opportunity.

---

## 55. Candidate CONFIRMED Immutability

Confirmed Candidate financial context не должен изменяться произвольно.

---

## 56. Candidate REJECTED

REJECTED означает:

Candidate не соответствует confirmation requirements.

---

## 57. Candidate EXPIRED

EXPIRED означает:

Candidate больше нельзя использовать из-за stale data или expiration.

---

## 58. Candidate CANCELLED

CANCELLED означает:

Candidate был отменён до confirmation.

---

## 59. Opportunity States

Opportunity может использовать:

- CONFIRMED;
- NOTIFIED;
- NOTIFIED_PARTIAL;
- NOTIFIED_FAILED.

---

## 60. Opportunity Creation

Opportunity создаётся только после успешного Level 2 confirmation.

---

## 61. Opportunity Initial State

Новая confirmed Opportunity начинается в:

`CONFIRMED`

---

## 62. CONFIRMED → NOTIFIED

Разрешено после успешной notification delivery согласно notification policy.

---

## 63. CONFIRMED → NOTIFIED_PARTIAL

Разрешено, если notification destinations несколько и только часть delivery завершилась успешно.

---

## 64. CONFIRMED → NOTIFIED_FAILED

Разрешено, если notification delivery окончательно failed согласно policy.

---

## 65. Opportunity No Recalculation

Notification state transition не должен пересчитывать financial result.

---

## 66. Opportunity Financial Immutability

После создания Opportunity следующие данные не должны изменяться обычным workflow:

- input amount;
- output amount;
- costs;
- net profit;
- profit percentage;
- route;
- network;
- calculation version.

---

## 67. Opportunity Correction

Если financial correction действительно необходима:

использовать explicit correction/audit mechanism.

Не изменять snapshot silently.

---

## 68. Notification States

Notification использует:

- QUEUED;
- SENDING;
- SENT;
- RETRY_WAIT;
- FAILED;
- CANCELLED.

---

## 69. Notification QUEUED

Notification ожидает delivery.

---

## 70. QUEUED → SENDING

Переход выполняется при начале delivery attempt.

---

## 71. SENDING → SENT

Разрешено после подтверждённого успешного delivery.

---

## 72. SENDING → RETRY_WAIT

Разрешено при retryable temporary failure.

---

## 73. SENDING → FAILED

Разрешено при permanent failure или исчерпании retry budget.

---

## 74. SENDING → CANCELLED

Разрешено при explicit cancellation, если policy допускает cancellation.

---

## 75. RETRY_WAIT

RETTRY_WAIT означает:

следующая delivery attempt ожидает разрешённого времени.

---

## 76. RETRY_WAIT → SENDING

Разрешено после наступления retry time и при наличии retry budget.

---

## 77. RETRY_WAIT → FAILED

Разрешено при:

- retry budget exhausted;
- permanent configuration failure;
- destination unavailable permanently.

---

## 78. SENT Terminal State

SENT является terminal state для конкретной Notification delivery.

---

## 79. FAILED Notification

FAILED не должен изменять Opportunity financial state.

---

## 80. Notification Idempotency

Повторная обработка одной logical notification должна проверять existing delivery state.

---

## 81. Duplicate Notification

Если Notification уже SENT для соответствующей logical destination:

повторная отправка не должна происходить автоматически.

---

## 82. Scheduler Task States

Scheduler Task execution может использовать:

- SCHEDULED;
- RUNNING;
- SUCCESS;
- FAILED;
- SKIPPED;
- CANCELLED.

---

## 83. SCHEDULED

Task ожидает execution time.

---

## 84. SCHEDULED → RUNNING

Переход происходит при начале execution.

---

## 85. SCHEDULED → SKIPPED

Разрешено при:

- disabled task;
- overlap policy;
- missed execution policy;
- system shutdown.

---

## 86. RUNNING → SUCCESS

Разрешено после успешного execution.

---

## 87. RUNNING → FAILED

Разрешено при task failure.

---

## 88. RUNNING → CANCELLED

Разрешено при controlled shutdown/cancellation.

---

## 89. Scheduler Failure Isolation

FAILED одна Task не должна автоматически переводить весь Scheduler в FAILED.

---

## 90. Scheduler Overlap

Если overlap policy запрещает concurrent executions:

новый execution должен перейти в SKIPPED или controlled delayed state.

---

## 91. Provider Health States

Provider Health использует:

- UNKNOWN;
- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- RECOVERING.

---

## 92. Provider UNKNOWN

UNKNOWN означает:

состояние ещё не подтверждено.

UNKNOWN не означает HEALTHY.

---

## 93. UNKNOWN → HEALTHY

Разрешено после successful health/operational check.

---

## 94. UNKNOWN → DEGRADED

Разрешено при частичном failure.

---

## 95. UNKNOWN → UNAVAILABLE

Разрешено при подтверждённой недоступности.

---

## 96. HEALTHY → DEGRADED

Разрешено при превышении configured failure threshold.

---

## 97. HEALTHY → UNAVAILABLE

Разрешено при подтверждённой полной недоступности.

---

## 98. DEGRADED → HEALTHY

Разрешено после успешного recovery threshold.

---

## 99. DEGRADED → UNAVAILABLE

Разрешено при ухудшении состояния.

---

## 100. UNAVAILABLE → RECOVERING

Разрешено после начала controlled recovery probes.

---

## 101. RECOVERING → HEALTHY

Разрешено после успешных recovery checks.

---

## 102. RECOVERING → UNAVAILABLE

Разрешено при failed recovery.

---

## 103. Health Flapping

Health transitions должны использовать hysteresis/threshold policy для предотвращения постоянного переключения states.

---

## 104. Application Health States

Application Health использует:

- STARTING;
- HEALTHY;
- DEGRADED;
- UNAVAILABLE;
- STOPPING.

---

## 105. STARTING

STARTING означает:

application выполняет initialization.

---

## 106. STARTING → HEALTHY

Разрешено после успешной critical initialization.

---

## 107. STARTING → DEGRADED

Разрешено, если optional subsystem недоступна, но application может безопасно работать.

---

## 108. STARTING → UNAVAILABLE

Разрешено при critical initialization failure.

---

## 109. HEALTHY → DEGRADED

Разрешено при operational degradation.

---

## 110. HEALTHY → UNAVAILABLE

Разрешено при critical application failure.

---

## 111. DEGRADED → HEALTHY

Разрешено после successful recovery.

---

## 112. DEGRADED → UNAVAILABLE

Разрешено при critical deterioration.

---

## 113. HEALTHY → STOPPING

Разрешено при graceful shutdown.

---

## 114. DEGRADED → STOPPING

Разрешено при graceful shutdown.

---

## 115. STOPPING

STOPPING означает:

application прекращает работу.

---

## 116. STOPPING Terminal

После STOPPING application должен завершить process.

---

## 117. State Transition Atomicity

Critical state transition и соответствующая persistent update должны выполняться atomic transaction.

---

## 118. State Transition Event

Каждый critical transition должен быть observable.

Минимально:

- entity ID;
- previous state;
- new state;
- timestamp;
- reason;
- correlation ID.

---

## 119. Transition Reason

Reason должен быть machine-readable или иметь stable code.

---

## 120. No Hidden Transitions

Нельзя менять state без зарегистрированного transition operation.

---

## 121. State Validation

Перед transition необходимо проверить:

- current state;
- requested state;
- business conditions;
- expiration;
- permissions;
- dependencies.

---

## 122. Race Conditions

Concurrent state transitions должны быть защищены.

---

## 123. Optimistic Protection

Если используется optimistic concurrency:

transition должен проверить expected current state/version.

---

## 124. Duplicate Transition

Повторное выполнение уже успешно применённого idempotent transition должно быть безопасным.

---

## 125. Conflicting Transition

Если два workers пытаются выполнить incompatible transitions:

только один должен успешно изменить state.

---

## 126. Terminal State Protection

Terminal states не должны изменяться обычными background processes.

---

## 127. Recovery Operations

Recovery operation должна быть отдельным explicit action.

Например:

FAILED → QUEUED

не является обычным автоматическим transition.

---

## 128. Recovery Authorization

Recovery operation должна выполняться только approved subsystem/process.

---

## 129. Expiration Priority

Expiration должна иметь приоритет над retry, если validity window закончился.

---

## 130. Cancellation Priority

Explicit cancellation должна предотвращать новые execution attempts, если operation ещё не начала irreversible action.

---

## 131. Confirmation Priority

CONFIRMED может быть достигнут только после прохождения всех required confirmation checks.

---

## 132. No Shortcut

Нельзя выполнять:

QUEUED → CONFIRMED

или:

CREATED → CONFIRMED

без полного workflow.

---

## 133. State Persistence

Critical state должен сохраняться до transition completion.

---

## 134. Restart Safety

После restart application должен восстановить state из database и продолжить только допустимые workflows.

---

## 135. Stale RUNNING State

RUNNING state после crash не должен считаться доказательством успешного execution.

---

## 136. Recovery Timestamp

Recovery operation должна фиксировать:

- recovery time;
- previous state;
- resulting state;
- reason.

---

## 137. State Machine Tests

Каждый state machine должен иметь tests для:

- every valid transition;
- every forbidden transition;
- initial state;
- terminal states;
- expiration;
- cancellation;
- retry;
- recovery;
- concurrency;
- restart.

---

## 138. Transition Coverage

Critical state machines должны иметь полный coverage разрешённых и запрещённых transitions.

---

## 139. State Diagram Source

Если state machine имеет diagram:

она должна соответствовать этому document и implementation.

---

## 140. Documentation Consistency

Изменение state machine требует синхронного обновления:

- implementation;
- tests;
- database schema;
- API contracts;
- documentation.

---

## 141. Critical Invariants

State Machines никогда не должны позволять:

1. QUEUED → CONFIRMED без Level 2 validation;

2. Candidate → CONFIRMED без confirmation workflow;

3. CONFIRMED → FAILED через обычный notification failure;

4. terminal state изменяться обычным background process;

5. stale Job становиться CONFIRMED;

6. expired Job автоматически retry;

7. invalid transition silently игнорироваться;

8. два workers одновременно успешно изменить один critical state;

9. RUNNING после restart автоматически считаться successful;

10. UNKNOWN считаться HEALTHY;

11. Notification менять financial state Opportunity;

12. retry обходить state machine;

13. cancellation запускать новую работу;

14. state изменяться без persistent consistency;

15. architecture-dependent state transition существовать только в одном consumer без explicit contract.

---

## 142. Главный принцип

State Machines должны обеспечить:

**явный, проверяемый и безопасный lifecycle каждого критического объекта Monik, при котором любое изменение состояния имеет определённые условия, observable reason, persistent consistency и предсказуемое поведение при ошибках, retry, restart и concurrent execution.**
