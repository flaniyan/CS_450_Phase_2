# Phase 2 Project Todo List

**Current Status**: 52% of autograder portion (35% of total grade) = ~18.2% overall

---

## 📋 Overall Priority Todo List (Ranked by Importance)

### 🔴 Critical Priority (Must Complete for Passing Grade)
1. **Autograder Baseline Features (35% of grade)** - Currently at 52%
   - Fix any remaining autograder compliance issues
   - Ensure all endpoints match OpenAPI spec exactly
   - Test with autograder requirements
   - **Note**: Regardless of implementation seeming correct, the autograder score is the true determination

2. **Extended Features - Performance Track (15% of grade)**
   - Performance measurements with 100 concurrent clients
   - Bottleneck identification and optimization
   - Component experimentation (Lambda vs EC2, etc.)

3. **Delivery 2 Final Report (Part of 60% working delivery)**
   - Substantial report describing status
   - Relation to Sarah's requirements
   - Relation to specification
   - URI provided for autograder access

### 🟡 High Priority (Significant Grade Impact)
4. **Test Coverage (Part of 10% Engineering Practices)**
   - Achieve at least 60% line coverage
   - Front-end tests with Selenium

5. **Engineering Practices Completion (10% of grade)**
   - Dependabot configuration
   - ADA/WCAG Compliance verification
   - Test coverage documentation

6. **Week 9 Milestone Report (Part of 30% Design & Planning)**
   - Complete final weekly milestone report

### 🟢 Medium Priority (Quality Improvements)
7. **Performance Track Dashboard Integration**
   - Make workload triggerable from health dashboard

8. **Cost Management Documentation**
   - Create cost spreadsheet or use AWS tool
   - Calculate expected costs in advance

9. **Security Case Completion**
   - Develop system design in ThreatModeler platform
   - Assess ThreatModeler recommendations

### 🔵 Low Priority (Nice to Have)
10. **Post-mortem (10% of grade - End of Project)**
    - Projected 100% completion at end of project
    - Reflect on Plan vs Execution
    - Five Whys analysis

---

## Estimated Grade Breakdown

### Current Estimated Grade: **~63.7%**

**Breakdown:**
- **Design & Planning + Milestones (30%)**: ~95% complete = **28.5%**
  - Project plan: ~98% (missing only Role of LLMs)
  - Weekly milestones: ~89% (Week 9 in progress)
  
- **Working Delivery (60%)**:
  - **Autograder Baseline (35%)**: 52% complete = **18.2%**
  - **Extended Features (15%)**: ~0% complete = **0%**
  - **Engineering Practices (10%)**: ~70% complete = **7%**
  - **Subtotal**: **25.2%**

- **Post-mortem (10%)**: Projected 100% = **10%**

**Total Estimated Grade: ~63.7%**

**With Post-mortem Projection (100%): ~63.7%** (already included above)

**Note**: This estimate assumes:
- Autograder score remains at 52% (needs improvement)
- Performance track not yet started
- Engineering practices mostly complete
- Post-mortem will be completed at 100%

**To Improve Grade:**
- Focus on autograder compliance (could add 10-15% if improved to 80-90%)
- Complete Performance Track (adds 15% if done well)
- Complete remaining engineering practices (adds 2-3%)

**Potential Final Grade Range: 75-85%** (if autograder improves and Performance Track completed)

---

## 35% - Autograder Baseline Features (Currently at 52%)

**⚠️ IMPORTANT NOTE**: Regardless of implementation seeming correct, the autograder score is the true determination of completion for all items below.

### CR[U]D Operations 
*Note: Final grade determined by autograder*

- **Upload registry artifacts**
  - Implement artifact upload endpoint
  - Validate artifact format/structure
  - Store artifacts in AWS (S3 or equivalent)
  - Update registry metadata

