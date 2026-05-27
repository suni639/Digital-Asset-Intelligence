# Product Requirement Document (PRD)

## Project Name: Institutional Digital Asset Intelligence Engine (Project ID: `DA-INTEL-01`)

### 1. Executive Summary & Objective

The objective of this project is to build an automated, localized intelligence engine using Google Antigravity 2.0. The system will autonomously scan, harvest, filter, and synthesize weekly developments in the regulated digital asset ecosystem.

Unlike standard market trackers, this system explicitly strips away retail crypto news (price movements, speculative trading, market-cap rumors, and memecoins). Instead, it isolates structural, post-trade, operational, and macroeconomic shifts across commercial banking, central banking, sovereign infrastructure, payment rails, and global regulatory frameworks. The end product is a high-signal, professional-grade executive brief pushed directly to the user's inbox every Friday morning.

---

### 2. Data Sourcing Strategy (The Ingestion Layer)

The engine must strictly limit its ingestion to the approved Master Source List. Agents are ordered to cross-reference multiple primary sources to validate structural developments.

#### 2.1 Approved Source Configurations

```
[Ingestion Engine]
   ├── 🏢 Free Tier Feed (Ledger Insights, Finextra, CoinDesk Standard, Fintech Nexus, Diginomica)
   ├── 🔓 Freemium Tier Feed (Blockworks, The Block, Cointelegraph Institutional Hub)
   └── 🏛️ System-Supplemented Ground Truth (BIS, Atlantic Council, Local Sandbox Portals)

```

1. **Enterprise & Wholesale Banking Infrastructure:**
* **Ledger Insights:** Primary ground truth for wholesale tokenization, digital securities, and institutional DLT.
* **Finextra:** Focus point for traditional capital markets tech and B2B banking deployments.
* **Diginomica & Fintech Nexus:** Evaluators of operational utility and B2B corporate cash management.


2. **Institutional Flows & Macro Policy:**
* **Blockworks & The Block:** Monitored strictly for asset management shifts, TradFi product pipelines, and corporate venture flows.
* **CoinDesk & Cointelegraph (Institutional/Regulatory Hubs):** Monitored exclusively for corporate regulatory filings, ETF flows, and sovereign baseline policies.


3. **System-Supplemented Ground Truth (Mandatory Additions):**
* **Bank for International Settlements (BIS):** Ingest all papers detailing Project Agorá, unified ledgers, and wholesale cross-border multi-CBDC experiments.
* **Atlantic Council Geoeconomics Center:** Ingest monthly/weekly deltas from the Global CBDC Tracker.
* **Major Law Firm Briefings:** Ingest digital asset regulatory updates from Clifford Chance, Linklaters, and DLA Piper.



---

### 3. Functional Requirements & Agent Logic (The Filtering Layer)

#### 3.1 Strict Content Filtering (The Noise Gate)

The main execution agent must enforce a binary filtering model. If an ingested article triggers "Forbidden Attributes," it must be discarded immediately before text compaction occurs.

