# MONIK — PROFIT CALCULATOR

## 1. Назначение

Profit Calculator — единая подсистема финансовых расчётов Monik.

Она отвечает за:

- gross profit;
- net profit;
- gross ROI;
- net ROI;
- суммирование расходов;
- учёт gas;
- учёт aggregator fees;
- учёт protocol fees;
- учёт integrator fees;
- учёт rebates;
- точность расчётов;
- применение profitability threshold.

Scanner не должен самостоятельно реализовывать финансовые формулы.

---

## 2. Главный принцип

Все финансовые расчёты должны выполняться через единый Profit Calculator.

Level 1 и Level 2 передают Calculator normalized financial data.

Calculator возвращает deterministic calculation result.

---

## 3. Decimal

Для финансовых расчётов использовать Decimal.

Запрещено использовать float для:

- token amounts;
- fees;
- gas;
- profit;
- ROI;
- percentages;
- threshold comparisons.

---

## 4. Raw Blockchain Amounts

Blockchain raw amounts должны храниться как integer.

Например:

1000000

может представлять:

1 USDT

при соответствующем decimals.

Преобразование в Decimal выполняется только через token metadata.

---

## 5. Token Decimals

Calculator должен получать decimals из Token Registry/normalized token metadata.

Не hard-code:

USDT = 6

или:

AAVE = 18

внутри Calculator.

---

## 6. Input Amount

Каждый calculation context должен содержать:

- input amount;
- input token;
- network.

Input amount должен быть однозначно определён.

---

## 7. BUY Output

Calculation context должен содержать фактический BUY output.

Это значение должно быть получено из текущего quote.

Не использовать старый Level 1 BUY result для Level 2 calculation.

---

## 8. SELL Output

SELL output является основным final output текущей проверки.

Например:

Input:
100 USDT

BUY:
5.14 AAVE

SELL:
101.50 USDT

---

## 9. Gross Profit

Gross profit рассчитывается до вычитания расходов.

Формула:

gross_profit = final_output - input_amount

при условии, что input и final output приведены к одной единице расчёта.

---

## 10. Gross ROI

Формула:

gross_roi = gross_profit / input_amount × 100

Результат хранится как Decimal.

---

## 11. Costs

Calculator должен учитывать все известные applicable costs.

Минимально:

- aggregator fee;
- protocol fee;
- integrator fee;
- gas;
- other costs.

---

## 12. Total Fees

Если существует несколько fee components:

total_fees =
aggregator_fee
+
protocol_fee
+
integrator_fee
+
other_costs

Каждый component должен сохраняться отдельно.

---

## 13. Gas

Gas является отдельным cost component.

Если gas выражен в native token:

он должен быть преобразован в calculation currency через надёжный conversion mechanism.

---

## 14. Net Profit

Формула:

net_profit =
gross_profit
-
total_costs

где:

total_costs =
total_fees
+
gas_cost
+
other_costs
-
rebates

Если rebates отсутствуют:

их значение равно 0 только потому, что соответствующий компонент подтверждённо отсутствует или не применяется.

---

## 15. Rebate

Rebate не должен смешиваться с обычной fee.

Он хранится отдельным компонентом.

Например:

aggregator_fee = 0.20 USDT
rebate = 0.05 USDT

Итоговый cost:

0.15 USDT

---

## 16. Unknown Costs

Если обязательный cost неизвестен:

Calculator не должен автоматически считать его равным 0.

Например:

gas = UNKNOWN

не превращается в:

gas = 0

---

## 17. Calculation Status

Calculator должен возвращать статус расчёта.

Минимально:

- COMPLETE;
- PARTIAL;
- INVALID;
- UNKNOWN.

---

## 18. COMPLETE

COMPLETE означает:

все необходимые данные для соответствующего calculation context известны и валидны.

Результат может использоваться для полноценной profitability evaluation.

---

## 19. PARTIAL

PARTIAL означает:

часть данных известна, но недостаточно для полностью достоверного net result.

Например:

- gas unknown;
- fee unknown;
- conversion unavailable.

PARTIAL не является подтверждением прибыльности.

---

## 20. INVALID

INVALID означает:

данные противоречат друг другу или содержат невозможное значение.

Например:

- отрицательный input amount;
- неправильная currency;
- invalid token decimals;
- impossible output.

---

## 21. UNKNOWN

UNKNOWN используется, если невозможно определить корректный calculation result.

---

## 22. Negative Profit

Если:

net_profit < 0

возможность не является прибыльной.

Calculator возвращает отрицательное значение.

Не превращать его в 0.

---

## 23. Zero Profit

Если:

net_profit = 0

profitability считается нулевой.

---

## 24. Threshold

Default Level 1 profitability threshold:

1%

Threshold должен быть configuration value.

Не hard-code его внутри Calculator.

---

## 25. Threshold Metric

По умолчанию threshold применяется к:

net_roi

если все необходимые costs известны.

---

## 26. Threshold Comparison

По умолчанию:

net_roi >= threshold

означает прохождение threshold.

Например:

threshold = 1.00%

net_roi = 1.00%

проходит threshold.

---

## 27. Unknown Cost и Threshold

Если неизвестный cost способен изменить результат относительно threshold:

нельзя считать opportunity прошедшей threshold.

Например:

calculated net ROI = 1.20%
unknown gas = potentially > 0.20%

не подтверждать прохождение threshold.

---

## 28. Level 1 Calculation

Level 1 использует Calculator для discovery profitability.

Результат может быть:

- profitable;
- unprofitable;
- incomplete.

Level 1 не является окончательным confirmation.

---

## 29. Level 2 Calculation

Level 2 использует Calculator для свежего profitability result.

Если все необходимые данные валидны:

результат может использоваться Confirmation Policy.

---

## 30. Один Calculator

Не создавать отдельную финансовую формулу для:

- Level 1;
- Level 2;
- Telegram;
- History.

Все используют общий Calculator.

---

## 31. Calculation Input Model

Calculator должен получать normalized input model.

Минимально:

- input amount;
- input currency;
- final output;
- output currency;
- fees;
- gas;
- rebates;
- conversion rates;
- threshold context.

---

## 32. Calculation Output Model

Результат должен содержать:

- gross profit;
- gross ROI;
- total fees;
- gas cost;
- other costs;
- rebates;
- net profit;
- net ROI;
- threshold;
- threshold passed;
- calculation status;
- calculation timestamp.

---

## 33. Component Breakdown

Result должен позволять восстановить:

как получился net profit.

Например:

gross profit = 1.80
aggregator fee = 0.20
protocol fee = 0.10
gas = 0.30
rebate = 0.05
net profit = 1.25

---

## 34. Currency Conversion

Если input и final output находятся в одной валюте:

дополнительная conversion не требуется.

Если они разные:

необходимо использовать надёжный conversion mechanism.

---

## 35. Conversion Source

Каждый conversion rate должен иметь:

- source;
- timestamp;
- pair;
- rate;
- precision.

---

## 36. Stale Conversion

Если conversion rate устарел:

Calculator должен получить актуальный rate или вернуть соответствующий incomplete/unknown result.

Не использовать бесконечно старый rate.

---

## 37. Conversion Failure

Если conversion невозможно выполнить:

Calculator не должен придумывать значение.

Результат:

PARTIAL

или:

UNKNOWN.

---

## 38. Conversion Direction

Система должна явно учитывать направление conversion.

Например:

ETH → USDT

не равно автоматически:

USDT → ETH

без соответствующего inverse calculation.

---

## 39. Precision

Calculator должен сохранять необходимую точность до финального этапа.

Не округлять промежуточные значения без необходимости.

---

## 40. Rounding

Округление должно происходить:

- по официальным правилам, если они существуют;
- либо на presentation layer.

Не округлять промежуточные значения только ради удобства отображения.

---

## 41. Token Amount Validation

Calculator должен проверять:

- amount > 0;
- корректную decimals;
- корректную currency;
- соответствие input/output context.

---

## 42. Fee Validation

Каждая fee component должна проверяться:

- type;
- amount;
- currency;
- applicability;
- status.

UNKNOWN fee не должна передаваться как valid zero.

---

## 43. Gas Validation

Gas должен проверяться:

- amount;
- currency;
- network;
- conversion status.

---

## 44. Cost Double Counting

Calculator не должен дважды вычитать один и тот же cost.

Например, если quote уже включает aggregator fee в final output и Fee System отдельно передала ту же fee:

Calculator должен знать соответствующий inclusion flag.

---

## 45. Fee Inclusion

Каждый cost component должен иметь информацию:

- included_in_quote;
- not_included;
- unknown.

Если fee уже отражена в quote:

не вычитать её второй раз.

---

## 46. Gas Inclusion

Аналогично gas:

если gas уже учтён в исходном financial value:

не вычитать его повторно.

---

## 47. Quote Semantics

Calculator должен знать semantics quote:

- gross output;
- net output;
- fee-inclusive output.

Эта информация приходит из Adapter/Fee System.

Calculator не должен угадывать её.

---

## 48. Aggregator-specific Semantics

Если конкретный агрегатор имеет специфичную semantics:

она должна быть нормализована Adapter/Fee System.

Calculator получает единый формат.

---

## 49. Profitability Result

Calculator должен возвращать deterministic result.

Одинаковые входные данные должны давать одинаковый результат.

---

## 50. Threshold Result

Результат threshold должен содержать:

- threshold value;
- metric;
- actual metric;
- passed;
- calculation status.

---

## 51. Level 1 Threshold Configuration

Level 1 threshold:

1%

является default.

Пользовательская configuration может изменить значение.

---

## 52. No Individual Aggregator Threshold

Не создавать отдельный profitability threshold для каждого агрегатора, если это не предусмотрено отдельной configuration policy.

Базовый threshold относится к profitability result.

---

## 53. Multiple Amounts

Каждая сумма имеет отдельный calculation context.

Например:

50 USDT
100 USDT
500 USDT
1000 USDT

рассчитываются отдельно.

---

## 54. No Cross-Amount Mixing

Результаты одной суммы нельзя использовать для расчёта другой суммы.

Например:

gas для:

50 USDT

не должен автоматически использоваться как gas для:

1000 USDT

если gas зависит от операции/route.

---

## 55. Same Route, Different Amount

В рамках одной Opportunity разные суммы используют один и тот же route.

Но financial result для каждой суммы рассчитывается отдельно.

---

## 56. Gas Dependence

Если gas зависит от:

- amount;
- route;
- network;
- operation;

Calculator получает соответствующий gas для конкретной суммы/route.

---

## 57. Percentage Fee Dependence

Если fee является процентом:

Calculator применяет её к соответствующей базе.

База должна быть явно определена Fee Policy.

Например:

- input amount;
- output amount;
- transaction value.

Не угадывать базу.

---

## 58. Fixed Fee Dependence

Fixed fee применяется только один раз к соответствующей операции, если provider policy не требует иного.

Не умножать fixed fee на количество tokens или legs без подтверждённого правила.

---

## 59. Multi-leg Fees

Если route содержит несколько legs и каждая имеет отдельную fee:

Calculator должен получить нормализованные fee components.

Не создавать искусственную общую fee без подтверждённых данных.

---

## 60. Protocol Fees

Protocol fee является отдельным component.

Если она уже включена в quote:

это должно быть отражено в fee metadata.

---

## 61. Integrator Fees

Integrator fee является отдельным component.

Если Monik не использует integrator fee:

он не должен появляться как скрытый cost.

---

## 62. Other Costs

Other costs могут использоваться для дополнительных подтверждённых расходов.

Каждый такой cost должен иметь:

- description/type;
- amount;
- currency;
- source.

---

## 63. Unknown Other Costs

Если существует потенциальный cost, но его размер неизвестен:

не считать его zero.

