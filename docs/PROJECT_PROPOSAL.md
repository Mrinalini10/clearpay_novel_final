# PROJECT PROPOSAL

# ClearPay: A Liquidity-Aware, Fault-Tolerant Payment Clearing and Settlement System Using AWS Serverless Architecture

**Domain:** Cloud Computing, Financial Technology, Distributed Systems and Payment Settlement Optimization

**Project Type:** Software Development / Cloud-Based Application

**Platform:** Amazon Web Services (AWS)

**Implementation Language:** Python

**Development Constraint:** AWS Free Tier-eligible services and local benchmarking, with the objective of avoiding cloud charges

---

## 1. Abstract

Digital payment systems depend on reliable transaction processing, efficient settlement mechanisms and accurate financial record reconciliation. While traditional payment processing ensures that transactions are recorded and transferred between accounts, interbank settlement introduces additional challenges related to liquidity availability, transaction failures, duplicate processing and operational efficiency.

ClearPay is a cloud-based payment clearing and reconciliation engine developed using AWS serverless architecture. The system is designed to process payment requests asynchronously, prevent duplicate processing, maintain consistent ledger records and calculate settlement obligations using established netting techniques.

The proposed enhancement introduces a liquidity-aware partial settlement mechanism that determines which payments can be settled when participating banks have insufficient available liquidity to settle an entire batch. Instead of delaying every payment, the system identifies a feasible subset, settles the selected obligations and carries forward the remaining payments into subsequent settlement windows.

The project will additionally strengthen transaction recovery through deterministic settlement plans, idempotent operations and checkpoint-based execution. Automated reconciliation will be used to identify discrepancies between internal settlement records and simulated external bank statements.

The completed system will be evaluated using simulated financial transactions, with particular attention to settlement completion, liquidity efficiency, transaction consistency, failure recovery and processing performance.

---

## 2. Problem Statement

Modern payment clearing and settlement systems must process financial transactions accurately while operating within the liquidity constraints of participating financial institutions. When one or more banks have insufficient settlement funds, an all-or-nothing batch settlement approach may delay an entire group of transactions, even when a subset could be settled using the liquidity already available.

Furthermore, asynchronous transaction processing introduces challenges such as duplicate payment requests, repeated message delivery, interrupted settlement workflows, inconsistent financial records and reconciliation discrepancies. Addressing these problems requires a system that combines reliable transaction processing with efficient liquidity utilization and fault-tolerant settlement execution.

**The proposed project, ClearPay, aims to develop a cloud-based payment clearing and reconciliation engine that can identify and settle a feasible subset of payment obligations under limited liquidity, safely defer the remaining payments, prevent duplicate financial effects, and recover from operational failures.**

The solution will build on AWS serverless infrastructure and incorporate multilateral netting, liquidity-constrained payment selection, deterministic settlement execution and automated reconciliation.

---

## 3. Project Objectives

### Primary Objective

To design and implement a reliable cloud-based payment clearing and settlement engine that maximizes feasible payment settlement under limited liquidity while maintaining financial consistency.

### Specific Objectives

1. Develop an asynchronous payment ingestion and processing system using AWS serverless services.
2. Prevent duplicate payment processing through idempotency keys and conditional database operations.
3. Maintain transaction consistency using atomic ledger updates.
4. Support gross, bilateral, multilateral and hub-spoke netting for comparative analysis.
5. Develop a liquidity-aware partial settlement algorithm to select feasible payment subsets.
6. Defer payments that cannot be settled and reconsider them in future settlement windows.
7. Implement failure recovery mechanisms that prevent duplicate bank-level financial effects.
8. Automate reconciliation between internal transaction records and simulated bank statements.
9. Evaluate the proposed algorithm against existing baseline approaches.
10. Minimize cloud expenditure by using applicable AWS Free Tier allowances and local benchmarking.

---

## 4. Existing System and Work Completed