- **Rate artifacts**
  - Return net score and sub-scores from Phase 1
  - Implement **Reproducibility metric** (0, 0.5, or 1)
    - Check if model runs with only demonstration code
    - Distinguish: no code/doesn't run (0), runs with debugging (0.5), runs without changes (1)
  - Implement **Reviewedness metric**
    - Calculate fraction of code introduced through PRs with code review
    - Handle case where no GitHub repository linked (-1)
  - Implement **Treescore metric**
    - Calculate average of total model scores of all parents in lineage graph
  - Integrate all metrics into rate endpoint response

- **Download artifacts**
  - Download full model package
  - Download sub-aspects (weights only, datasets only, etc.)
  - Handle download requests efficiently

### Model Ingest
- **HuggingFace model ingestion**
  - Request ingestion of public HuggingFace model
  - Validate package scores at least 0.5 on each non-latency metric
  - Add/repair any missing Phase 1 metrics
  - Proceed to package upload if ingestible
  - Handle ingestion failures gracefully

### Enumerate/Directory
- **Directory listing**
  - Fetch directory of all models
  - Design to handle large datasets (millions of models) without DoS
  - Implement pagination or streaming if needed
  - **Regex search functionality**
    - Search by model name (regex)
    - Search by model card content (regex)
    - Return subset of directory results

### Lineage Graph
- **Model lineage analysis**
  - Parse model structured metadata (config.json)
  - Build lineage graph from available models
  - Report lineage graph for a given model
  - Handle models with no lineage data

### Size Cost
- **Download size calculation**
  - Check size cost of using a model
  - Measure size of associated download
  - Return size information in appropriate format

### License Check
- **License compatibility assessment**
  - Given GitHub URL and Model ID
  - Assess GitHub project license compatibility with model license
  - Check for "fine-tune + inference/generation" compatibility
  - Reference ModelGo paper approach
  - Return compatibility result

### Reset Functionality
- **System reset**
  - Reset to default system state
  - Empty registry
  - Restore default user
  - Ensure clean state for autograder

### API Compliance
- **OpenAPI specification compliance**
  - Review provided OpenAPI schema
  - Ensure all endpoints match specification exactly
  - Test with autograder requirements
  - Fix any compliance issues

### Default User Setup
- **Default admin user**
  - Username: `ece30861defaultadminuser`
  - Password: `correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages`
  - Handle special characters in password correctly
  - Ensure user exists in initial/Reset state
  - If Access Control Track: ensure admin privileges

---

## 15% - Extended Features (Performance Track Selected)

### Performance Track
- [ ] **Performance measurements**
  - [ ] Ingest Tiny-LLM model from HuggingFace
  - [ ] Populate registry with 500 distinct models
  - [ ] Design experiment for 100 concurrent clients
  - [ ] Measure throughput
  - [ ] Measure mean latency
  - [ ] Measure median latency
  - [ ] Measure 99th percentile latency
  - [ ] Document experimental design
  - [ ] Provide black-box measurements
  - [ ] Provide white-box explanations
  - [ ] Make workload triggerable from health dashboard

- [ ] **Bottleneck identification and optimization**
  - [ ] Identify at least 2 performance bottlenecks
  - [ ] Document how bottlenecks were found
  - [ ] Describe optimization approach
  - [ ] Measure and document effect of optimizations

- [ ] **Component experimentation**
  - [ ] Make AWS component selection configurable
  - [ ] Test Lambda vs EC2 performance
  - [ ] Test object store vs relational database performance
  - [ ] Measure latency differences
  - [ ] Measure throughput differences
  - [ ] Document findings

---

## 10% - Engineering Practices

### Code Quality
- [x] **Code organization**
  - [x] Good file/class/variable names
  - [x] Consistent code style
  - [x] Appropriate data structures
  - [x] Use patterns to isolate changing components
  - [x] Code review all PRs

