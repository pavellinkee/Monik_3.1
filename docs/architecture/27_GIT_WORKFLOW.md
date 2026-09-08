# MONIK — GIT WORKFLOW

## 1. Назначение

Этот документ определяет обязательные правила работы с Git и GitHub для проекта Monik.

Цель:

- сохранить историю изменений;
- защитить утверждённую архитектуру;
- предотвратить случайную потерю кода;
- обеспечить воспроизводимость проекта;
- упростить review;
- обеспечить безопасную работу Claude Code с repository.

---

## 2. Главный принцип

GitHub repository является source of truth для:

- исходного кода;
- утверждённых architecture documents;
- tests;
- configuration schemas;
- deployment files;
- project documentation.

Runtime data и secrets source of truth repository не являются.

---

## 3. GitHub Repository

Monik должен разрабатываться внутри одного определённого Git repository.

Claude Code должен работать с этим repository как с основным source tree проекта.

---

## 4. Claude Code

Claude Code должен иметь возможность:

- читать repository;
- читать architecture documents;
- создавать source code;
- создавать tests;
- изменять application code;
- запускать проверки;
- создавать commits;
- выполнять push в GitHub при наличии необходимых credentials/permissions.

---

## 5. GitHub Access

Если Claude Code имеет authenticated GitHub/Git access:

он может самостоятельно:

- `git pull`;
- `git status`;
- `git add`;
- `git commit`;
- `git push`.

Если credentials или permissions отсутствуют:

Claude Code должен сообщить об этом, а не пытаться обходить authentication.

---

## 6. No Credential Bypass

Claude Code никогда не должен:

- запрашивать у пользователя private keys;
- сохранять GitHub passwords в repository;
- обходить authentication;
- отключать Git security;
- использовать чужие credentials.

---

## 7. Repository State

Перед началом существенной работы Claude Code должен проверить:

- current branch;
- working tree status;
- current commit;
- remote;
- наличие незакоммиченных изменений.

---

## 8. No Silent Overwrite

Claude Code не должен автоматически удалять или перезаписывать пользовательские незакоммиченные изменения без explicit approval.

---

## 9. Existing Changes

Если working tree содержит изменения, которые Claude Code не создавал:

он должен учитывать их как existing user work.

Не удалять их автоматически.

---

## 10. Pull Before Work

Перед началом новой development phase рекомендуется получить актуальное состояние repository.

Использовать:

`git pull`

согласно repository workflow.

---

## 11. Remote Changes

Если remote содержит изменения, которых нет локально:

Claude Code должен сначала синхронизировать repository или явно сообщить о конфликте.

---

## 12. Merge Conflicts

Merge conflicts нельзя разрешать автоматически, если невозможно однозначно определить правильный результат.

В случае architectural conflict:

нужно остановиться и запросить решение пользователя.

---

## 13. Architecture Documents

Утверждённые документы в:

`docs/architecture/`

являются protected architectural source.

---

## 14. Architecture Protection

Claude Code не должен изменять утверждённые architecture documents только для того, чтобы:

- упростить реализацию;
- устранить конфликт;
- сделать tests проходящими;
- адаптировать код под удобный implementation.

---

## 15. Architecture Conflict

Если существующая architecture document противоречит необходимой implementation:

Claude Code должен:

1. определить конфликт;
2. сообщить о нём;
3. не изменять architecture document самостоятельно;
4. ждать explicit approval пользователя.

---

## 16. No Architecture Drift

Claude Code не должен постепенно менять архитектуру через небольшие code changes без explicit architectural decision.

---

## 17. Documentation Hierarchy

При разработке использовать следующий порядок:

1. `CLAUDE.md`;
2. утверждённые project requirements;
3. утверждённые architecture documents;
4. tests;
5. implementation details.

Implementation не должна silently переопределять architecture.

---

## 18. CLAUDE.md

`CLAUDE.md` содержит обязательные инструкции для Claude Code.