ClearPay already has a foundational serverless architecture and a set of implemented Python modules.

### 4.1 Development Environment and Infrastructure

The following activities have been completed:

- Installed and configured AWS CLI and AWS SAM CLI.
- Configured AWS authentication profiles and verified AWS access.
- Created a Git repository containing the project source code.
- Configured a Python 3.12 development environment with project dependencies.
- Created Lambda handlers, shared processing modules and automated tests.
- Defined AWS infrastructure using a SAM/CloudFormation template.
- Validated and built the serverless application.
- Deployed the ClearPay CloudFormation stack in the AWS Mumbai region (`ap-south-1`).
- Successfully invoked the payment ingestion endpoint.

The successful deployment used the AWS CLI profile `clearpay-andrea`. A separate profile, `clearpay-dev`, was also configured earlier.

### 4.2 Existing Payment Processing Architecture

**Stage 1 — Payment Ingestion**

AWS Services: API Gateway, AWS Lambda, DynamoDB, Amazon SQS.

The ingestion layer receives payment requests through an HTTP API. The Lambda function validates transaction information, checks the API key and processes the supplied idempotency key.

A conditional DynamoDB operation is used to prevent multiple records from being created for the same payment identifier. Valid payment requests are placed in an SQS queue for asynchronous processing.

**Implementation status:** Code written, infrastructure deployed and a successful HTTP 202 payment-ingestion response verified.

**Stage 2 — Ledger Posting**

AWS Services: SQS, AWS Lambda, DynamoDB, Dead-Letter Queue.

The posting Lambda is designed to process queued payments and perform transactional ledger updates. DynamoDB transactions are used to maintain consistency across the debit, credit and payment records.

Failed messages are intended to be retried and eventually moved to a dead-letter queue when retry limits are exceeded.

**Implementation status:** Handler and infrastructure created. Successful end-to-end processing of a live queued payment has not yet been established from the available execution logs.

**Stage 3 — Settlement Processing**

AWS Services: EventBridge Scheduler, AWS Step Functions, AWS Lambda and DynamoDB.

The existing architecture includes a scheduled settlement workflow with separate stages for collecting posted payments, calculating settlement obligations and finalizing settlement records.

The workflow is designed to support retries and resumable processing.

**Implementation status:** Settlement handlers and infrastructure have been developed and deployed. A complete successful settlement execution has not yet been verified.

**Stage 4 — Netting Algorithms**

The existing Python implementation includes:

- Gross settlement
- Bilateral netting
- Multilateral netting
- Hub-spoke settlement

These techniques are used to calculate and compare the number and value of resulting transfers.

**Implementation status:** Implemented locally and covered by unit tests. A 10,000-payment simulated input was used in a local netting test; this does not mean 10,000 payments were processed through AWS.

**Stage 5 — Automated Reconciliation**

AWS Services: Amazon S3, AWS Lambda and DynamoDB.

The reconciliation component is designed to read a simulated bank-statement file, compare it against internal transaction records and identify discrepancies such as missing payments, duplicate entries and amount mismatches.

**Implementation status:** Reconciliation logic and AWS integration code created. A complete live S3-triggered reconciliation demonstration has not yet been verified.

**Stage 6 — Monitoring and Reporting**

The architecture includes CloudWatch monitoring, error-handling mechanisms and S3-based report generation.

A richer performance dashboard has been considered but should remain optional.

**Implementation status:** Monitoring and reporting components are present in the infrastructure design. Full dashboard functionality and end-to-end operational monitoring have not been demonstrated.

### 4.3 Verified Results So Far

The available development logs confirm:

| Activity | Verified outcome |
|---|---|
| Python environment setup | Completed |
| AWS SAM template validation | Passed |
| AWS SAM build | Passed |
| Existing automated tests | 8 passed |
| Git commit and push | Completed |
| AWS CloudFormation deployment | Successful |
| Initial API authorization test | HTTP 401 |
| Corrected authenticated payment request | HTTP 202 Accepted |
| Payment created through API | `demo-payment-0001`, ₹1,500, status `PENDING` |
| Complete AWS payment lifecycle | Not yet verified |
| Liquidity-aware partial settlement | Not yet implemented |
| Automated crash-safe recovery | Not yet verified |
| Full performance benchmark | Not yet completed |

The current project therefore has an implemented and deployed foundation, but further integration testing and development are required.

---

## 5. Proposed Novelty and Enhancements

The project will introduce three distinguishing features.

### Novelty 1 — Liquidity-Aware Partial Settlement

**Primary project-level novelty**

Existing ClearPay functionality calculates settlement obligations through predefined netting strategies. The proposed enhancement will extend this functionality to handle situations where banks do not have enough available liquidity to settle all transactions in a batch.

Instead of delaying every payment, the system will identify a feasible subset based on available liquidity and settle those transactions.

The remaining payments will be deferred to subsequent settlement windows.

This mechanism will include:

- Calculation of each bank's net settlement obligation.
- Verification of available settlement liquidity.
- Identification of banks with liquidity deficits.
- Selective removal of payments until the remaining batch is feasible.
- Reintroduction of feasible deferred payments.
- Bounded group-aware restoration of mutually offsetting bilateral payments.
- Recording and reconsideration of deferred payments in future settlement windows.

**Expected benefit:** Greater settlement completion under liquidity constraints compared with an all-or-nothing baseline.

### Novelty 2 — Fault-Tolerant and Idempotent Settlement Recovery

The existing AWS infrastructure will be extended to make settlement execution recoverable even after interruptions.

Enhancements will include:

- Deterministic settlement window identifiers.
- An active-window lock to prevent overlapping settlement execution.
- Immutable settlement plans stored in S3.
- Conditional payment claiming.
- Separate payment-level and settlement-window state tracking.
- Deterministic settlement markers to prevent duplicate bank balance updates.
- Atomic bank-level net settlement for small bank networks.
- Chunk-based payment finalization.
- Checkpoint-based recovery.
- Idempotent deferred-payment accounting.

**Expected benefit:** Prevention of duplicate financial effects during retries and controlled recovery from partial workflow failures.

### Novelty 3 — Exception-Based Automated Reconciliation

The existing reconciliation component will be extended with deterministic discrepancy injection and structured exception classification.

The system will identify:

- Payments missing from a simulated bank statement.
- Duplicate transaction references.
- Amount mismatches.
- Ledger records without corresponding statement entries.

This will be tested using separately generated simulated statements with controlled discrepancies.

**Expected benefit:** Automated identification of settlement-record inconsistencies and reduced dependence on manual comparison.

These are distinguishing features of the ClearPay implementation. They are not claims that the underlying financial algorithms or distributed-system techniques are entirely new.

---

## 6. Proposed System Architecture

ClearPay will retain its existing AWS processing pipeline and introduce a liquidity-aware decision layer between payment collection and settlement finalization.

### High-Level Architecture

**Payment Ingestion**

Client → API Gateway → Validation Lambda → DynamoDB Payments Table → SQS

**Ledger Posting**

SQS → Posting Lambda → DynamoDB Transaction → Payment and Ledger Records

**Settlement Workflow**

EventBridge / Manual Trigger → Step Functions → Collect Eligible Payments → Liquidity-Aware Selection → Freeze Settlement Plan → Apply Net Bank Movements → Finalize Payments

**Reconciliation**

Simulated Bank Statement → S3 → Reconciliation Lambda → Exception Report

**Monitoring**

CloudWatch Logs, Error Metrics, Dead-Letter Queue and Settlement Reports

### AWS Services Used

