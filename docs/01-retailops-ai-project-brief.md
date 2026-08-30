# RetailOps AI — Project Brief

## 1. Project name

**RetailOps AI**

AI-assisted Retail Operations Platform.

---

## 2. Vision

RetailOps AI is a portfolio-grade platform designed to demonstrate how Artificial Intelligence, Machine Learning and cloud-native software engineering can be applied to real retail operations.

The platform will support operational teams in three primary areas:

1. Category demand forecasting.
2. Automated supplier document review.
3. Purchase order, goods receipt and invoice reconciliation.

The system will not treat AI output as inherently correct.

High-risk, uncertain or financially significant decisions will be routed through a Human-in-the-Loop review process.

Every relevant AI recommendation, human correction and operational decision should be auditable and measurable.

---

## 3. Primary goals

The project should demonstrate competence across:

- Software Engineering
- Backend architecture
- Frontend development
- Machine Learning Engineering
- Generative AI
- Document AI
- Human-in-the-Loop systems
- AI evaluation
- MLOps
- AWS
- Infrastructure as Code
- CI/CD
- Observability
- Security

The objective is not to build an AI demo.

The objective is to build a realistic AI-enabled retail operations system.

---

## 4. Core business capabilities

### 4.1 Category Forecasting

Forecast future demand by:

- category
- store
- SKU
- time period

Inputs may include:

- historical sales
- promotions
- discounts
- stock availability
- holidays
- seasonality
- store characteristics
- product characteristics

The system should support:

- baseline models
- trained ML models
- backtesting
- model comparison
- forecast evaluation
- forecast versioning

Primary metrics may include:

- MAE
- RMSE
- WAPE
- forecast bias

### 4.2 Supplier Document Review

Suppliers may submit documents containing:

- SKUs
- product descriptions
- EANs
- categories
- costs
- VAT
- case packs
- minimum orders
- lead times

The system should:

1. ingest the document
2. extract structured information
3. validate deterministic business rules
4. perform AI-assisted semantic review
5. identify anomalies
6. produce findings
7. assign severity and confidence
8. route uncertain findings to human review

Potential findings include:

- invalid EAN
- missing fields
- suspicious category
- unexpected cost increase
- inconsistent VAT
- duplicate product
- unreasonable lead time

### 4.3 Purchase Order Reconciliation

The platform should reconcile:

- purchase orders
- goods receipts
- supplier invoices

The reconciliation engine should identify:

- quantity mismatches
- cost mismatches
- missing deliveries
- unexpected items
- invoice duplication
- tolerance violations

Deterministic business rules should perform calculations.

AI should primarily help with:

- classification
- prioritization
- explanation
- suggested resolution

---

## 5. Human-in-the-Loop

AI decisions should support statuses such as:

- `AUTO_APPROVED`
- `REVIEW_REQUIRED`
- `APPROVED`
- `REJECTED`
- `CORRECTED`

The review workflow should allow a user to:

- inspect source information
- inspect AI findings
- approve recommendations
- reject recommendations
- modify AI suggestions
- add comments

Every decision should preserve an audit trail.

---

## 6. AI evaluation

The platform should measure the quality of AI-assisted decisions.

Potential metrics:

- AI acceptance rate
- human override rate
- extraction accuracy
- classification accuracy
- false positive rate
- false negative rate
- confidence calibration
- average review time
- accuracy by supplier
- accuracy by category
- accuracy by model version

The system should preserve:

- model version
- prompt version
- prediction
- confidence
- human decision
- human correction
- timestamp

---

## 7. Initial technical stack

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- pytest

### Frontend

- Next.js
- TypeScript
- React

### Database

- PostgreSQL

### Machine Learning

- pandas
- scikit-learn
- LightGBM or XGBoost

### AWS

Future cloud integration may include:

- S3
- Textract
- Bedrock
- SageMaker
- RDS
- ECS Fargate
- ECR
- SQS
- EventBridge
- Step Functions
- CloudWatch
- IAM
- Secrets Manager

### Infrastructure

- Terraform

### CI/CD

- GitHub Actions

### Local development

- Docker
- Docker Compose

---

## 8. Architecture principles

### Cloud-independent core domain

Business logic should not depend directly on AWS SDKs.

Use interfaces/adapters where appropriate.

Example:

```text
DocumentStorage

Implementations:
- LocalDocumentStorage
- S3DocumentStorage
```

### Deterministic before AI

Do not use an LLM where normal software can provide a deterministic answer.

Example:

Incorrect:

```text
LLM determines whether:
80 != 75
```

Correct:

```text
Application calculates the mismatch.
LLM may explain why the mismatch matters.
```

### Human oversight

Financially significant or low-confidence recommendations should support human review.

### Auditability

Important system actions should be traceable.

### Reproducibility

Development, training and deployment workflows should be reproducible.

### Infrastructure as Code

Cloud infrastructure should eventually be defined through Terraform rather than manually configured.

---

## 9. Repository strategy

The project will use a monorepo.

Target structure:

```text
retailops-ai/
├── apps/
│   ├── api/
│   └── web/
├── ml/
│   ├── forecasting/
│   └── notebooks/
├── infra/
│   ├── modules/
│   └── environments/
├── data/
│   ├── raw/
│   ├── processed/
│   └── synthetic/
├── docs/
│   ├── architecture/
│   └── adr/
├── scripts/
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## 10. Development strategy

Development will happen incrementally.

Every implementation block should include:

1. objective
2. scope
3. implementation
4. tests
5. validation
6. documentation
7. Git commit

No large feature should be implemented without tests and validation.

---

## 11. First delivery

The first project milestone is:

**Block 0 — Development Environment & Repository Bootstrap**

Its objective is to establish a reliable engineering foundation before implementing retail functionality.
