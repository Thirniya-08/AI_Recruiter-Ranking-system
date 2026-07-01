# AI_Recruiter-Ranking-system
The Candidate Ranking System is designed to identify and rank the top 100 most suitable candidates from a large pool (≈100,000 candidates) based on their relevance to a given job requirement.

INDIA.RUNS

Track 1 — Data & AI Challenge

Redrob AI

Offline, Explainable Candidate Ranking & Fraud-Aware Recruitment Intelligence

Detailed Solution Document

Team: Dijikstras

Team Leader: Thirniya P

Problem Statement: Track 1 — Data and AI Challenge



Table of Contents





1. Executive Summary

Redrob AI is an offline, intelligent candidate-ranking system built to automate and standardize the early stages of recruitment. Rather than requiring a recruiter to manually sift through dozens or hundreds of resumes, the system ingests a Job Description (JD) together with a batch of candidate profiles — in whatever file format they arrive in — and produces a ranked, explained, and fraud-checked shortlist of the strongest matches.

The design brief behind Redrob AI rests on four pillars that recur throughout this document and throughout the underlying system architecture:

Automation — the system accepts candidate profiles in multiple formats (JSON, ZIP archives, Excel spreadsheets, PDF resumes, and Word documents) and automatically extracts structured JD requirements, removing the manual data-entry burden from recruiters.

Semantic understanding — matching is not limited to literal keyword overlap. The system groups conceptually related skills (for example, recognizing that “TensorFlow” and “Deep Learning” both signal AI/ML relevance) so that candidates are not unfairly penalized for phrasing differences.

Fraud awareness — a dedicated honeypot detection mechanism screens every profile for suspicious, fabricated, or low-credibility signals before scoring, and penalizes rather than silently deletes flagged profiles, preserving transparency.

Explainability — every ranking decision is accompanied by a human-readable justification that traces back to the underlying component scores, so recruiters can see not just who ranked highest but why.

At a structural level, the solution is organized into five major functional layers — JD and candidate ingestion, data validation and fraud detection, multi-factor scoring, explainable ranking, and result export — each of which is elaborated in the sections that follow.

2. Solution Overview: Redrob AI

Redrob AI positions itself as a direct response to the shortcomings of conventional applicant tracking and keyword-matching tools. The table below summarizes how the proposed solution differs from traditional candidate-matching systems across six evaluation dimensions.

Table 1. Comparative positioning of Redrob AI against traditional candidate-matching systems.

Four key differentiators emerge from this comparison and recur as themes across the rest of the solution:

Fraud-aware ranking — suspicious or fabricated profiles are identified and penalized rather than passed through uncritically.

Explainable decision support — every score is accompanied by reasoning that a recruiter can audit.

Offline-first deployment — the entire pipeline runs locally without dependency on external APIs or cloud LLM calls, which reduces both latency and data-privacy risk.

Multi-signal, semantic skill scoring — matching goes beyond literal string comparison to capture conceptual relationships between skills.

Redrob AI is described as an offline intelligent candidate ranking system that automates recruitment by accepting candidate profiles in multiple formats and extracting Job Description requirements. The system analyzes candidate profiles against the JD using semantic skill matching to identify must-have, nice-to-have, and missing skills. It includes a honeypot detection mechanism to detect suspicious, fake, or low-credibility profiles and applies penalties instead of removing them outright — a design choice that keeps the process auditable rather than silently discarding data. Finally, candidates are evaluated using multi-factor scoring across title, skills, experience, location, and behavior, ranked by a final composite score, and presented with explainable reasoning for transparent recruiter decision-making.

3. JD Understanding & Candidate Evaluation

Before any candidate can be scored, the system must first understand what the job actually requires. This section covers how Redrob AI extracts structured requirements from a free-text Job Description, which signals it treats as most predictive of candidate fit, and how it goes beyond naive keyword matching to capture semantic relevance.

3.1 Key Requirements Extracted from the JD

The system parses the JD and organizes its requirements into five structured categories. Each category is visually represented with its own icon and color coding on the dashboard, and each carries a distinct role in downstream scoring.

Table 2. Structured JD requirement categories extracted by the system.

This structured extraction step matters because it converts an unstructured JD (which might be a paragraph of prose) into discrete, scoreable fields. Each of these five categories subsequently maps onto one or more of the weighted scoring components described in Section 4.

3.2 Which Candidate Signals Matter Most for Relevance