| AWS Service | Purpose |
|---|---|
| API Gateway | Receive payment requests |
| AWS Lambda | Execute application logic |
| Amazon DynamoDB | Store payments, ledger entries, bank liquidity and settlement states |
| Amazon SQS | Queue payment-processing tasks |
| SQS Dead-Letter Queue | Capture repeatedly failed messages |
| AWS Step Functions | Orchestrate settlement and recovery |
| Amazon EventBridge | Trigger settlement workflows when enabled |
| Amazon S3 | Store frozen settlement plans, simulated statements and reports |
| Amazon CloudWatch | Application logs and operational monitoring |
| AWS SAM / CloudFormation | Infrastructure deployment and configuration |

The design will use a small number of simulated banks for the cloud demonstration, with larger datasets processed locally.

---

## 7. Proposed Settlement Optimization Algorithm

### 7.1 Problem Definition

Consider a payment batch containing transactions between multiple banks.

Each payment has:

- Payment identifier
- Sending bank
- Receiving bank
- Payment amount
- Business priority
- Creation timestamp
- Current payment status

Each bank has an available settlement-liquidity balance.

The objective is to select a subset of payments that maximizes the total underlying payment value settled without requiring any bank to fund more than its available liquidity.

### 7.2 Mathematical Model

Let:

- \(P\): Set of eligible payments.
- \(v_p\): Value of payment \(p\).
- \(A_b\): Available settlement liquidity of bank \(b\).
- \(x_p\): Binary variable indicating whether payment \(p\) is selected.

The optimization objective is:

\[
\max \sum_{p \in P} v_p x_p
\]

Subject to, for every bank \(b\):

\[
\sum_{p:\,from(p)=b} v_p x_p
-
\sum_{p:\,to(p)=b} v_p x_p
\leq A_b
\]

\[
x_p \in \{0,1\}
\]

This formulation assumes simultaneous net settlement of the selected batch and non-negative available liquidity.

### 7.3 Proposed Heuristic

A deterministic removal-and-add-back algorithm will be implemented.

**Step 1 — Initialization**

Begin with all eligible payments selected.

**Step 2 — Net Position Calculation**

Calculate the net debit or credit position of every participating bank.

**Step 3 — Liquidity Verification**

Compare each bank's required net debit against its available settlement liquidity.

**Step 4 — Payment Removal**

If a bank exceeds its available liquidity:

1. Select the bank with the largest liquidity shortfall, breaking ties by bank identifier.
2. Select an outgoing payment for removal using a deterministic rule.
3. Remove the selected payment.
4. Recalculate net positions.
5. Repeat until the remaining batch is feasible.

Two removal policies will be implemented and compared:

- Priority-first removal.
- Smallest-payment-covering-the-deficit removal.

**Step 5 — Single-Payment Add-Back**

Attempt to restore individual deferred payments in deterministic priority and age order. Retain any payment whose addition preserves liquidity feasibility.

**Step 6 — Group-Aware Add-Back**

For each unordered pair of banks, consider the deferred payments between those two banks as a group.

Try groups in descending order of combined underlying payment value, with bank identifiers used to break ties.

Reintroduce a group only when the resulting settlement remains feasible for all banks.

**Step 7 — Settlement Plan Generation**

Generate selected-payment IDs, deferred-payment IDs, bank-level net obligations and settlement metrics.

**Step 8 — Settlement Execution**

Freeze the plan and apply it using guarded, idempotent database operations.

The heuristic is not guaranteed to produce a globally optimal subset. Its effectiveness will be evaluated against baseline approaches and a local exact optimizer.

### 7.4 Illustrative Example

Consider these transactions:

| Transaction | Amount |
|---|---:|
| Bank A → Bank B | ₹100 |
| Bank B → Bank A | ₹80 |
| Bank C → Bank D | ₹30 |
| Bank D → Bank C | ₹20 |

Available settlement liquidity:

| Bank | Liquidity |
|---|---:|
| A | ₹10 |
| B | ₹0 |
| C | ₹15 |
| D | ₹0 |

