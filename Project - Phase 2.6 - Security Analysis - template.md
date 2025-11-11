# **Project Phase 2 – Security Analysis**

*As a Boilermaker pursuing academic excellence, we pledge to be honest and true in all that we do. Accountable together – We are Purdue.*

*(On group submissions, have each team member type their name).*

Type or sign your names: Ali Afrose, Ethan Silverthorne, Taiwo Olawore, and Fahd Laniyan\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Write today’s date: 11-9-2025\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

# **Assignment**

This document provides a template for your system's security analysis. You are welcome to add content beyond what is listed; the template is designed to help ensure you cover all crucial components.

The terms used in this section are defined [here](https://docs.microsoft.com/en-us/archive/msdn-magazine/2006/november/uncover-security-design-flaws-using-the-stride-approach).

##### Security requirements.

Here, list the *security* requirements of your system, aligned with the six security properties defined by the STRIDE article. These requirements may be unique to your system, depending on which features you implemented. It is possible that you will not have a requirement associated with every security property.

| Confidentiality Observers along the network cannot directly observe client-server interactions.  Integrity JWT token must be signed using HS256 algorithm with an environment variable and validated on every request to prevent malicious activities such as token forgery, tampering, etc. Our codebase prevents replay attacks by decrementing the remaining uses on each token consumption with the help of dynamoDB (tracks token usage counters and expiration times).  DynamoDB conditional writes are used to prevent race conditions during concurrent updates Availability … Authentication Only authenticated users can retrieve packages. Most of the endpoints mentioned in the yaml file must require valid JWT token in the authentication header Authorization … Nonrepudiation …  |
| :---- |

##### System model via DFDs

Present one or more data-flow diagrams of your deployed system. You can use some drawing tools such as [https://app.diagrams.net/](https://app.diagrams.net/). A whiteboard picture is also fine, but use the correct symbols please – process, data sink, etc.

- You may provide multiple DFDs to capture different aspects of the system (e.g. one per feature or feature group).  
- You may wish to indicate multiple trust boundaries, e.g. for different classes of users or for external components.  
- Each diagram should indicate **at least** the following entities: data flow; data store; process; trust boundary. You may include interactors and multi-process if needed.

|   |
| :---- |

##### Threats

For each trust boundary indicated in the DFDs, describe the nature of the untrusted party involved (examples: “outsider threat \[e.g. external hacker\]” or “insider threat \[e.g. ACME employee with valid credentials\]” or “infrastructure provider threat \[AWS\]”), why the location of the trust boundary is appropriate, and a potential attack that could occur were this trust boundary not secured.

| Trust boundary \#: 1 Untrusted party: … Rationale for this boundary: (1-3 sentences)… Potential attack across this boundary: (1-3 sentences)… Trust boundary \#: 2 Untrusted party: … Rationale for this boundary: … Potential attack across this boundary: … … |
| :---- |

##### AI-Assisted Threat Modeling and Feedback

After completing your DFD(s), consult a Large Language Model (LLM) for a preliminary security analysis. The goal is to generate a broad set of security considerations and best practices for your group to critically evaluate.

1. **Request Specific Analysis:** Ask the LLM for a component-by-component security analysis. Key requests should include:  
   * Specific advice on securely configuring the services you are using (e.g., “What are the security best practices for configuring an AWS S3 bucket that stores user files?” or “How should we securely configure our AWS RDS instance?”).  
   * General feedback on potential design weaknesses in your data flows or trust boundaries.  
2. **Sub-Group Analysis:** Divide your team into two sub-groups. Each sub-group will independently query an LLM using the group's DFD. After gathering feedback:  
   * As a full group, consolidate and compare the results.  
   * Discuss similarities and differences in the LLM's advice.  
   * Critically evaluate which recommendations are most relevant and actionable for your project.  
3. **Summarize Findings:** In the area below, summarize this process. You **must** detail the specific LLM analysis or recommendations that you found most helpful or insightful. Discuss how this feedback informed your team's final security analysis and mitigation strategies.

|  |
| :---- |

##### 

##### Analysis of Threats and Mitigations

Fill out the following table for each [STRIDE property](https://docs.microsoft.com/en-us/archive/msdn-magazine/2006/november/uncover-security-design-flaws-using-the-stride-approach) (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege). For each STRIDE category, you must list specific potential threats, brainstorm multiple mitigation strategies, and then label each threat as either “Should Fix” or “Won't Fix”. You must justify any “Won't Fix” decisions by explaining why the risk is low-priority, implausible, or out of scope. For every “Should Fix” threat, you must identify a single, specific mitigation strategy you plan to implement.

**Note:** It is acceptable if you are unable to implement *all* mitigation strategies you planned by the deadline for *this* document. However, for the final project submission, you will be required to have implemented *all* mitigation strategies for every threat you labeled as “Should Fix” in this document.

| STRIDE property: Spoofing Relevant system security properties: … Analysis of components: Diagram+Component (e.g. “Diagram 1, component 3 – Database”): XXX Risk 1: Possible Mitigations: (1-2 sentences) … How do these address the risk: (1-2 sentences) … Suggestions for additional mitigations, if needed: Decision: (“Should Fix” or “Won’t Fix”) Justification and Plan (If “Should Fix”, identify the mitigation strategy you are going to implement; if “Won’t fix”, justify why) Risk 2: … Diagram+Component: YYY Risk 1: … |
| :---- |

| STRIDE property: Tampering …  |
| :---- |

| STRIDE property: Repudiation …  |
| :---- |

| STRIDE property: Information disclosure *(e.g. looking at confidentiality property \#1, one threat is that there is an observer on the client-server network path. A mitigation is to use HTTPS for encryption. HTTPS would not protect against e.g. keyloggers on the client’s machine, but that threat would be out of scope for your system – a relevant additional mitigation might be “ACME Corp. employees should have anti-virus installed to check for keyloggers”).* … |
| :---- |

| STRIDE property: Denial of service *NB: Remember the ReDoS demonstration in class?* … |
| :---- |

| STRIDE property: Elevation of privilege *NB: If you implemented the “JSProgram” feature, tread carefully.* … |
| :---- |

##### Risks resulting from component interactions

The STRIDE framework (per Microsoft) advises you to divide and conquer – analyze each component in turn. You have now done that.

Are there any instances in your system where a risk emerges from the interaction of multiple components? If you can, identify one case and describe it with reference to your DFDs. Did you find it during your STRIDE process or only just now? (1 paragraph)

|  |
| :---- |

Are there instances in your system where the requirements of one component (e.g., security, correctness, performance) may negatively affect the security requirements of another component or the system? If you can, identify one case and describe it. (1 paragraph)

|  |
| :---- |

##### Root cause analysis

Presumably (1) you did not intentionally create any security vulnerabilities, yet (2) found some through this process. Choose two interesting vulnerabilities. Describe why they happened.

| Example 1: Succinctly describe the vulnerability and mitigation (1-2 sentences) How did it get through your design and review process? (2-3 sentences) Example 2: Succinctly describe the vulnerability and mitigation How did it get through your design and review process?  |
| :---- |