Если CLAUDE.md конфликтует с более свежим explicit user instruction:

user instruction имеет приоритет.

---

## 19. User Approval

Изменение архитектуры требует explicit user approval.

Approval должен быть однозначным.

---

## 20. Code Changes

Обычные code changes не требуют отдельного approval для каждого файла, если они:

- соответствуют architecture;
- соответствуют requirements;
- проходят tests;
- не меняют established boundaries.

---

## 21. Major Changes

Claude Code должен остановиться перед:

- удалением subsystem;
- изменением public contract;
- изменением database schema без migration;
- изменением architecture boundary;
- добавлением нового major dependency;
- изменением security model;
- включением trading execution.

---

## 22. Commit

Каждый логически завершённый набор изменений рекомендуется сохранять отдельным commit.

---

## 23. Commit Atomicity

Commit должен содержать одну логическую задачу или связанный набор изменений.

Не смешивать:

- unrelated refactoring;
- feature;
- dependency upgrade;
- architecture change

в один commit без необходимости.

---

## 24. Commit Message

Commit message должен кратко описывать изменение.

Рекомендуемый формат:

`type: short description`

Например:

`feat: implement level 1 scanner`

или:

`fix: handle stale quotes`

---

## 25. Commit Types

Допустимые типы:

- feat;
- fix;
- refactor;
- test;
- docs;
- chore;
- security;
- perf.

---

## 26. No Secret Commit

Перед commit необходимо убедиться, что не добавлены:

- `.env`;
- API keys;
- Telegram tokens;
- passwords;
- private keys;
- local databases;
- backups.

---

## 27. Gitignore

Repository должен иметь `.gitignore`, предотвращающий случайный commit:

- secrets;
- runtime data;
- logs;
- databases;
- temporary files;
- local environments.

---

## 28. Database

Production/local SQLite database не должна находиться под Git tracking.

---

## 29. Logs

Runtime logs не должны commit-иться.

---

## 30. Backups

Database backups не должны commit-иться.

---

## 31. Environment Files

Реальные `.env` files не должны commit-иться.

Можно хранить:

`.env.example`

без реальных credentials.

---

## 32. Generated Files

Generated artifacts не должны commit-иться без explicit reason.

---

## 33. Large Files

Не добавлять большие binary/runtime files в repository без необходимости.

---

## 34. Branches

Рекомендуется использовать:

- main;
- feature branches;
- fix branches.

---

## 35. Main Branch

`main` должна содержать состояние, которое соответствует known-good project state.

---

## 36. Feature Branch

Большие features рекомендуется разрабатывать в отдельной branch.

---

## 37. Fix Branch

Bug fixes могут выполняться в отдельных branches, если это соответствует workflow.

---

## 38. Direct Main Changes

Direct changes в `main` допустимы только если repository workflow это явно разрешает.

---

## 39. Pull Requests

Для существенных изменений рекомендуется использовать Pull Request.

---

## 40. Pull Request Requirements

Перед merge необходимо проверить:

- tests;
- architecture;
- security;
- code quality;
- documentation;
- database migrations.

---

## 41. Architecture Review

PR, изменяющий architecture boundary, требует отдельного architectural review.

---

## 42. No Hidden Architectural Changes

Нельзя включать architecture changes в PR, описанный только как:

`refactor`;

если они изменяют actual system behavior/boundaries.

---

## 43. Tags

Production releases рекомендуется помечать Git tag.

Например:

`v1.0.0`

---

## 44. Versioning

Release version должна однозначно соответствовать определённому commit.

---

## 45. Release State

Production deployment должен использовать конкретный commit/tag.

Не использовать moving branch как единственную гарантию deployed version.

---

## 46. Rollback

Rollback должен быть возможен через возврат к предыдущему known-good commit/tag.

---

## 47. Database Rollback

Code rollback и database rollback должны рассматриваться отдельно.

Нельзя предполагать, что возврат Git commit автоматически откатывает database schema.