The complete batch requires A to fund ₹20 and C to fund ₹10. Since A has only ₹10, the full batch is infeasible.

An all-or-nothing baseline would settle none of the payments.

The proposed partial settlement mechanism can select both C–D transactions. These payments have an underlying value of ₹50 but require only a ₹10 net transfer from C to D.

| Approach | Underlying payment value settled |
|---|---:|
| All-or-nothing | ₹0 |
| Liquidity-aware partial settlement | ₹50 |

This example demonstrates the potential benefit of partial settlement. It is an illustrative scenario, not a measured performance result.

---

## 8. Transaction Consistency and Recovery Design

Correct financial accounting is essential to the project.

### 8.1 Separation of Ledger and Settlement Liquidity

The system will distinguish payment ledger accounting from interbank settlement liquidity.

Posting records the payment obligation and its associated ledger effects.

Settlement applies the corresponding net movement against a separate bank-level `available_liquidity_paise` field.

This separation prevents cash-settlement balances from being debited twice.

### 8.2 Payment Lifecycle

The payment state model will include:

`PENDING → POSTED → IN_WINDOW → SETTLED`

A payment may remain `POSTED` if deferred or return to `POSTED` from `IN_WINDOW` through an authorized conditional transition before bank settlement occurs.

Relevant audit information, including the original posting time and deferral history, will be preserved.

### 8.3 Reliable Settlement Execution

The settlement workflow will follow this order:

1. Acquire an active-window lock with a recoverable lease and ownership token.
2. Read eligible payments and the current liquidity snapshot.
3. Compute the feasible settlement subset.
4. Write an immutable, versioned plan to S3 using a conditional create operation.
5. Claim selected payments conditionally.
6. Verify the claims and current settlement eligibility.
7. Atomically apply bank-level net liquidity movements, write deterministic settlement markers and advance the window state.
8. Finalize selected payment statuses in bounded chunks.
9. Update deferred-payment records idempotently.
10. Verify the results and mark the settlement window complete.

Retries will reuse the frozen plan after bank settlement begins.

Any plan replacement before that point will require a new plan version and guarded cleanup. Following successful bank movements, recovery must only progress toward completion.

The initial AWS demonstration will use a sufficiently small number of banks to fit the bank-level updates and settlement markers within one DynamoDB transaction.

### 8.4 Failure Scenarios

The system will be tested against:

- Duplicate payment requests.
- Repeated SQS message delivery.
- Lambda failures during payment posting.
- Failures after payment claiming.
- Failures before bank settlement.
- Failures after bank settlement but before all payment statuses are finalized.
- Concurrent settlement-window attempts.
- Retried deferred-payment accounting.
- Insufficient settlement liquidity.

Financial operations must remain consistent after recovery, with no duplicate balance effects.

---

## 9. Evaluation and Performance Analysis

The project will be assessed through algorithmic experiments, functional testing and controlled failure scenarios.

### 9.1 Algorithms to Be Compared

1. **All-or-nothing settlement:** Settle the complete batch only if all banks can fund their net obligations.
2. **Cumulative greedy settlement:** Evaluate payments sequentially and accept a payment only if the cumulative selected set remains feasible.
3. **Priority-first removal heuristic:** Remove payments until the batch becomes feasible, prioritizing business rules.
4. **Smallest-covering removal heuristic:** Prefer removals that resolve liquidity shortages with less unnecessary disruption.
5. **Group-aware partial settlement:** Extend the removal heuristic with individual and bilateral-group add-back.
6. **Exact optimization benchmark:** Use a locally executed mixed-integer linear programming solver for instances where computationally practical.

### 9.2 Performance Metrics