---

## 64. Profit Currency

Calculator должен определить единую currency результата.

По умолчанию:

input currency.

Если это невозможно:

calculation status становится PARTIAL/UNKNOWN.

---

## 65. Profit Currency Metadata

Result должен содержать:

- profit currency;
- currency source;
- conversion data references.

---

## 66. Result Snapshot

При Level 2 confirmation необходимо сохранять calculation snapshot.

Он должен содержать:

- input;
- output;
- fee components;
- gas;
- conversions;
- formula version;
- threshold;
- result.

---

## 67. Formula Version

Calculator должен иметь versioned calculation formula.

Например:

profit_formula_version = 1

Если финансовая формула изменится:

новая версия должна быть различима.

---

## 68. Backward Compatibility

Исторические результаты должны сохранять информацию о formula version.

Нельзя интерпретировать старый результат через новую формулу без явного указания.

---

## 69. Calculation Audit

Для важных Level 2 results должна быть возможность восстановить:

- какие значения использовались;
- какие fees использовались;
- какой gas использовался;
- какие conversion rates использовались;
- какая formula version использовалась.

---

## 70. Database Storage

SQLite должна хранить calculation result для Level 2.

Минимально:

- K-ID;
- amount;
- formula version;
- gross profit;
- fees;
- gas;
- rebates;
- net profit;
- ROI;
- threshold;
- status;
- timestamp.

---

## 71. Idempotency

Повторный calculation с одинаковыми входными данными и formula version должен быть deterministic.

Не создавать duplicate business result из-за повторной доставки одного события.

---

## 72. Error Handling

Calculator должен возвращать структурированную ошибку при:

- invalid amount;
- invalid currency;
- invalid decimals;
- missing conversion;
- invalid fee;
- inconsistent quote;
- arithmetic error.

Не возвращать случайный numeric result.

---

## 73. No Silent Correction

Calculator не должен молча исправлять:

- отрицательные amounts;
- неверные currencies;
- missing fees;
- invalid decimals.

Ошибка должна быть явно отражена.

---

## 74. No API Calls

Calculator не должен самостоятельно обращаться к внешним API.

Он получает уже normalized financial data.

Внешние запросы выполняют:

- Adapters;
- Fee System;
- соответствующие conversion/market data subsystems.

---

## 75. No Scheduler Logic

Calculator не должен:

- создавать tasks;
- управлять очередью;
- выполнять retries;
- управлять resources.

---

## 76. No Telegram Logic

Calculator не должен форматировать Telegram messages.

Presentation layer получает calculation result и форматирует его отдельно.

---

## 77. Testing

Обязательно тестировать:

- gross profit;
- gross ROI;
- net profit;
- net ROI;
- zero profit;
- negative profit;
- threshold boundary;
- fees;
- gas;
- rebates;
- unknown costs;
- currency conversion;
- precision;
- rounding;
- duplicate cost prevention;
- multiple amounts;
- formula version.

---

## 78. Property Tests

Желательно иметь property-based tests для основных финансовых инвариантов.

Например:

если все costs увеличиваются при прочих равных:

net profit не должен увеличиваться.

---

## 79. Critical Invariants

Profit Calculator никогда не должен:

1. использовать float для финансовых расчётов;

2. считать UNKNOWN fee равной zero;

3. считать UNKNOWN gas равным zero;

4. дважды вычитать один cost;

5. использовать невалидный conversion rate;

6. менять route;

7. выполнять API requests;

8. менять Scheduler state;

9. самостоятельно создавать Opportunity;

10. скрывать calculation errors.

---

## 80. Главный принцип

Profit Calculator должен отвечать на вопрос:

**какова реальная прибыльность конкретного результата при заданных свежих входных данных и известных расходах?**

Он должен быть:

- точным;
- deterministic;
- auditable;
- provider-independent;
- независимым от Scheduler;
- независимым от Telegram.

Если критически важный расход неизвестен:

**Calculator не должен создавать искусственно завышенную прибыльность.**
