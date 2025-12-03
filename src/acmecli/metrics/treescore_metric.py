import time
import re
import os
import json
import logging
from typing import Optional
from ..types import MetricValue
from .base import register

logger = logging.getLogger(__name__)


class TreescoreMetric:
    name = "Treescore"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        
        # Try to use Purdue LLM GENAI service first
        try:
            llm_score = self._get_treescore_from_purdue_llm(meta)
            if llm_score is not None:
                value = max(0.0, min(1.0, float(llm_score)))
                value = round(value, 2)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                return MetricValue(self.name, value, latency_ms)
        except Exception as e:
            logger.warning(f"Failed to get treescore from Purdue LLM GENAI: {str(e)}, falling back to parent score calculation")
        
        # Fallback to original parent score calculation
        parents = self._extract_parents(meta)

        scores = []
        for p in parents:
            score = None
            try:
                if isinstance(p, dict):
                    score = p.get("score")
                    if score is not None:
                        s = float(score)
                        if 0.0 <= s <= 1.0:
                            scores.append(round(s, 2))
                            continue
                elif isinstance(p, (int, float)):
                    s = float(p)
                    if 0.0 <= s <= 1.0:
                        scores.append(round(s, 2))
                        continue
            except (TypeError, ValueError, AttributeError):
                pass

            parent_id = None
            if isinstance(p, dict):
                parent_id = p.get("id") or p.get("name") or p.get("model_id")
            elif isinstance(p, str):
                parent_id = p

            if parent_id:
                parent_score = self._lookup_parent_score(parent_id)
                if parent_score is not None and 0.0 <= parent_score <= 1.0:
                    scores.append(parent_score)

        # Per spec: Average of the total model scores (net_score) of all parents
        # Only includes models currently uploaded to the system
        if len(scores) > 0:
            # Calculate simple average of parent net_scores
            value = sum(scores) / len(scores)
            value = max(0.0, min(1.0, value))
        else:
            if len(parents) > 0:
                # Parents found in lineage graph but no scores available (parents not uploaded to system)
                # Per spec (4): Cannot calculate average without parent scores, default to 0.5
                value = 0.5
            else:
                # No parents found - no lineage information available in config.json
                # Per spec (4): Cannot calculate average without parents, default to 0.5
                value = 0.5

        value = max(0.0, min(1.0, value))
        value = round(float(value), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)
    
    def _get_treescore_from_purdue_llm(self, meta: dict) -> Optional[float]:
        """
        Get treescore from Purdue LLM GENAI service.
        
        Args:
            meta: Model metadata dictionary
            
        Returns:
            Treescore value (0.0-1.0) or None if service unavailable
        """
        try:
            try:
                import requests
            except ImportError:
                logger.debug("requests library not available, cannot call Purdue LLM GENAI service")
                return None
            
            # Get Purdue LLM GENAI service configuration from environment variables
            purdue_llm_url = os.environ.get("PURDUE_LLM_GENAI_URL")
            purdue_llm_api_key = os.environ.get("PURDUE_LLM_GENAI_API_KEY")
            
            if not purdue_llm_url:
                logger.debug("PURDUE_LLM_GENAI_URL not set, skipping LLM service")
                return None
            
            # Prepare request payload with model metadata
            model_name = meta.get("name", meta.get("model_id", "unknown"))
            config = meta.get("config", {})
            readme_text = meta.get("readme_text", "")
            description = meta.get("description", "")
            
            # Get all potential parent models from the system for the LLM to check against
            # This helps the LLM identify which parents are actually uploaded
            try:
                from ...services.s3_service import list_models
                uploaded_models_result = list_models(limit=1000)
                uploaded_model_names = [m.get("name", "") for m in uploaded_models_result.get("models", [])]
            except Exception:
                uploaded_model_names = []
            
            # Pre-extract potential parents and their scores to help the LLM
            # The LLM will still do its own lineage extraction, but we provide this as reference
            potential_parents = self._extract_parents(meta)
            parent_scores_lookup = {}
            for p in potential_parents[:20]:  # Limit to avoid too many lookups
                parent_id = p.get("id") if isinstance(p, dict) else str(p)
                if parent_id:
                    parent_score = self._lookup_parent_score(parent_id)
                    if parent_score is not None:
                        parent_scores_lookup[parent_id] = parent_score
            
            # Build comprehensive prompt that asks LLM to extract lineage AND calculate treescore
            # Following OpenAPI spec requirements for lineage graph and treescore
            prompt = f"""You are analyzing a machine learning model to extract its lineage graph and calculate its Treescore according to the ECE 461 Fall 2025 OpenAPI specification.

TASK 1: EXTRACT LINEAGE GRAPH FROM CONFIG.JSON STRUCTURED METADATA
Per the OpenAPI spec, the lineage graph must be extracted from structured metadata (config.json).
Analyze the config.json to identify all parent models and their relationships.

Look for fields in config.json such as:
- base_model_name_or_path
- _name_or_path
- parent_model
- pretrained_model_name_or_path
- base_model
- parent
- from_pretrained
- model_name_or_path
- source_model
- original_model
- foundation_model
- backbone
- teacher_model
- student_model
- checkpoint
- checkpoint_path
- init_checkpoint
- load_from
- from_checkpoint
- resume_from
- transfer_from

Also check lineage_metadata and lineage fields if present.

For each parent model found, identify:
- The parent's artifact_id (if it's uploaded to the system) or name
- The relationship type (e.g., "base_model", "fine_tuning_dataset", "parent_model", etc.)
- The source should be "config_json" since it's extracted from structured metadata

IMPORTANT: Lineage only includes data available from models currently uploaded to the system (per spec requirement).

TASK 2: IDENTIFY UPLOADED PARENTS
For each parent model you extract from the lineage graph, check if it exists in the uploaded_models list.
Only parents that are currently uploaded to the system should be included in the lineage graph nodes.
External dependencies (not uploaded) should be noted but not included in treescore calculation.

TASK 3: CALCULATE TREESCORE (Supply-chain health score for model dependencies)
Per the OpenAPI spec, treescore is described as "Supply-chain health score for model dependencies."
It is calculated as the average of the total model scores (net_score) of all parents according to the lineage graph.

Rules:
- Use the parent_scores_lookup provided below for parents that are uploaded and have scores
- Calculate the average of all parent net_scores that are available
- Only include parents that are currently uploaded to the system
- If no parents found in the lineage graph → treescore = 0.5
- If parents found but none are uploaded to the system → treescore = 0.5
- If parents found and uploaded but no scores available → treescore = 0.5
- Otherwise → treescore = average of available parent net_scores (must be between 0.0 and 1.0)

MODEL INFORMATION:
- Model Name: {model_name}
- Config.json (structured metadata): {json.dumps(config, indent=2)[:3000]}
- Lineage metadata: {json.dumps(meta.get("lineage_metadata", {}), indent=2)[:1000]}
- Lineage field: {json.dumps(meta.get("lineage", {}), indent=2)[:1000] if meta.get("lineage") else "None"}

UPLOADED MODELS (check if parents are in this list):
{json.dumps(uploaded_model_names[:100], indent=2) if uploaded_model_names else "No models uploaded to system"}

PARENT SCORES LOOKUP (net_score for parents that are uploaded):
{json.dumps(parent_scores_lookup, indent=2) if parent_scores_lookup else "No parent scores available"}

INSTRUCTIONS:
1. Extract the lineage graph by analyzing config.json structured metadata. Identify ALL parent models and their relationships.
2. For each parent model, check if it exists in the uploaded_models list.
3. Build the lineage graph structure with:
   - nodes: array of parent models (with artifact_id if uploaded, name, source="config_json")
   - edges: array of relationships (from_node_artifact_id, to_node_artifact_id, relationship type)
4. For parents that are uploaded AND have scores in parent_scores_lookup, use those scores.
5. Calculate the average of all parent net_scores that are available.
6. Apply default rules: no parents → 0.5, parents not uploaded → 0.5, no scores → 0.5
7. Otherwise → treescore = average of available parent net_scores

Return a JSON object matching the OpenAPI spec format:
{{
  "lineage_graph": {{
    "nodes": [
      {{
        "artifact_id": "parent_artifact_id_or_name",
        "name": "parent_model_name",
        "source": "config_json"
      }}
    ],
    "edges": [
      {{
        "from_node_artifact_id": "parent_artifact_id",
        "to_node_artifact_id": "current_model_artifact_id",
        "relationship": "base_model"  // or "parent_model", "fine_tuning_dataset", etc.
      }}
    ]
  }},
  "uploaded_parents": ["parent1", ...],  // Parents that are in uploaded_models list
  "parent_scores_used": {{"parent1": 0.85, ...}},  // Parent IDs and their net_scores used in calculation
  "treescore": 0.75  // Average of parent net_scores (supply-chain health score), or 0.5 if unavailable
}}
"""
            
            payload = {
                "prompt": prompt,
                "model_name": model_name,
                "config": config,
                "readme_text": readme_text[:5000] if readme_text else "",  # Limit text length
                "description": description[:1000] if description else "",
                "lineage_metadata": meta.get("lineage_metadata", {}),
                "lineage": meta.get("lineage", {}),
                "uploaded_models": uploaded_model_names[:100],  # Include uploaded models for reference
                "parent_scores_lookup": parent_scores_lookup,  # Pre-looked up scores for reference
                "requirements": {
                    "treescore_definition": "Average of the total model scores (net_score) of all parents according to the lineage graph",
                    "lineage_source": "config.json structured metadata analysis",
                    "lineage_scope": "Only includes models currently uploaded to the system",
                    "default_value": 0.5,
                    "value_range": [0.0, 1.0],
                    "tasks": [
                        "Extract lineage graph from config.json",
                        "Identify which parents are uploaded to system",
                        "Calculate treescore as average of parent net_scores"
                    ]
                }
            }
            
            headers = {
                "Content-Type": "application/json",
            }
            
            if purdue_llm_api_key:
                headers["Authorization"] = f"Bearer {purdue_llm_api_key}"
            
            # Make request to Purdue LLM GENAI service
            response = requests.post(
                purdue_llm_url,
                json=payload,
                headers=headers,
                timeout=10,  # 10 second timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Log lineage graph if provided
                lineage_graph = result.get("lineage_graph") or result.get("lineage")
                if lineage_graph:
                    logger.info(f"Purdue LLM GENAI extracted lineage graph for {model_name}: {lineage_graph}")
                
                uploaded_parents = result.get("uploaded_parents")
                if uploaded_parents:
                    logger.info(f"Purdue LLM GENAI identified uploaded parents for {model_name}: {uploaded_parents}")
                
                # Extract treescore from response
                # Support multiple possible response formats
                treescore = (
                    result.get("treescore") or
                    result.get("tree_score") or
                    result.get("score") or
                    result.get("value")
                )
                
                if treescore is not None:
                    try:
                        score = float(treescore)
                        if 0.0 <= score <= 1.0:
                            logger.info(f"Got treescore {score} from Purdue LLM GENAI for {model_name} (lineage: {len(lineage_graph) if lineage_graph else 0} parents)")
                            return score
                        else:
                            logger.warning(f"Purdue LLM GENAI returned invalid treescore {score} (out of range 0.0-1.0)")
                    except (TypeError, ValueError):
                        logger.warning(f"Purdue LLM GENAI returned non-numeric treescore: {treescore}")
            else:
                logger.warning(f"Purdue LLM GENAI service returned status {response.status_code}: {response.text[:200]}")
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error calling Purdue LLM GENAI service: {str(e)}")
        except Exception as e:
            logger.warning(f"Unexpected error calling Purdue LLM GENAI service: {str(e)}")
        
        return None

    def _lookup_parent_score(self, parent_id: str) -> Optional[float]:
        """
        Look up the net_score (total model score) of a parent model.
        Only includes models currently uploaded to the system.
        Supports both HuggingFace model IDs and GitHub repository URLs.
        """
        try:
            from ...services.s3_service import list_models
            from ...services.rating import analyze_model_content

            # Handle GitHub URLs - convert to a searchable format
            if "github.com" in parent_id.lower():
                # Extract owner/repo from GitHub URL
                github_match = re.search(
                    r"github\.com/([\w\-\.]+)/([\w\-\.]+)", parent_id, re.IGNORECASE
                )
                if github_match:
                    owner, repo = github_match.groups()
                    # Try to find models that might be associated with this GitHub repo
                    # Search by repo name as a fallback
                    clean_parent_id = f"{owner}/{repo}"
                else:
                    return None
            else:
                # Handle HuggingFace URLs
                clean_parent_id = (
                    parent_id.replace("https://huggingface.co/", "")
                    .replace("http://huggingface.co/", "")
                    .strip()
                )

            if not clean_parent_id:
                return None

            try:
                uploaded_models = list_models(
                    name_regex=f"^{clean_parent_id.replace('/', '_')}$", limit=1000
                )
                if not uploaded_models.get("models"):
                    uploaded_models = list_models(
                        name_regex=f".*{re.escape(clean_parent_id.split('/')[-1])}.*",
                        limit=1000,
                    )

                if not uploaded_models.get("models"):
                    return None

                for model in uploaded_models.get("models", []):
                    model_name = model.get("name", "").replace("_", "/")
                    if model_name == clean_parent_id or model_name.endswith(
                        clean_parent_id.split("/")[-1]
                    ):
                        parent_result = analyze_model_content(
                            model_name, suppress_errors=True
                        )
                        if parent_result:
                            net_score = (
                                parent_result.get("net_score")
                                or parent_result.get("NetScore")
                                or parent_result.get("netScore")
                            )
                            if net_score is not None:
                                try:
                                    score = float(net_score)
                                    if 0.0 <= score <= 1.0:
                                        return round(score, 2)
                                except (TypeError, ValueError):
                                    pass
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _extract_parents(self, meta: dict) -> list:
        """
        Extract parent models from config.json structured metadata analysis.
        Priority: config.json fields > lineage_metadata > parents array.
        Lineage graph is obtained by analysis of config.json structured metadata.
        Only includes parents that are currently uploaded to the system.
        """
        parents = []
        existing_ids = set()

        config = meta.get("config") or {}
        base_model_fields = [
            "base_model_name_or_path",
            "_name_or_path",
            "parent_model",
            "pretrained_model_name_or_path",
            "base_model",
            "parent",
            "from_pretrained",
            "model_name_or_path",
            "source_model",
            "original_model",
            "foundation_model",
            "backbone",
            "teacher_model",
            "student_model",
            "checkpoint",
            "checkpoint_path",
            "init_checkpoint",
            "load_from",
            "from_checkpoint",
            "resume_from",
            "transfer_from",
        ]

        for field in base_model_fields:
            if field in config:
                base_model = config[field]
                if base_model and isinstance(base_model, str):
                    # Handle both HuggingFace and GitHub URLs
                    if "github.com" in base_model.lower():
                        # Extract owner/repo from GitHub URL
                        github_match = re.search(
                            r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                            base_model,
                            re.IGNORECASE,
                        )
                        if github_match:
                            owner, repo = github_match.groups()
                            clean_base_model = f"{owner}/{repo}"
                        else:
                            clean_base_model = base_model.strip()
                    else:
                        clean_base_model = (
                            base_model.replace("https://huggingface.co/", "")
                            .replace("http://huggingface.co/", "")
                            .strip()
                        )
                    if clean_base_model and clean_base_model not in existing_ids:
                        parents.append({"id": clean_base_model, "score": None})
                        existing_ids.add(clean_base_model)

        lineage_metadata = meta.get("lineage_metadata")
        if lineage_metadata and isinstance(lineage_metadata, dict):
            base_model = lineage_metadata.get("base_model")
            if base_model and isinstance(base_model, str):
                # Handle both HuggingFace and GitHub URLs
                if "github.com" in base_model.lower():
                    github_match = re.search(
                        r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                        base_model,
                        re.IGNORECASE,
                    )
                    if github_match:
                        owner, repo = github_match.groups()
                        clean_base_model = f"{owner}/{repo}"
                    else:
                        clean_base_model = base_model.strip()
                else:
                    clean_base_model = (
                        base_model.replace("https://huggingface.co/", "")
                        .replace("http://huggingface.co/", "")
                        .strip()
                    )
                if clean_base_model and clean_base_model not in existing_ids:
                    parents.append({"id": clean_base_model, "score": None})
                    existing_ids.add(clean_base_model)

        if meta.get("parents"):
            parents_list = (
                meta.get("parents")
                if isinstance(meta.get("parents"), list)
                else [meta.get("parents")]
            )
            for p in parents_list:
                if isinstance(p, dict):
                    p_id = p.get("id") or p.get("name") or p.get("model_id")
                    if p_id:
                        # Handle both HuggingFace and GitHub URLs
                        if "github.com" in p_id.lower():
                            github_match = re.search(
                                r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                                p_id,
                                re.IGNORECASE,
                            )
                            if github_match:
                                owner, repo = github_match.groups()
                                clean_p_id = f"{owner}/{repo}"
                            else:
                                clean_p_id = p_id.strip()
                        else:
                            clean_p_id = (
                                p_id.replace("https://huggingface.co/", "")
                                .replace("http://huggingface.co/", "")
                                .strip()
                            )
                        if clean_p_id and clean_p_id not in existing_ids:
                            parents.append({"id": clean_p_id, "score": None})
                            existing_ids.add(clean_p_id)
                elif isinstance(p, str):
                    # Handle both HuggingFace and GitHub URLs
                    if "github.com" in p.lower():
                        github_match = re.search(
                            r"github\.com/([\w\-\.]+)/([\w\-\.]+)", p, re.IGNORECASE
                        )
                        if github_match:
                            owner, repo = github_match.groups()
                            clean_p = f"{owner}/{repo}"
                        else:
                            clean_p = p.strip()
                    else:
                        clean_p = (
                            p.replace("https://huggingface.co/", "")
                            .replace("http://huggingface.co/", "")
                            .strip()
                        )
                    if clean_p and clean_p not in existing_ids:
                        parents.append({"id": clean_p, "score": None})
                        existing_ids.add(clean_p)

        lineage = meta.get("lineage")
        if lineage:
            if isinstance(lineage, dict):
                if lineage.get("parents"):
                    lineage_parents = lineage.get("parents")
                    lineage_parents_list = (
                        lineage_parents
                        if isinstance(lineage_parents, list)
                        else [lineage_parents]
                    )
                    for lp in lineage_parents_list:
                        if isinstance(lp, dict):
                            lp_id = lp.get("id") or lp.get("name") or lp.get("model_id")
                            if lp_id:
                                # Handle both HuggingFace and GitHub URLs
                                if "github.com" in lp_id.lower():
                                    github_match = re.search(
                                        r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                                        lp_id,
                                        re.IGNORECASE,
                                    )
                                    if github_match:
                                        owner, repo = github_match.groups()
                                        clean_lp_id = f"{owner}/{repo}"
                                    else:
                                        clean_lp_id = lp_id.strip()
                                else:
                                    clean_lp_id = (
                                        lp_id.replace("https://huggingface.co/", "")
                                        .replace("http://huggingface.co/", "")
                                        .strip()
                                    )
                                if clean_lp_id and clean_lp_id not in existing_ids:
                                    parents.append({"id": clean_lp_id, "score": None})
                                    existing_ids.add(clean_lp_id)
                        elif isinstance(lp, str):
                            # Handle both HuggingFace and GitHub URLs
                            if "github.com" in lp.lower():
                                github_match = re.search(
                                    r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                                    lp,
                                    re.IGNORECASE,
                                )
                                if github_match:
                                    owner, repo = github_match.groups()
                                    clean_lp = f"{owner}/{repo}"
                                else:
                                    clean_lp = lp.strip()
                            else:
                                clean_lp = (
                                    lp.replace("https://huggingface.co/", "")
                                    .replace("http://huggingface.co/", "")
                                    .strip()
                                )
                            if clean_lp and clean_lp not in existing_ids:
                                parents.append({"id": clean_lp, "score": None})
                                existing_ids.add(clean_lp)
            elif isinstance(lineage, list):
                for lp in lineage:
                    if isinstance(lp, dict):
                        lp_id = lp.get("id") or lp.get("name") or lp.get("model_id")
                        if lp_id:
                            # Handle both HuggingFace and GitHub URLs
                            if "github.com" in lp_id.lower():
                                github_match = re.search(
                                    r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                                    lp_id,
                                    re.IGNORECASE,
                                )
                                if github_match:
                                    owner, repo = github_match.groups()
                                    clean_lp_id = f"{owner}/{repo}"
                                else:
                                    clean_lp_id = lp_id.strip()
                            else:
                                clean_lp_id = (
                                    lp_id.replace("https://huggingface.co/", "")
                                    .replace("http://huggingface.co/", "")
                                    .strip()
                                )
                            if clean_lp_id and clean_lp_id not in existing_ids:
                                parents.append({"id": clean_lp_id, "score": None})
                                existing_ids.add(clean_lp_id)
                    elif isinstance(lp, str):
                        # Handle both HuggingFace and GitHub URLs
                        if "github.com" in lp.lower():
                            github_match = re.search(
                                r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                                lp,
                                re.IGNORECASE,
                            )
                            if github_match:
                                owner, repo = github_match.groups()
                                clean_lp = f"{owner}/{repo}"
                            else:
                                clean_lp = lp.strip()
                        else:
                            clean_lp = (
                                lp.replace("https://huggingface.co/", "")
                                .replace("http://huggingface.co/", "")
                                .strip()
                            )
                        if clean_lp and clean_lp not in existing_ids:
                            parents.append({"id": clean_lp, "score": None})
                            existing_ids.add(clean_lp)

        if meta.get("lineage_parents"):
            lineage_parents = meta.get("lineage_parents")
            lineage_parents_list = (
                lineage_parents
                if isinstance(lineage_parents, list)
                else [lineage_parents]
            )
            for lp in lineage_parents_list:
                if isinstance(lp, dict):
                    lp_id = lp.get("id") or lp.get("name") or lp.get("model_id")
                    if lp_id:
                        # Handle both HuggingFace and GitHub URLs
                        if "github.com" in lp_id.lower():
                            github_match = re.search(
                                r"github\.com/([\w\-\.]+)/([\w\-\.]+)",
                                lp_id,
                                re.IGNORECASE,
                            )
                            if github_match:
                                owner, repo = github_match.groups()
                                clean_lp_id = f"{owner}/{repo}"
                            else:
                                clean_lp_id = lp_id.strip()
                        else:
                            clean_lp_id = (
                                lp_id.replace("https://huggingface.co/", "")
                                .replace("http://huggingface.co/", "")
                                .strip()
                            )
                        if clean_lp_id and clean_lp_id not in existing_ids:
                            parents.append({"id": clean_lp_id, "score": None})
                            existing_ids.add(clean_lp_id)
                elif isinstance(lp, str):
                    # Handle both HuggingFace and GitHub URLs
                    if "github.com" in lp.lower():
                        github_match = re.search(
                            r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp, re.IGNORECASE
                        )
                        if github_match:
                            owner, repo = github_match.groups()
                            clean_lp = f"{owner}/{repo}"
                        else:
                            clean_lp = lp.strip()
                    else:
                        clean_lp = (
                            lp.replace("https://huggingface.co/", "")
                            .replace("http://huggingface.co/", "")
                            .strip()
                        )
                    if clean_lp and clean_lp not in existing_ids:
                        parents.append({"id": clean_lp, "score": None})
                        existing_ids.add(clean_lp)

        return parents

    def _has_lineage_indicators(self, meta: dict) -> bool:
        meta_str = str(meta).lower()
        readme = str(meta.get("readme_text", "")).lower()
        description = str(meta.get("description", "")).lower()
        all_text = meta_str + " " + readme + " " + description

        lineage_keywords = [
            "parent",
            "parents",
            "parent model",
            "parent_model",
            "parent models",
            "lineage",
            "lineage graph",
            "model lineage",
            "lineage tree",
            "lineage chain",
            "base model",
            "base_model",
            "base_model_name_or_path",
            "base models",
            "pretrained",
            "pretrained model",
            "pretrained_model",
            "pretrained models",
            "pre-trained",
            "pre-trained model",
            "pre_trained",
            "pre trained",
            "from_pretrained",
            "from pretrained",
            "from_pretrained_model",
            "from pretrained model",
            "fine-tuned",
            "finetuned",
            "fine tuned",
            "fine-tune",
            "finetune",
            "fine-tunes",
            "fine-tuning",
            "finetuning",
            "fine tuning",
            "finetuning",
            "derived from",
            "derived_from",
            "derived",
            "derives",
            "derivation",
            "based on",
            "based_on",
            "based",
            "bases",
            "baseline",
            "built on",
            "built_on",
            "built from",
            "built_from",
            "builds on",
            "extends",
            "extend",
            "extended from",
            "extended_from",
            "extension",
            "inherits",
            "inherit",
            "inherited from",
            "inherited_from",
            "inheritance",
            "forked from",
            "forked_from",
            "fork",
            "forks",
            "forked",
            "model_name_or_path",
            "model name or path",
            "model_name",
            "model path",
            "architecture",
            "architectures",
            "arch",
            "architectural",
            "source model",
            "source_model",
            "source",
            "sources",
            "source code",
            "original model",
            "original_model",
            "original",
            "originally",
            "foundation model",
            "foundation_model",
            "foundation",
            "foundations",
            "backbone",
            "backbone model",
            "backbone_model",
            "backbones",
            "teacher model",
            "teacher_model",
            "teacher",
            "teachers",
            "student model",
            "student_model",
            "student",
            "students",
            "checkpoint",
            "checkpoint_path",
            "from checkpoint",
            "checkpoints",
            "init_checkpoint",
            "initial checkpoint",
            "init checkpoint",
            "load from",
            "load_from",
            "loaded from",
            "loading from",
            "transfer from",
            "transfer_from",
            "transferred from",
            "transferring from",
            "resume from",
            "resume_from",
            "resumed from",
            "resuming from",
            "adapted from",
            "adapted_from",
            "adaptation",
            "adaptations",
            "modified from",
            "modified_from",
            "modification",
            "modifications",
            "trained on",
            "trained_on",
            "training",
            "train on",
            "trained",
            "initialized from",
            "initialized_from",
            "initialization",
            "initializations",
            "weights from",
            "weights_from",
            "weight initialization",
            "weight init",
            "transfer learning",
            "transfer_learning",
            "transfer-learning",
            "knowledge distillation",
            "knowledge_distillation",
            "distillation",
            "model zoo",
            "model_zoo",
            "modelzoo",
            "model repository",
            "huggingface",
            "hugging face",
            "hf_model",
            "hf model",
            "hf_model_id",
            "transformers",
            "transformer model",
            "transformer models",
            "transformer",
            "bert",
            "gpt",
            "t5",
            "roberta",
            "distilbert",
            "albert",
            "electra",
            "downstream",
            "downstream task",
            "downstream_task",
            "downstream tasks",
            "upstream",
            "upstream model",
            "upstream_model",
            "upstream models",
            "ancestor",
            "ancestors",
            "ancestor model",
            "ancestral",
            "predecessor",
            "predecessors",
            "predecessor model",
            "predecessors",
            "root model",
            "root_model",
            "root",
            "roots",
            "seed model",
            "seed_model",
            "seed",
            "seeds",
            "variant",
            "variants",
            "variant of",
            "variation",
            "version",
            "versions",
            "version of",
            "v1",
            "v2",
            "v3",
            "clone",
            "cloned",
            "cloned from",
            "cloning",
            "copy",
            "copied",
            "copied from",
            "copying",
            "replicate",
            "replicated",
            "replicated from",
            "replication",
            "reproduce",
            "reproduced",
            "reproduced from",
            "reproduction",
            "reimplementation",
            "re-implementation",
            "reimplement",
            "port",
            "ported",
            "ported from",
            "porting",
            "migration",
            "migrated",
            "migrated from",
            "migrating",
            "evolution",
            "evolved",
            "evolved from",
            "evolving",
            "descendant",
            "descendants",
            "descendant of",
            "offspring",
            "offsprings",
            "offspring of",
            "child",
            "children",
            "child model",
            "child models",
            "sibling",
            "siblings",
            "sibling model",
            "sibling models",
            "family",
            "families",
            "model family",
            "model families",
            "generation",
            "generations",
            "generation of",
            "iteration",
            "iterations",
            "iteration of",
            "variant",
            "variants",
            "variant of",
            "edition",
            "editions",
            "edition of",
            "release",
            "releases",
            "release of",
            "version",
            "versions",
            "version of",
        ]

        if any(keyword in all_text for keyword in lineage_keywords):
            return True

        config = meta.get("config") or {}
        config_str = str(config).lower()
        if any(keyword in config_str for keyword in lineage_keywords):
            return True

        if meta.get("lineage"):
            return True

        if meta.get("lineage_metadata"):
            return True

        if meta.get("architecture") or meta.get("architectures"):
            return True

        if meta.get("model_type") or meta.get("model_types"):
            return True

        if meta.get("base_model") or meta.get("base_models"):
            return True

        if meta.get("pretrained_model") or meta.get("pretrained_models"):
            return True

        if any(key in meta for key in ["_name_or_path", "name_or_path", "model_name"]):
            return True

        return False


register(TreescoreMetric())