### Testing Infrastructure
- [x] **Test suite organization**
  - [x] Unit (component) level tests
  - [x] Feature level tests
  - [x] End-to-end/system level tests
  - [ ] Achieve at least 60% line coverage
  - [ ] Front-end tests with Selenium

### Development Tools
- [ ] **Dependabot**
  - [ ] Configure Dependabot
  - [ ] Review and merge dependency updates

- [x] **GitHub CoPilot Auto-Review**
  - [x] Configure automatic code review
  - [x] Review CoPilot suggestions
  - [x] Integrate into workflow

### Front-End Quality
- [x] **Web interface**
  - [x] Implement more than single query text box
  - [x] Basic styling (not plain white HTML)
  - [x] Use Bootstrap, Material-UI, or similar
  - [x] Make interface pleasant and usable

- [ ] **ADA/WCAG Compliance**
  - [ ] Ensure WCAG 2.1 Level AA compliance
  - [ ] Test with accessibility tools
  - [ ] Use Microsoft accessibility tools if helpful
  - [ ] Document compliance measures

---

## 30% - Design & Planning + Milestones

### Project Plan Document
- [x] **Tool selection and preparation**
  - [x] Programming language selection
  - [x] Toolset selection (linter, git-hooks, CI, testing framework, logging)
  - [x] Component selection
  - [x] Communication mechanism (Slack, Teams, Email)
  - [ ] Role of LLMs in engineering process

- [x] **Team contract**
  - [x] Work commitment expectations
  - [x] Code documentation standards
  - [x] Testing rules
  - [x] Style guide
  - [x] Timeliness expectations

- [x] **Team synchronous meeting times**
  - [x] Mid-week sync schedule
  - [x] End-of-week sync schedule

- [x] **Requirements**
  - [x] Refined and organized list from Sarah's description
  - [x] Disambiguate unclear requirements
  - [x] Organize by priority/scope

- [x] **Preliminary design**
  - [x] At least one activity diagram
  - [x] At least one dataflow diagram (with trust boundaries)
  - [x] Additional diagrams as needed
  - [x] Use LucidChart or draw.io

- [x] **Timeline and planned internal milestones**
  - [x] List features and sub-tasks
  - [x] Assign task owners
  - [x] Estimate time to complete
  - [x] Define success measures
  - [x] Note communication requirements between tasks

- [x] **Validation and Assessment plan**
  - [x] Plan to assess requirement satisfaction
  - [x] Define behaviors to check
  - [x] Define performance metrics
  - [x] Plan integration/validation approach

- [x] **Starting project analysis**
  - [x] Review inherited Phase 1 implementation
  - [x] Assess integration cost
  - [x] Plan changes to inherited code
  - [x] Independent trustworthiness assessment
  - [x] Check if requirements are met
  - [x] Check if test suite exists

- [x] **Lessons learned from Phase 1**
  - [x] Review Phase 1 postmortem
  - [x] Integrate lessons into Phase 2 plan
  - [x] Document changes based on lessons

### Weekly Milestone Reports
- [x] **Week 1 milestone report**
  - [x] Updated milestone list
  - [x] Task completion status
  - [x] Actual time spent per team member
  - [x] Self-contained report with original plan info
  - [x] Table for each feature with task status

- [x] **Week 2 milestone report** (same structure)
- [x] **Week 3 milestone report** (same structure)
- [x] **Week 4 milestone report** (same structure)
- [x] **Week 5 milestone report** (same structure)
- [x] **Week 6 milestone report** (same structure)
- [x] **Week 7 milestone report** (same structure)
- [x] **Week 8 milestone report** (same structure)
- [~] **Week 9 milestone report** (same structure) - *In Progress*

- [ ] **Revised plans as needed**
  - [ ] Submit revised plan if deviating from timeline
  - [ ] Update weekly reports with changes

---

## 10% - Post-mortem (End of Project - Projected 100%)