Once JD requirements are structured, the system evaluates each candidate against five signals, ordered here by their conceptual role in the scoring pipeline:

Title Relevance — measures how closely the candidate's job title matches the JD role. A candidate whose most recent title closely mirrors the target role (e.g., “ML Engineer” applying for an “AI Engineer” position) is treated as more relevant than one with a distantly related title.

Skill Match Score — the overlap between candidate skills and JD requirements. This is described as the strongest individual signal in the model, since direct skill alignment is usually the clearest evidence of role fit.

Experience Relevance — measures both the number of years and the domain relevance of a candidate's work experience, so that raw tenure alone does not dominate the score.

Behavioral Completeness — measures how complete, consistent, and high-quality a candidate's profile is; incomplete or inconsistent profiles are treated as weaker signals of trustworthy information.

Location Match — measures regional alignment between candidate and role, applied only when location is relevant to the position.

3.3 Evaluating Fit Beyond Keyword Matching

A purely literal keyword match would penalize strong candidates who describe equivalent skills using different terminology. Redrob AI addresses this with four complementary techniques:

Semantic Skill Grouping — conceptually related terms are grouped together, so, for example, “TensorFlow” and “Deep Learning” both contribute to a candidate's AI-relevance signal even though they are not identical strings.

Weighted Signal Aggregation — not all signals are treated equally; skills carry a higher weight than location, reflecting their relatively greater predictive value for role fit.

Profile Quality Validation — incomplete or suspicious profiles receive penalties during scoring rather than being excluded outright, keeping the process transparent and reviewable.

Explainable Reasoning Generation — every ranking decision includes supporting evidence, ensuring that the “why” behind a score is always available to the recruiter, not just the final number.

4. Ranking Methodology

This section describes the mechanics of how the system retrieves candidate data, scores it, and produces a ranked list — including the specific heuristics and algorithms used and the mathematical formula that combines every signal into one final score.

4.1 Retrieval, Scoring, and Ranking Pipeline

At a high level, candidates move through five sequential steps from ingestion to final ranking:

Retrieve Candidate Data — profiles are extracted from uploaded files, regardless of their original format.

Validate Profiles — the honeypot detector flags suspicious candidates during this pass, before scoring begins.

Score Candidates — each candidate is evaluated using the individual component scorers (title, skills, experience, location, behavior).

Combine Scores — the individual component scores are merged into a single composite score using the weighted formula described in Section 4.3.

Sort Candidates — candidates are ranked in descending order of composite score, producing the final shortlist.

4.2 Models, Algorithms, and Heuristics Used

Rather than relying on a single machine-learning model, the system deliberately combines three lightweight, interpretable approaches. This is a notable design decision: it favors transparency and offline operability over the marginal accuracy gains that a heavier, cloud-hosted large language model might provide.

Table 3. The three complementary techniques underlying the ranking engine.

A point emphasized on this slide is that the system is fully local and offline, and that no external large language models or third-party APIs are used at any point in the pipeline. This has two direct benefits: it removes network latency and dependency risk, and it avoids sending potentially sensitive candidate data to a third-party service — an important consideration for recruitment data, which is often personally identifiable.

4.3 Combining Signals into a Final Ranking

All individual component scores are combined using a weighted linear aggregation formula:

Final Score = (Title Score × Weight) + (Skills Score × Weight) + (Experience Score × Weight) + (Location Score × Weight) + (Behavioral Score × Weight) − Honeypot Penalty

This formula has three properties that the team highlights as important design guarantees:

The score is normalized between 0 and 1, making results easy to compare across candidates and across different JDs.

A higher score always means a better candidate fit — there is no inverted or ambiguous scale to interpret.

The weighted structure ensures balanced ranking: no single signal (such as years of experience) can dominate the outcome purely by virtue of a large raw value, because each component is normalized and then weighted before summation.

The accompanying dashboard mockup shows this scoring in action: a “Top Ranked Candidates” table lists each candidate's rank, name, current title, location, years of experience (YOE), a normalized composite score (e.g., 0.6729678400), and an “Inspect” action that presumably opens the detailed, explainable breakdown for that candidate.

5. Explainability & Data Validation

A central design goal of Redrob AI is that no ranking decision should be a black box. This section explains how the system generates human-readable justifications, how it avoids fabricating explanations that are not grounded in real data, and how it identifies and handles low-quality or suspicious candidate profiles.

5.1 How Ranking Decisions Are Explained