---

## 48. Migration Compatibility

Database migrations должны учитывать возможность deployment rollback.

---

## 49. Git History

Не переписывать shared history без explicit reason.

---

## 50. Force Push

Force push запрещён для shared protected branches без explicit approval.

---

## 51. Rebase

Rebase допустим на private feature branches.

Не выполнять rebase shared branch без необходимости.

---

## 52. Reset

`git reset --hard` запрещено использовать для удаления пользовательских изменений без explicit approval.

---

## 53. Clean

`git clean` нельзя использовать для удаления untracked files без explicit approval.

---

## 54. Checkout

Не заменять пользовательские modified files через checkout/restore без explicit approval.

---

## 55. Destructive Git Commands

Особенно осторожно обращаться с:

- `git reset --hard`;
- `git clean`;
- `git checkout --`;
- `git restore`;
- force push.

---

## 56. Before Destructive Operation

Перед destructive Git operation необходимо:

1. определить, какие данные будут потеряны;
2. сообщить пользователю;
3. получить approval.

---

## 57. Diff

Перед commit Claude Code должен проверить diff.

Минимально:

`git diff`

и при необходимости:

`git diff --cached`

---

## 58. Unexpected Changes

Если diff содержит изменения, которые не относятся к текущей задаче:

не включать их в commit автоматически.

---

## 59. Commit Scope

Commit должен включать только необходимые изменения.

---

## 60. Push

После commit Claude Code может выполнять push, если:

- repository authenticated;
- branch policy разрешает push;
- изменения соответствуют task;
- tests пройдены.

---

## 61. Push Failure

Если push failed:

Claude Code должен сообщить точную причину.

Не использовать destructive workaround.

---

## 62. Non-Fast-Forward

При non-fast-forward:

не выполнять force push автоматически.

Сначала получить remote changes и определить безопасный merge/rebase strategy.

---

## 63. Authentication Failure

При authentication failure:

не пытаться обходить credentials.

---

## 64. Remote Verification

Перед push необходимо убедиться, что remote соответствует ожидаемому repository.

---

## 65. Wrong Remote

Если remote выглядит подозрительно или не соответствует project:

не выполнять push.

---

## 66. Commit Verification

После push желательно проверить:

- current commit;
- branch;
- remote synchronization;
- GitHub state, если доступен.

---

## 67. CI

После push CI должен автоматически выполнять required checks, если он настроен.

---

## 68. Failed CI

Failed CI означает, что изменения не должны считаться production-ready.

---

## 69. No CI Bypass

Не отключать CI checks только для прохождения merge без explicit approval.

---

## 70. Test Failures

Если tests failed:

Claude Code должен исправлять код, а не изменять tests только для получения зелёного CI.

---

## 71. Test Modification

Изменение test expected result допустимо только если:

- behavior действительно изменён намеренно;
- architecture/requirements допускают изменение;
- изменение подтверждено корректными expected semantics.

---

## 72. Documentation Updates

Если code change меняет documented behavior:

соответствующая documentation должна быть рассмотрена.

---

## 73. Architecture Documents and Git

Architecture documents должны иметь обычную Git history.

Это позволяет определить:

- когда документ изменён;
- какой commit его изменил;
- кто инициировал изменение.

---

## 74. Protected Documents

Наличие Git permissions само по себе не заменяет instruction-level protection.

Claude Code должен дополнительно соблюдать protection rules из:

- `CLAUDE.md`;
- architecture documents;
- user instructions.

---

## 75. GitHub Branch Protection

Если repository поддерживает branch protection:

рекомендуется защищать `main`.

---

## 76. Required Checks

Для protected `main` рекомендуется требовать:

- CI;
- tests;
- architecture checks;
- security checks.

---

## 77. CODEOWNERS

Для критических architecture documents можно использовать `CODEOWNERS`, если repository workflow это поддерживает.

---

## 78. CODEOWNERS Scope

Рекомендуется защищать как минимум:

`docs/architecture/`

а также security/deployment files.

---

## 79. GitHub Permissions

Claude Code должен иметь только необходимые repository permissions.

---

## 80. Minimal Access

Если Claude Code способен работать с repository через ограниченные permissions:

не предоставлять избыточные права.

---

## 81. Repository Secrets

GitHub Actions secrets должны использоваться вместо hard-coded credentials.

---

## 82. CI Secrets

CI secrets не должны выводиться в logs.

---

## 83. Pull Request Secrets

Не предоставлять production secrets недоверенным pull request workflows.

---

## 84. GitHub Actions

Workflow files должны проходить review.

---

## 85. Action Dependencies

GitHub Actions dependencies должны иметь контролируемые versions.

---

## 86. Workflow Security

Не запускать arbitrary untrusted code с production credentials.

---

## 87. Release Automation

Release automation может создавать tags/artifacts.

Она не должна автоматически изменять architecture documents.

---

## 88. Generated Documentation

Generated documentation не должна перезаписывать вручную утверждённые architecture documents без explicit policy.

---

## 89. Repository Backup

Git repository сам по себе не заменяет database backup.

---

## 90. Git Is Not Database Backup

SQLite data должна иметь отдельный backup/recovery mechanism.

---

## 91. Git Is Not Secret Storage

Git history не должна использоваться для хранения secrets.

Даже удалённый secret может остаться в Git history.

---

## 92. Secret Leak

Если secret случайно попал в Git:

1. credential должен быть revoked/rotated;
2. repository history должен быть проверен;
3. secret exposure должен быть оценён;
4. простой delete file недостаточен.

---

## 93. History Inspection

При security incident необходимо проверить Git history на наличие leaked credentials.

---

## 94. Large Refactor

Large refactor должен выполняться отдельными логическими commits, если это помогает review и rollback.

---

## 95. Atomic Release

Production release должен соответствовать определённому commit/tag.

---

## 96. Reproducibility

Любой production state должен быть воспроизводим по:

- Git commit/tag;
- dependencies;
- configuration;
- deployment environment.

Secrets восстанавливаются отдельно.

---

## 97. Developer Workflow

Рекомендуемый цикл:

1. sync repository;
2. read architecture;
3. inspect status;
4. implement;
5. test;
6. inspect diff;
7. commit;
8. push;
9. CI;
10. verify.

---

## 98. Claude Code Workflow

Claude Code должен:

1. прочитать `CLAUDE.md`;
2. прочитать relevant architecture documents;
3. проверить repository state;
4. реализовать задачу;
5. запустить tests;
6. проверить diff;
7. commit изменения;
8. push, если разрешено;
9. проверить результат.

---

## 99. No Blind Automation

Claude Code не должен выполнять destructive Git operations автоматически.

---

## 100. Final Git Principle

Git workflow должен обеспечить:

**контролируемую историю изменений, защиту архитектуры, безопасную синхронизацию с GitHub и возможность точно определить, какой код находится в каждом production deployment.**

---

## 101. Critical Invariants

Git workflow никогда не должен позволять:

1. терять пользовательские изменения без approval;

2. force push в protected branch без approval;

3. commit-ить production secrets;

4. commit-ить production database;

5. commit-ить runtime logs;

6. обходить CI для сокрытия failures;

7. изменять architecture documents silently;

8. использовать Git как secret storage;

9. использовать Git как database backup;

10. выполнять destructive Git commands без approval;

11. выполнять push в неизвестный remote;

12. использовать production credentials в untrusted CI workflows;

13. менять tests только для искусственного получения successful CI;

14. считать branch без конкретного commit достаточной гарантией production version.

---

## 102. Главный принцип

Git workflow Monik должен обеспечить:

**безопасный цикл от изменения кода до GitHub и production deployment, при котором история изменений прозрачна, архитектура защищена, secrets не попадают в repository, а любое production состояние можно однозначно связать с конкретным commit.**