- [ ] **Project postmortem report** - *To be completed at end of project*
  - [ ] Reflect on Plan vs Execution
  - [ ] What went well? (with "Why?")
  - [ ] What went poorly? (with "Why?")
  - [ ] Where did time estimates fail? (with "Why?")
  - [ ] When and why did you deviate from Plan?
  - [ ] Use provided template

---

## Additional Requirements (Supporting All Categories)

### AWS Deployment
- [x] **Multi-component AWS setup**
  - [x] Use at least 2 AWS components
  - [x] Stay within Free Tier limits
  - [ ] Calculate expected costs in advance
  - [x] Set up usage monitoring and alerts
  - [x] Document component choices in design

- [x] **Cost management**
  - [ ] Create cost spreadsheet or use AWS tool
  - [x] Set alerts to prevent overage
  - [x] Evaluate on small resources
  - [x] Monitor usage regularly

### CI/CD Pipeline
- [x] **GitHub Actions setup**
  - [x] Automated tests on pull requests
  - [x] Automated service deployment to AWS on successful merge
  - [x] Test GitHub Actions locally to reduce debugging
  - [x] Ensure pipeline works reliably

- [x] **Code review process**
  - [x] Every PR receives code review from independent evaluator
  - [x] Document review process
  - [x] Ensure reviews are meaningful

### Observability
- [x] **System health dashboard**
  - [x] Report semi-real-time data (last hour activities)
  - [x] Make logs inspectable
  - [x] Provide `/health` API endpoint
  - [x] Provide visualization through web UI
  - [ ] Include performance workload trigger (if Performance Track)

### Security Case
- [x] **Design for security**
  - [ ] Develop system design in ThreatModeler platform
  - [x] Document threat model

- [x] **Analyze risks**
  - [x] Principled: STRIDE approach security analysis
  - [x] Dataflow diagram with trust boundaries
  - [x] Prioritized: OWASP Top 10 analysis
  - [x] Other security best practices review
  - [ ] Automated: Assess ThreatModeler recommendations
  - [x] Indicate relevant recommendations

- [x] **Mitigate risks**
  - [x] Enumerate security risks
  - [x] Rank security risks
  - [x] Modify design to address critical risks
  - [x] Modify implementation to address critical risks
  - [x] Justify excluded risks based on threat model
  - [ ] Address at least 4 vulnerabilities

- [x] **Document vulnerabilities**
  - [x] Analyze how vulnerabilities entered system
  - [x] Use "Five Whys" analysis
  - [x] Maintain strong version control record-keeping
  - [x] Traceability from code to author
  - [x] Document processes and decisions
  - [x] Explain learning from errors

### Repository Management
- [x] **Single GitHub repository**
  - [x] Include source code
  - [x] Include tests
  - [x] Make private copy of Phase 1 repo
  - [x] Organize code structure clearly

### Project Management
- [x] **Project management software**
  - [x] Set up tool (Trello, Monday, GitHub Projects, Asana, Jira, etc.)
  - [x] Use in weekly milestones
  - [x] Include screenshots in reports
  - [x] Track progress visually

### Deliverables
- [x] **Delivery 1** (Mid-project milestone)
  - [x] CI/CD working
  - [x] CR[U]D functionality demo
  - [x] Ingest functionality demo
  - [x] At least some Enumerate functionality
  - [x] Screenshots
  - [x] Progress summary relative to schedule

- [ ] **Delivery 2** (Final delivery)
  - [x] All baseline functionality
  - [ ] Extended features (selected track)
  - [ ] Substantial report describing status
  - [ ] Relation to Sarah's requirements
  - [ ] Relation to specification
  - [x] Working system deployed
  - [ ] URI provided for autograder access

### Code Re-use Justification
- [x] **Component re-use documentation**
  - [x] Justify re-used components in Project Plan
  - [x] Discuss reliability and trustworthiness assessment
  - [ ] Update assessment in Postmortem if needed
  - [x] Use module APIs, don't copy-paste code
  - [x] Extend APIs rather than copying logic

---