| Metric | Purpose |
|---|---|
| Settled payment value (%) | Proportion of underlying payment value successfully settled |
| Settled payment count (%) | Proportion of eligible payments successfully settled |
| Net settlement liquidity requirement | Liquidity needed to complete the selected batch |
| Deferred payment count and value | Remaining unsettled obligations |
| Deferred payment age | Fairness and payment-delay analysis |
| Algorithm execution time | Computational performance |
| Optimality gap | Difference between heuristic and proven optimal settlement value |
| Duplicate financial effects | Correctness under retries and failures |
| Recovery completion | Ability to finish interrupted settlement workflows |
| Reconciliation detection accuracy | Performance in identifying deliberately injected discrepancies |

### 9.3 Experimental Design

**Experiment 1 — Liquidity Variation**

Test settlement behavior at varying liquidity levels, such as 20%, 40%, 60%, 80% and 100% of a chosen funding requirement.

Measure the amount and number of payments settled by each algorithm.

**Experiment 2 — Algorithm Comparison**

Compare the different heuristic variants against all-or-nothing and cumulative greedy approaches.

Measure settlement value, payment count and execution time.

**Experiment 3 — Optimality Analysis**

Use brute-force evaluation on very small instances and `scipy.optimize.milp` on larger manageable instances to determine how close heuristic solutions are to the exact optimum.

Verify returned subsets using exact integer arithmetic because the solver uses floating-point numerical tolerances.

**Experiment 4 — Multiple Settlement Windows**

Simulate payments deferred due to insufficient liquidity, provide additional liquidity in a later window and verify that eligible payments can subsequently settle.

**Experiment 5 — Fault Recovery**

Inject failures before and after critical settlement operations.

Verify that bank liquidity changes occur exactly once per committed settlement, even when workflows retry.

**Experiment 6 — Reconciliation**

Generate a simulated external statement, deterministically inject discrepancies and verify that the reconciliation component identifies them correctly.

### 9.4 Benchmarking Scale

Large-scale algorithm experiments, including approximately 10,000 simulated payments, will run locally.

AWS testing will use smaller payment batches and bank networks to demonstrate that the actual serverless processing and settlement pipeline works.

A fixed random seed and documented experimental configuration will be used to make results reproducible.

No performance improvements will be claimed until they are measured.

---

## 10. Proposed Implementation Plan

### Phase 1 — Verify the Existing Infrastructure

**Status: Partially completed**

Tasks:

- Verify that accepted API payments progress from `PENDING` to `POSTED`.
- Confirm queue processing and ledger consistency.
- Test GET payment status.
- Run the existing settlement workflow manually.
- Validate S3 reconciliation end to end.
- Review IAM permissions, API-key handling and database billing configuration.

**Deliverable:** Verified baseline payment processing and settlement workflow.

### Phase 2 — Implement Liquidity-Aware Optimization

**Status: Not yet started**

Tasks:

- Add a separate simulated settlement-liquidity balance.
- Introduce optional payment priority.
- Implement liquidity feasibility calculations.
- Implement both payment-removal variants.
- Implement individual and bilateral-group add-back.
- Build the cumulative greedy and all-or-nothing baselines.
- Create unit tests for edge cases and known examples.

**Deliverable:** Tested local liquidity-aware partial settlement module.

### Phase 3 — Integrate Partial Settlement with AWS

**Status: Not yet started**

Tasks:

- Connect the selection algorithm to the existing settlement workflow.
- Introduce payment-level window claiming.
- Implement deterministic window IDs.
- Persist immutable settlement plans.
- Implement atomic bank-level liquidity movement.
- Finalize selected payments and defer remaining obligations.
- Support simulated liquidity top-ups.

**Deliverable:** Functional liquidity-aware AWS settlement demonstration.

### Phase 4 — Implement Fault-Tolerant Recovery

**Status: Not yet started**

Tasks:

- Add guarded payment state transitions.
- Introduce window locks and deterministic settlement markers.
- Implement resumable settlement finalization.
- Configure SQS partial batch failures.
- Add controlled crash-injection tests.
- Confirm that repeated executions cannot duplicate financial effects.