To make the ranking process transparent and understandable, the system uses an Explainable AI (XAI) mechanism. Instead of only showing a final rank or score, it provides a detailed explanation of why a candidate received that particular ranking.

How it works: after calculating the individual component scores, the system examines three categories of evidence and turns them into concise, human-readable reasoning:

Strong matching areas — identifies where the candidate performed well, giving positive, specific evidence for the ranking.

Weak or missing areas — detects important missing skills or areas of low relevance, so the recruiter understands the candidate's gaps as well as their strengths.

Penalty reasons — highlights any suspicious patterns detected during validation, connecting the honeypot mechanism directly to the final explanation shown to the recruiter.

The explanation is generated by analyzing the contribution of each individual scoring component. Three of these components are broken out explicitly:

Title Relevance Score and Skills Score — capturing how well the candidate's previous job titles match the JD, and how many required and preferred skills match.

Behavioral Score and Honeypot Penalty — measuring profile completeness, consistency, and quality, and reducing the score if suspicious or low-credibility patterns are detected.

Experience Score — assessing whether the candidate has sufficient and relevant work experience for the role.

5.2 Preventing Hallucinations and Unsupported Justifications

Because the explanations are generated automatically, there is a risk that an AI system could “invent” plausible-sounding but false justifications. Redrob AI is explicitly designed to prevent this failure mode through two mechanisms:

Evidence-Based Explanation Generation

All explanations are derived only from actual profile data — nothing is generated speculatively.

No Generative Assumptions and Deterministic Logic

The system does not invent skills or experiences that are not present in the source data.

Every explanation is traceable back to specific score components, so a recruiter can verify the reasoning against the underlying evidence.

This traceability ensures consistency: the same inputs will always produce the same explanation, unlike a free-form generative model that might phrase things differently each run.

5.3 Handling Inconsistent, Low-Quality, or Suspicious Profiles

The Honeypot Detector is the component responsible for identifying suspicious or low-credibility patterns in candidate profiles, in order to keep the overall ranking fair and transparent. It operates in two stages: detection, and response.

What It Detects

Table 4. The four categories of suspicious-profile detection performed by the Honeypot Detector.

What Happens Next

Once a profile has been analyzed, it moves through a four-stage response pipeline rather than being unilaterally rejected:

Candidate Profile Analyzed — the profile goes through multiple validation checks.

Issues Detected — if any suspicious pattern is found, the profile is flagged.

Profile Penalized — instead of deleting the profile, the system applies a penalty to the final score.

Flags Shown to Recruiters — all detected issues are surfaced clearly for full transparency.

Why This Approach

No genuine profile is removed without review — false positives remain visible and correctable rather than silently discarded.

Recruiters retain full visibility of potential risks associated with any given candidate.

The overall effect is greater transparency, fairness, and better-informed decision-making throughout the hiring funnel.

6. End-to-End Workflow

The complete workflow from JD input to ranked candidate output consists of fourteen discrete stages. This sequence effectively stitches together every mechanism described in the previous sections into a single operational pipeline.

Table 5. The fourteen-stage end-to-end processing workflow, from JD input to final recruiter decision.

Notice how this workflow interleaves validation and scoring: honeypot detection (step 6) occurs before scoring (step 7), which is why fraud signals can directly contribute a penalty term inside the final composite score rather than being applied as an afterthought.

7. System Architecture

The system architecture is organized into eight sequential layers, plus a set of supporting side components that serve the pipeline throughout its execution.

7.1 The Eight Core Layers

1. Recruiter / User Layer — the recruiter interacts with a Web Dashboard, through which candidate files (JSON, ZIP, XLSX, PDF, DOCX) are supplied.

2. Input Processing Layer — a Unified Uploader accepts all supported file formats, and a Document Parser extracts candidate profiles as well as the optional JD text.

3. Data Validation Layer — the Honeypot Detection Engine screens for missing fields, fake experience, skill inconsistencies, and duplicate patterns, and classifies each profile as either a REAL Candidate or a FAKE Candidate. Only REAL candidates proceed further down the pipeline.

4. Candidate Processing Pipeline — the Background Scoring Engine runs five parallel component scorers — Title/Career Scorer, Skills Scorer, Experience Scorer, Location Scorer, and Behavioral Scorer — whose outputs feed into a Composite Ranking Engine that computes the Final Score as a weighted sum minus the honeypot penalty.

5. AI Intelligence Layer — three engines operate here: the Skill Matcher, the Semantic Matching Engine, and the Explainable AI (XAI) module. Together they output which skills were must-have matched, which were nice-to-have matched, which skills are missing, and the underlying ranking reasoning.

