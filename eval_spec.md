# Phase 2 Project Todo List

**Current Status**: 82.3% of autograder portion (35% of total grade) = ~28.8% overall
**Latest Test Results**: 261 / 317 points (November 26, 2025)

---

## 📋 Overall Priority Todo List (Ranked by Importance)

### 🔴 Critical Priority (Must Complete for Passing Grade)
1. **Autograder Baseline Features (35% of grade)** - Currently at 82.3% (261/317)
   - **Working Well (100% pass rate)**:
     - Setup and Reset Test Group: 6/6 ✅
     - Artifact Read Test Group: 61/61 ✅
     - Artifact Download URL Test Group: 5/5 ✅
     - Artifact Cost Test Group: 14/14 ✅
   
   - **Needs Fixing**:
     - **Model Query Tests**: Single Model Query Test failed, All Model Query Test failed (dependency issue)
       - Issue: Model queries not returning expected results after ingestion
       - Impact: Blocks All Artifacts Query Test and Regex Tests (0/6)
     - **Rate Models Concurrently**: 1/14 passing (13 failures)
       - Issue: Rating endpoint failing for most models during concurrent requests
       - Impact: Critical for rating functionality
     - **Model Rating Attributes**: 135/156 (86.5% partial success)
       - Issue: Some rating attributes missing or incorrect
       - Most models have 11/12 attributes correct, some have 9/12 or 7/12
     - **Artifact License Check**: 1/6 passing (5 failures)
       - Issue: License compatibility checks failing
     - **Artifact Lineage**: 1/4 passing (3 failures)
       - Issue: Lineage graph extraction failing for specific models
     - **Artifact Delete**: 5/10 passing (5 failures)
       - Issue: Delete operations not working correctly for models
       - After delete, artifacts still appear in queries
   
   - **Action Items**:
     - Fix model query endpoint to properly return ingested models
     - Investigate rating endpoint failures during concurrent requests
     - Verify all rating attributes are included in response
     - Fix license check endpoint implementation
     - Fix lineage extraction for models that should have lineage data
     - Fix delete endpoint to properly remove artifacts and update queries
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

### Current Estimated Grade: **~74.3%**

**Breakdown:**
- **Design & Planning + Milestones (30%)**: ~95% complete = **28.5%**
  - Project plan: ~98% (missing only Role of LLMs)
  - Weekly milestones: ~89% (Week 9 in progress)
  
- **Working Delivery (60%)**:
  - **Autograder Baseline (35%)**: 82.3% complete (261/317) = **28.8%**
  - **Extended Features (15%)**: ~0% complete = **0%**
  - **Engineering Practices (10%)**: ~70% complete = **7%**
  - **Subtotal**: **35.8%**

- **Post-mortem (10%)**: Projected 100% = **10%**

**Total Estimated Grade: ~74.3%**

**Latest Test Results (November 26, 2025):**
- **Total Score**: 261 / 317 (82.3%)
- **Test Groups**:
  - Setup and Reset: 6/6 (100%) ✅
  - Upload Artifacts: 32/35 (91.4%) ⚠️
  - Regex Tests: 0/6 (0%) ❌ (blocked by dependency)
  - Artifact Read: 61/61 (100%) ✅
  - Artifact Download URL: 5/5 (100%) ✅
  - Rate models concurrently: 1/14 (7.1%) ❌
  - Validate Model Rating Attributes: 135/156 (86.5%) ⚠️
  - Artifact Cost: 14/14 (100%) ✅
  - Artifact License Check: 1/6 (16.7%) ❌
  - Artifact Lineage: 1/4 (25%) ❌
  - Artifact Delete: 5/10 (50%) ⚠️

**Note**: This estimate assumes:
- Autograder score at 82.3% (improved from 52%)
- Performance track not yet started
- Engineering practices mostly complete
- Post-mortem will be completed at 100%

**To Improve Grade:**
- Fix model query issues (could add 3-5% if all query tests pass)
  - Priority: HIGH - Blocks multiple test groups
- Fix rating endpoint for concurrent requests (could add 5-7%)
  - Priority: HIGH - Critical functionality failing
- Fix license check and lineage endpoints (could add 2-3%)
  - Priority: MEDIUM - Specific functionality issues
- Fix delete endpoint (could add 1-2%)
  - Priority: MEDIUM - Delete works but verification fails
- Complete Performance Track (adds 15% if done well)
  - Priority: HIGH - Significant grade impact
- Complete remaining engineering practices (adds 2-3%)
  - Priority: MEDIUM - Quality improvements

**Potential Final Grade Range: 85-95%** (if all critical issues fixed and Performance Track completed)

**Critical Path to 90%+ Grade:**
1. Fix model query endpoint (unblocks 9+ test points)
2. Fix concurrent rating requests (unblocks 13+ test points)
3. Fix license check endpoint (unblocks 5+ test points)
4. Fix lineage extraction (unblocks 3+ test points)
5. Fix delete verification (unblocks 5+ test points)
6. Complete Performance Track (adds 15% to grade)