**Deliverable:** Verified retry-safe and recoverable settlement workflow.

### Phase 5 — Reconciliation and Testing

**Status: Existing foundation developed; enhancements pending**

Tasks:

- Generate simulated bank statements independently of reconciliation results.
- Inject missing, duplicate and mismatched transactions.
- Generate reconciliation exception reports.
- Validate detection correctness.
- Add integration tests for the complete payment lifecycle.

**Deliverable:** Tested automated reconciliation module.

### Phase 6 — Performance Evaluation and Documentation

**Status: Pending**

Tasks:

- Generate reproducible local transaction datasets.
- Execute liquidity-level experiments.
- Compare baseline and proposed algorithms.
- Evaluate heuristic quality using an exact solver.
- Generate performance graphs using Python and Matplotlib.
- Document the completed architecture, results and limitations.

**Deliverable:** Working project demonstration, benchmark results and final project report.

---

## 11. AWS Free Tier and Cost Management

The project will be designed to minimize cloud expenditure.

However, AWS Free Tier eligibility depends on the account plan, service, region, usage and remaining promotional credits. Therefore, using AWS Free Tier-eligible services does not independently guarantee a zero-cost deployment.

### Cost-Minimization Strategy

| Component | Planned cost-control method |
|---|---|
| API Gateway | Small number of manually generated requests |
| Lambda | Short-running functions with controlled concurrency |
| DynamoDB | Verify billing mode and evaluate provisioned capacity within applicable allowances |
| SQS | Small queues, limited polling and DLQ monitoring |
| Step Functions | Manual settlement execution rather than frequent schedules |
| EventBridge | Settlement schedule disabled by default |
| S3 | Small simulated input files and output reports |
| CloudWatch | Short log-retention period and limited alarms/metrics |
| Optimization benchmarks | Local Python execution |
| Charts and visualization | Local Matplotlib or static HTML |
| Athena and QuickSight | Excluded from the minimum viable project |

Additional precautions:

- Check the actual AWS account plan and remaining credits.
- Inspect all DynamoDB table and GSI capacity allocations.
- Configure billing alerts and review usage regularly.
- Keep chaos-injection settings disabled outside controlled tests.
- Do not generate large cloud workloads merely for benchmarking.
- Delete unused resources when they are no longer needed.
- Rotate any previously exposed API key.

**Budget objective:** Complete the project without out-of-pocket AWS charges, subject to verified account eligibility and continuous cost controls.

---

## 12. Sustainable Development Goal Alignment

### Primary: SDG 9 — Industry, Innovation and Infrastructure

ClearPay aligns with SDG 9 through its focus on reliable digital financial infrastructure and software innovation.

**Relevant targets:**

- **Target 9.1:** Development of reliable, sustainable and resilient infrastructure.
- **Target 9.5:** Enhancement of technological capabilities, research and innovation.

**Project contribution:** The system demonstrates how event-driven cloud infrastructure, fault tolerance and settlement optimization can improve the technical efficiency and reliability of a simulated payment-processing platform.

The project supports the themes of these targets but does not directly measure the official UN target indicators.

### Secondary: SDG 8 — Decent Work and Economic Growth

ClearPay has a secondary and indirect alignment with SDG 8 because efficient financial infrastructure can support institutional productivity and financial-service capacity.

**Relevant targets:**

- **Target 8.2:** Economic productivity through technological upgrading and innovation.
- **Target 8.10:** Strengthening domestic financial institutions and access to financial services.

**Project contribution:** The prototype explores technical improvements that could support more efficient financial-system operations.

The project does not independently demonstrate increased GDP, employment or financial inclusion.

---

## 13. Expected Outcomes

Upon successful completion, the project is expected to deliver:

1. A functioning AWS serverless payment ingestion and clearing pipeline.
2. Reliable processing of duplicate and asynchronously delivered payment requests.
3. Atomic financial ledger operations.
4. Implementations of conventional settlement netting strategies.
5. A liquidity-aware algorithm that selects feasible subsets of payments.
6. Support for deferring and later settling payments when sufficient liquidity becomes available.
7. Crash-safe settlement execution with deterministic plans and idempotent state transitions.
8. Automated reconciliation reports identifying simulated discrepancies.
9. Experimental results comparing settlement approaches under varying liquidity constraints.
10. Reproducible local benchmarks and a small-scale AWS demonstration.

The proposed system is expected to outperform an all-or-nothing baseline in appropriately constructed liquidity-shortage scenarios. The size and consistency of any improvement will be determined through experimentation rather than assumed.

---

## 14. Project Scope and Limitations

### In Scope

- Simulated interbank payment transactions.
- INR-denominated values represented in integer paise.
- Payment ingestion, validation and asynchronous processing.
- Transactional ledger accounting.
- Netting and liquidity-aware settlement selection.
- Deferred-payment handling.
- Small-scale atomic bank settlement.
- Failure injection and safe retry handling.
- Automated reconciliation.
- Local optimization benchmarks.
- AWS serverless deployment.

### Out of Scope

- Integration with real banking systems, RBI, UPI or payment networks.
- Movement of actual money.
- Production-grade banking authentication or regulatory certification.
- Real-world liquidity forecasting.
- High-frequency or real-time gross settlement at banking-system scale.
- Distributed atomic settlement involving hundreds of banks.
- Guaranteed globally optimal selection on large payment batches.
- A commercial banking dashboard or full financial analytics platform.

The system is a simulated financial infrastructure application intended for educational demonstration and technical evaluation.

---

## 15. Technology Stack

| Category | Technologies |
|---|---|
| Programming language | Python 3.12 |
| Cloud platform | AWS |
| API layer | Amazon API Gateway |
| Compute | AWS Lambda |
| Database | Amazon DynamoDB |
| Message queue | Amazon SQS |
| Orchestration | AWS Step Functions |
| Scheduling | Amazon EventBridge |
| Object storage | Amazon S3 |
| Monitoring | Amazon CloudWatch |
| Infrastructure as code | AWS SAM / CloudFormation |
| AWS integration | Boto3 |
| Testing | Pytest |
| Optimization benchmark | SciPy MILP |
| Performance analysis | NumPy, Matplotlib |
| Source control | Git and GitHub |

---

## 16. Relevant Technical Reference

Güntzer, M. M., Jungnickel, D., & Leclerc, M. (1998). *Efficient algorithms for the clearing of interbank payments.* European Journal of Operational Research, 106(1), 212–219.

DOI: https://doi.org/10.1016/S0377-2217(97)00265-8

This work establishes that optimizing payment clearing under limited bank deposits is an existing algorithmic problem.

ClearPay's contribution is the practical implementation and evaluation of liquidity-aware partial settlement integrated with fault-tolerant AWS-based payment processing and automated reconciliation.

---

## 17. Conclusion

ClearPay is proposed as a cloud-based payment clearing, liquidity-aware settlement and reconciliation system that combines established financial settlement techniques with reliable distributed transaction processing.

The existing implementation provides the foundation for payment ingestion, asynchronous ledger posting, settlement orchestration, netting and reconciliation. The proposed enhancements will address a specific operational limitation: the inability of an all-or-nothing settlement process to complete otherwise feasible transactions when some banks lack sufficient liquidity.

By incorporating group-aware partial settlement, payment deferral, deterministic settlement plans and fault-tolerant execution, the project will demonstrate how payment completion and processing reliability can be improved within a simulated financial environment.

The completed system will be evaluated using reproducible tests and measured performance results, with large-scale computation performed locally and a small AWS deployment used to demonstrate integration.

The project's primary focus is **efficient, reliable and recoverable payment settlement under limited liquidity**, with supporting alignment to SDG 9 and SDG 8.