6. Ranking Engine — the Candidate Rank Generator sorts all candidates by their final score.

7. Output Layer — the Web Dashboard presents the ranked candidates table, a candidate score breakdown, honeypot status, skill match analysis, and the explainable reasoning for each candidate.

8. Export Layer — a CSV Export Engine converts the ranked candidate list into a submission.csv file for downstream use.

7.2 Side Components

Running alongside the eight core layers, four supporting components provide infrastructure and observability across the pipeline:

FastAPI Backend — serves as the application programming interface layer connecting the dashboard to the processing pipeline.

System Metrics — tracks operational performance of the running system.

Evaluation Metrics — tracks the quality and accuracy of the ranking outputs.

Swagger API Docs — provides interactive, auto-generated documentation of the available API endpoints.

These side components connect into multiple layers of the core pipeline (illustrated as dashed “support” connections in the architecture diagram), indicating that they provide cross-cutting services — API access, monitoring, and documentation — rather than sitting at one single stage of the flow.

8. Results & Performance

8.1 Insights That Demonstrate Ranking Quality

Six outcomes are presented as evidence that the ranking system produces high-quality, trustworthy results:

Table 6. Six quality outcomes attributed to the ranking system, each with its own supporting mechanism and business result.

Taken together, the stated overall outcome is that the system delivers accurate, transparent, reliable, and efficient candidate ranking, improving both hiring quality and screening speed.

8.2 Meeting Runtime and Compute Constraints

Beyond ranking quality, the solution is also designed to satisfy strict runtime and resource constraints, which it addresses through five complementary design choices:

Offline Execution — the system runs locally without external APIs, which reduces both network delay and external dependency risk.

Lightweight Processing — rule-based heuristics and weighted scoring are used instead of heavy machine-learning models, keeping compute requirements low.

Streaming-Based Handling — candidates are processed one by one, which reduces peak memory usage compared to loading an entire candidate batch into memory at once.

FastAPI Performance — the choice of FastAPI as the backend framework enables faster API responses and efficient bulk processing.

Efficient Scoring — the simple weighted-aggregation formula (rather than a more computationally expensive model) ensures quick ranking computation even at scale.

9. Technologies Used

The following technologies, frameworks, and tools were selected for this solution, each chosen for a specific purpose within the pipeline:

Table 7. Technology stack and the purpose each component serves.

This stack is deliberately lightweight: Python and FastAPI provide a fast, well-supported backend; Pandas handles structured data processing for scoring; and a plain HTML/CSS/JavaScript frontend keeps the dashboard simple and dependency-light, consistent with the project's offline-first, low-compute design philosophy.

10. Submission Assets

The following assets accompany the submission:

GitHub Repository — full source code, README, and reproduction steps (repository link to be inserted by the team).

Demo Video — a walkthrough of the ranking pipeline and dashboard (video link to be inserted by the team).

Live Sandbox — a Dockerized FastAPI application, hosted for a sample run (sandbox link to be inserted by the team).

Reproduce Command — python rank.py --candidate’s candidates.jsonl --out submission.csv

Team — Dijikstras — Thirniya P (Team Lead), Sheraffin Ithai V, Sherin Sahai V.

Note: the GitHub repository link, demo video link, and live sandbox link are marked as placeholders in the original submission and should be filled in with the team's actual URLs before final submission.

11. Conclusion

RedrobAI presents a cohesive, end-to-end answer to the Track 1 Data & AI Challenge brief of building “what next India runs on” within the recruitment domain. Its core contribution is not any single novel algorithm, but the disciplined combination of several proven, lightweight techniques — rule-based heuristics, weighted multi-factor scoring, and semantic skill matching — into a pipeline that is simultaneously fast, offline-capable, fraud-aware, and fully explainable.

The fourteen-stage workflow and eight-layer architecture demonstrate a clear separation of concerns: ingestion and parsing are decoupled from validation, which is decoupled from scoring, which is decoupled from explanation generation and export. This modularity is what allows the honeypot penalty to be folded cleanly into the final composite score while still being reported to recruiters as a distinct, auditable signal.

Ultimately, the system's value proposition rests on trust: recruiters are given not just a ranked list, but a transparent, evidence-based account of how every score was produced, why any penalties were applied, and where a candidate's profile is strong or weak — turning an opaque automated filter into an auditable decision-support tool.