---

## 35% - Autograder Baseline Features (Currently at 82.3% - 261/317 points)

**⚠️ IMPORTANT NOTE**: Regardless of implementation seeming correct, the autograder score is the true determination of completion for all items below.

### Test Results Summary (November 26, 2025)

**✅ Fully Working (100% pass rate):**
- Setup and Reset functionality (6/6 tests)
- Artifact Read operations (61/61 tests)
- Artifact Download URL generation (5/5 tests)
- Artifact Cost calculation (14/14 tests)

**⚠️ Partially Working:**
- Upload Artifacts (32/35 tests - 91.4%)
  - Model ingestion working
  - Model query tests failing (blocking other tests)
- Model Rating Attributes (135/156 - 86.5%)
  - Most models have 11/12 attributes correct
  - Some missing attributes need investigation
- Artifact Delete (5/10 tests - 50%)
  - Delete operations work but verification fails

**❌ Needs Immediate Fix:**
- Model Query Tests (0/3 passing)
  - Single Model Query Test failed
  - All Model Query Test failed (dependency)
  - Blocks: All Artifacts Query Test, Regex Tests (0/6)
  - **Root Cause**: Models are being ingested successfully but queries are not finding them
  - **Action**: Investigate `/artifacts` POST endpoint and model query logic
- Rate Models Concurrently (1/14 passing - 7.1%)
  - 13 out of 14 rating requests failing during concurrent load
  - **Root Cause**: Rating endpoint may have race conditions or timeout issues
  - **Action**: Review concurrent request handling in rating endpoint
- Artifact License Check (1/6 passing - 16.7%)
  - 5 out of 6 license checks failing
  - **Root Cause**: License compatibility logic may be incorrect
  - **Action**: Review license check endpoint implementation
- Artifact Lineage (1/4 passing - 25%)
  - 3 out of 4 lineage extractions failing
  - **Root Cause**: Lineage extraction from config.json may be failing for some models
  - **Action**: Review lineage extraction logic and error handling

### Detailed Test Failure Analysis

#### 1. Model Query Tests (Critical - Blocks 9+ test points)
**Failed Tests:**
- Single Model Query Test
- All Model Query Test (dependency failure)
- All Artifacts Query Test (dependency failure)
- Regex Tests (0/6 - all blocked by dependency)

**Symptoms:**
- Models are successfully ingested (all 13 model ingestions passed)
- Queries immediately after ingestion fail to find the models
- This suggests a timing issue or query endpoint not properly searching ingested models

**Investigation Needed:**
- Check if `/artifacts` POST endpoint properly searches S3 for models
- Verify model metadata is being stored correctly after ingestion
- Check if there's a delay between ingestion and query availability
- Review query logic in `/artifacts` endpoint

#### 2. Rate Models Concurrently (Critical - 13/14 failures)
**Failed Tests:**
- 13 out of 14 rating requests failing during concurrent execution
- Only 1 model successfully rated under concurrent load

**Symptoms:**
- Rating works for individual requests (based on partial success in attribute validation)
- Fails when multiple requests are made concurrently
- Suggests race conditions, timeouts, or resource contention

**Investigation Needed:**
- Review rating endpoint for thread-safety issues
- Check for database/S3 locking problems
- Verify timeout settings are appropriate
- Review async/concurrent request handling

#### 3. Model Rating Attributes (Partial - 86.5% success)
**Status:**
- Most models: 11/12 attributes correct
- Some models: 9/12 or 7/12 attributes correct
- Missing attributes need identification

**Investigation Needed:**
- Compare successful vs failed attribute sets
- Verify all required fields from ModelRating schema are present
- Check for optional vs required field handling

#### 4. Artifact License Check (Critical - 5/6 failures)
**Failed Tests:**
- 5 out of 6 license compatibility checks failing
- Only 1 check passing

**Investigation Needed:**
- Review license compatibility logic
- Verify GitHub API integration for license fetching
- Check license parsing and comparison logic
- Review error handling for missing licenses

#### 5. Artifact Lineage (Critical - 3/4 failures)
**Failed Tests:**
- Microsoft ResNet-50 Artifact Lineage Test failed
- Crangana Trained Gender Artifact Lineage Test failed
- ONNX Community Trained Gender Artifact Lineage Test failed

**Investigation Needed:**
- Verify config.json extraction for these specific models
- Check if models have valid lineage data in config.json
- Review lineage graph construction logic
- Verify base_model field extraction

#### 6. Artifact Delete (Partial - 5/10 failures)
**Status:**
- Delete operations execute successfully
- Verification after delete fails (artifacts still appear in queries)
- Models: Delete fails completely
- Datasets: Delete works but verification fails
- Code: Delete works but verification fails

**Investigation Needed:**
- Verify delete actually removes artifacts from storage
- Check if queries are properly excluding deleted artifacts
- Review soft-delete vs hard-delete implementation
- Verify database/S3 cleanup after delete

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