* **Allowed Content Attributes (High-Signal):**
* Tokenised commercial bank liabilities (Deposit tokens, JPM Coin, GBTD).
* Delivery vs. Payment (DvP) and atomic settlement mechanics.
* Real-World Asset (RWA) tokenisation (sovereign bonds, private credit, funds like BlackRock's BUIDL).
* Central Bank Digital Currencies (Wholesale CBDC infrastructure over Retail).
* Legislative developments (EU MiCA enforcement timelines, UK Property Digital Assets Bill, US payment stablecoin frameworks, SEC asset custody rules/SAB 121 updates).
* Post-trade market utilities (DTCC, Euroclear, Swift network orchestration trials).


* **Forbidden Content Attributes (Noise):**
* Token spot price movements, percent gains/losses, or technical chart analysis.
* Retail exchange listings, retail trading volumes, or consumer wallet integrations.
* Speculative market commentary, influencer sentiment, and retail protocol updates (DeFi yield farms, memecoins, NFTs).



#### 3.2 State Management and Deduplication

To maintain a friction-free experience, the agent must not process the same news twice.

* The system will maintain a local file in the workspace directory titled `system_state.json`.
* Every Friday, upon successful execution, the current timestamp and a cryptographic hash or URL list of processed articles must be committed to `system_state.json`.
* Subsequent runs must scan this file and skip any URL or press release matching a historical entry.

---

### 4. Technical Architecture & Workspace Configuration

* **Runtime Environment:** Google Antigravity 2.0 (Local Workspace).
* **Local Project Directory:** `~/Documents/Digital_Asset_Briefs`
* **Agent Strategy:** Multi-Agent Orchestration with Dynamic Subagents enabled.
* *Lead Agent:* Manages state verification, coordinates subagents, performs final structural synthesis, and initiates delivery.
* *Subagent A (The Harvester):* Deploys the native `/browser` tool to safely scrape the master list URLs without hitting payload limits.
* *Subagent B (The Analyst):* Formats raw DOM text blocks into distilled semantic summaries.



---

### 5. Output and Delivery Specifications (The Push Layer)

#### 5.1 Document Formatting Requirements

The output file must be saved locally as a Markdown file titled `weekly_brief_[YYYY-MM-DD].md` and written entirely in **British English**. The layout must follow this exact structure:

```markdown
# Institutional Digital Asset Intelligence Briefing: [Date]

## 1. THE WEEKLY MACRO SYNTHESIS
[A high-level overview of the most critical structural shift this week. Focus heavily on systemic impact, infrastructure alignment, and geopolitical motivation.]

## 2. CORE PILLAR DEVELOPMENTS
* **Banking Infrastructure & Commercial Rails:** [Tokenised deposits, wholesale network expansions, intraday liquidity settlement.]
* **Institutional Asset Management & RWAs:** [Fund tokenisation updates, institutional custody shifts, security tokens.]
* **Sovereign Infrastructure & CBDCs:** [Wholesale CBDC trials, cross-border experiments, multi-ledger integrations.]
* **Regulatory & Legal Frameworks:** [Active compliance timelines, legal definitions of digital property, sandbox entries.]

## 3. STRUCTURAL & OPERATIONAL PAIN POINTS
* **Interoperability Silos:** [Where separate private blockchains or ledgers failed to bridge cleanly.]
* **Balance Sheet & Liquidity Friction:** [Disintermediation risks or regulatory constraints impacting capital efficiency.]
* **Post-Trade Plumbing Constraints:** [Settlement bottlenecks or custodian friction.]

## 4. NEW HIGH-SIGNAL TARGETS FOR TRACKING
* [List of 3-5 hyper-specific project names, working groups, or pieces of legislation discovered this week to add to keyword filters.]

```

#### 5.2 Push Delivery Mechanics

Upon creation of the Markdown file, the lead agent will invoke a temporary local Python SMTP execution environment using a securely configured app password:

* **Protocol:** SMTP via `smtp.gmail.com` (or specified server), Port 587, utilizing STARTTLS.
* **Credentials:** Read dynamically via local system environment variables (`SMTP_USER`, `SMTP_PASS`) to avoid hardcoded security vulnerabilities.
* **Format:** The email body must contain the cleanly parsed Markdown text directly.
* **Failsafe:** If the email script throws a connection error, the agent must save the logs to `error_log.txt` and retry delivery 3 times at 15-minute intervals. It must not delete the compiled markdown file under any circumstances.

---

### 6. Implementation Roadmap

* **Phase 1 (Day 1): Sandbox Initialization**
Create the Antigravity project environment, define the `system_state.json`, and set up local system environment variables for email authentication.
* **Phase 2 (Day 2-3): Scraper Optimization & Prompts**
Deploy Subagent A to scan the master list URLs. Fine-tune the "Noise Gate" parameters to ensure 100% filtering accuracy of speculative retail price tickers.
* **Phase 3 (Day 4): Automation Activation**
Deploy the `/schedule` cron task (`0 8 * * 1`). Perform a live end-to-end test execution to verify a well-formatted British English markdown brief lands directly in your email inbox by Monday morning.