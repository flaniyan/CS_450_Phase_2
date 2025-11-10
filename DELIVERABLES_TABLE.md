# Initial Deliverables and Current Progress

## Deliverables Status Table

| Requirement | Description | Initially part of plan? (yes/no) | Is baseline? (yes/no) | Status (complete/in progress/not started) | Planned, do you still plan to deliver? (yes/no) |
|------------|-------------|----------------------------------|----------------------|-------------------------------------------|------------------------------------------------|
| Comprehensive Model Registry | CRUD operations for model registry with ZIP file upload/download capabilities | yes | yes | in progress | yes |
| New Metrics (Reproducibility, Reviewedness, Treescore) | Reproducibility, Reviewedness, and Treescore metrics implementation | yes | yes | complete | yes |
| Ingest Public HuggingFace Models (≥0.5 threshold) | Ingest public HuggingFace models scoring ≥0.5 on non-latency metrics | yes | yes | in progress | yes |
| Search and Enumerate with DoS Protection | Search and enumerate artifacts with DoS protection | yes | yes | in progress | yes |
| Version Searching | Version searching: exact version ("1.2.3"), bounded range ("1.2.3-2.1.0"), tilde ranges ("~1.2.0"), carat ranges ("^1.2.0"), git tag parsing ("vX" or "X" notation) | yes | yes | complete | yes |
| Sub-aspects Support | Support for sub-aspects such as just weights, just datasets, etc. | yes | yes | in progress | yes |
| Additional Features | Lineage graphs, size costs, license checks, and system reset | yes | yes | in progress | yes |
| CI/CD Pipeline | Code review for every PR; automated tests on PRs using GitHub Actions CI/CD pipeline; automated deployment to AWS on successful merge | yes | yes | complete | yes |
| User-Friendly Web Interface | Web interface for people outside of our group to access our work | yes | no | complete | yes |
| REST-ful API | REST-ful API complying with provided OpenAPI schema | yes | yes | in progress | yes |
| Health Dashboard UI | Health dashboard UI with real-time data visualization | yes | no | in progress | yes |
| Front-end Automated Tests | Front-end user interface accompanied by automated tests | yes | no | in progress | yes |
| WCAG 2.1 AA Compliance | WCAG 2.1 AA compliance for web interface | yes | no | in progress | yes |
| 60% Line Coverage | 60% line coverage across unit, end-to-end, and integration test cases | yes | yes | in progress | yes |
| Deploy on AWS (2+ Components) | Deploy on AWS using at least two components | yes | yes | complete | yes |
| STRIDE Security Analysis | STRIDE security analysis with dataflow diagrams | yes | yes | complete | yes |
| OWASP Top 10 Analysis | OWASP Top 10 analysis and mitigation | yes | yes | in progress | yes |
| ThreatModeler Platform Security Design | ThreatModeler platform security design | yes | yes | in progress | yes |
| 4+ Vulnerability Mitigations | At least 4 vulnerability mitigations with root cause analysis | yes | yes | complete | yes |
| Version Control Traceability | Version control traceability | yes | yes | complete | yes |
| Performance Track (Load Testing & Bottleneck Analysis) | Load testing and bottleneck analysis (Sarah's extended requirement) | yes | no | in progress | yes |

## Summary

**Total Requirements**: 21 (matching initial project plan)  
**Complete**: 6 (29%)  
**In Progress**: 14 (67%)  
**Not Started**: 1 (5%)  

**Baseline Requirements**: 15  
**Non-Baseline Requirements**: 6  

**Still Planned to Deliver**: All 21 requirements (100%)

## Current Status Notes

### Autograder Results: 25/84 tests passing (30%)

**Key Achievements:**
- ✅ New metrics (Reproducibility, Reviewedness, Treescore) fully implemented
- ✅ All version search formats (exact, bounded, tilde, carat, git tags) working
- ✅ STRIDE security analysis complete with dataflow diagrams
- ✅ AWS infrastructure deployed with 6+ components (exceeds 2-component requirement)
- ✅ CI/CD pipeline with automated testing and deployment
- ✅ Complete web interface with multiple pages
- ✅ 4+ vulnerability mitigations documented with root cause analysis

**Areas Needing Attention:**
- ⚠️ OWASP Top 10 analysis (in progress)
- ⚠️ ThreatModeler documentation (in progress)
- ⚠️ Load testing and bottleneck analysis (in progress)
- ⚠️ WCAG 2.1 AA compliance (in progress)
- ⚠️ 60% line coverage goal (in progress)

**Budget Status**: Under budget and on schedule
