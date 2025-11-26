import time
import re
from typing import Optional
from ..types import MetricValue
from .base import register


class TreescoreMetric:
    name = "Treescore"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
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
                # Return 0.0 as no valid parent scores to average
                value = 0.0
            else:
                # No parents found - no lineage information available in config.json
                # Return 0.0 as there are no parents to average
                value = 0.0
        
        value = max(0.0, min(1.0, value))
        value = round(float(value), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)
    
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
                github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", parent_id, re.IGNORECASE)
                if github_match:
                    owner, repo = github_match.groups()
                    # Try to find models that might be associated with this GitHub repo
                    # Search by repo name as a fallback
                    clean_parent_id = f"{owner}/{repo}"
                else:
                    return None
            else:
                # Handle HuggingFace URLs
                clean_parent_id = parent_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
            
            if not clean_parent_id:
                return None
            
            try:
                uploaded_models = list_models(name_regex=f"^{clean_parent_id.replace('/', '_')}$", limit=1000)
                if not uploaded_models.get("models"):
                    uploaded_models = list_models(name_regex=f".*{re.escape(clean_parent_id.split('/')[-1])}.*", limit=1000)
                
                if not uploaded_models.get("models"):
                    return None
                
                for model in uploaded_models.get("models", []):
                    model_name = model.get("name", "").replace("_", "/")
                    if model_name == clean_parent_id or model_name.endswith(clean_parent_id.split("/")[-1]):
                        parent_result = analyze_model_content(model_name, suppress_errors=True)
                        if parent_result:
                            net_score = parent_result.get("net_score") or parent_result.get("NetScore") or parent_result.get("netScore")
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
                        github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", base_model, re.IGNORECASE)
                        if github_match:
                            owner, repo = github_match.groups()
                            clean_base_model = f"{owner}/{repo}"
                        else:
                            clean_base_model = base_model.strip()
                    else:
                        clean_base_model = base_model.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                    if clean_base_model and clean_base_model not in existing_ids:
                        parents.append({"id": clean_base_model, "score": None})
                        existing_ids.add(clean_base_model)
        
        lineage_metadata = meta.get("lineage_metadata")
        if lineage_metadata and isinstance(lineage_metadata, dict):
            base_model = lineage_metadata.get("base_model")
            if base_model and isinstance(base_model, str):
                # Handle both HuggingFace and GitHub URLs
                if "github.com" in base_model.lower():
                    github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", base_model, re.IGNORECASE)
                    if github_match:
                        owner, repo = github_match.groups()
                        clean_base_model = f"{owner}/{repo}"
                    else:
                        clean_base_model = base_model.strip()
                else:
                    clean_base_model = base_model.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                if clean_base_model and clean_base_model not in existing_ids:
                    parents.append({"id": clean_base_model, "score": None})
                    existing_ids.add(clean_base_model)
        
        if meta.get("parents"):
            parents_list = meta.get("parents") if isinstance(meta.get("parents"), list) else [meta.get("parents")]
            for p in parents_list:
                if isinstance(p, dict):
                    p_id = p.get("id") or p.get("name") or p.get("model_id")
                    if p_id:
                        # Handle both HuggingFace and GitHub URLs
                        if "github.com" in p_id.lower():
                            github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", p_id, re.IGNORECASE)
                            if github_match:
                                owner, repo = github_match.groups()
                                clean_p_id = f"{owner}/{repo}"
                            else:
                                clean_p_id = p_id.strip()
                        else:
                            clean_p_id = p_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                        if clean_p_id and clean_p_id not in existing_ids:
                            parents.append({"id": clean_p_id, "score": None})
                            existing_ids.add(clean_p_id)
                elif isinstance(p, str):
                    # Handle both HuggingFace and GitHub URLs
                    if "github.com" in p.lower():
                        github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", p, re.IGNORECASE)
                        if github_match:
                            owner, repo = github_match.groups()
                            clean_p = f"{owner}/{repo}"
                        else:
                            clean_p = p.strip()
                    else:
                        clean_p = p.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                    if clean_p and clean_p not in existing_ids:
                        parents.append({"id": clean_p, "score": None})
                        existing_ids.add(clean_p)
        
        lineage = meta.get("lineage")
        if lineage:
            if isinstance(lineage, dict):
                if lineage.get("parents"):
                    lineage_parents = lineage.get("parents")
                    lineage_parents_list = lineage_parents if isinstance(lineage_parents, list) else [lineage_parents]
                    for lp in lineage_parents_list:
                        if isinstance(lp, dict):
                            lp_id = lp.get("id") or lp.get("name") or lp.get("model_id")
                            if lp_id:
                                # Handle both HuggingFace and GitHub URLs
                                if "github.com" in lp_id.lower():
                                    github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp_id, re.IGNORECASE)
                                    if github_match:
                                        owner, repo = github_match.groups()
                                        clean_lp_id = f"{owner}/{repo}"
                                    else:
                                        clean_lp_id = lp_id.strip()
                                else:
                                    clean_lp_id = lp_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                                if clean_lp_id and clean_lp_id not in existing_ids:
                                    parents.append({"id": clean_lp_id, "score": None})
                                    existing_ids.add(clean_lp_id)
                        elif isinstance(lp, str):
                            # Handle both HuggingFace and GitHub URLs
                            if "github.com" in lp.lower():
                                github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp, re.IGNORECASE)
                                if github_match:
                                    owner, repo = github_match.groups()
                                    clean_lp = f"{owner}/{repo}"
                                else:
                                    clean_lp = lp.strip()
                            else:
                                clean_lp = lp.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
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
                                github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp_id, re.IGNORECASE)
                                if github_match:
                                    owner, repo = github_match.groups()
                                    clean_lp_id = f"{owner}/{repo}"
                                else:
                                    clean_lp_id = lp_id.strip()
                            else:
                                clean_lp_id = lp_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                            if clean_lp_id and clean_lp_id not in existing_ids:
                                parents.append({"id": clean_lp_id, "score": None})
                                existing_ids.add(clean_lp_id)
                    elif isinstance(lp, str):
                        # Handle both HuggingFace and GitHub URLs
                        if "github.com" in lp.lower():
                            github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp, re.IGNORECASE)
                            if github_match:
                                owner, repo = github_match.groups()
                                clean_lp = f"{owner}/{repo}"
                            else:
                                clean_lp = lp.strip()
                        else:
                            clean_lp = lp.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                        if clean_lp and clean_lp not in existing_ids:
                            parents.append({"id": clean_lp, "score": None})
                            existing_ids.add(clean_lp)
        
        if meta.get("lineage_parents"):
            lineage_parents = meta.get("lineage_parents")
            lineage_parents_list = lineage_parents if isinstance(lineage_parents, list) else [lineage_parents]
            for lp in lineage_parents_list:
                if isinstance(lp, dict):
                    lp_id = lp.get("id") or lp.get("name") or lp.get("model_id")
                    if lp_id:
                        # Handle both HuggingFace and GitHub URLs
                        if "github.com" in lp_id.lower():
                            github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp_id, re.IGNORECASE)
                            if github_match:
                                owner, repo = github_match.groups()
                                clean_lp_id = f"{owner}/{repo}"
                            else:
                                clean_lp_id = lp_id.strip()
                        else:
                            clean_lp_id = lp_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
                        if clean_lp_id and clean_lp_id not in existing_ids:
                            parents.append({"id": clean_lp_id, "score": None})
                            existing_ids.add(clean_lp_id)
                elif isinstance(lp, str):
                    # Handle both HuggingFace and GitHub URLs
                    if "github.com" in lp.lower():
                        github_match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", lp, re.IGNORECASE)
                        if github_match:
                            owner, repo = github_match.groups()
                            clean_lp = f"{owner}/{repo}"
                        else:
                            clean_lp = lp.strip()
                    else:
                        clean_lp = lp.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "").strip()
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
            "parent", "parents", "parent model", "parent_model", "parent models",
            "lineage", "lineage graph", "model lineage", "lineage tree", "lineage chain",
            "base model", "base_model", "base_model_name_or_path", "base models",
            "pretrained", "pretrained model", "pretrained_model", "pretrained models",
            "pre-trained", "pre-trained model", "pre_trained", "pre trained",
            "from_pretrained", "from pretrained", "from_pretrained_model", "from pretrained model",
            "fine-tuned", "finetuned", "fine tuned", "fine-tune", "finetune", "fine-tunes",
            "fine-tuning", "finetuning", "fine tuning", "finetuning",
            "derived from", "derived_from", "derived", "derives", "derivation",
            "based on", "based_on", "based", "bases", "baseline",
            "built on", "built_on", "built from", "built_from", "builds on",
            "extends", "extend", "extended from", "extended_from", "extension",
            "inherits", "inherit", "inherited from", "inherited_from", "inheritance",
            "forked from", "forked_from", "fork", "forks", "forked",
            "model_name_or_path", "model name or path", "model_name", "model path",
            "architecture", "architectures", "arch", "architectural",
            "source model", "source_model", "source", "sources", "source code",
            "original model", "original_model", "original", "originally",
            "foundation model", "foundation_model", "foundation", "foundations",
            "backbone", "backbone model", "backbone_model", "backbones",
            "teacher model", "teacher_model", "teacher", "teachers",
            "student model", "student_model", "student", "students",
            "checkpoint", "checkpoint_path", "from checkpoint", "checkpoints",
            "init_checkpoint", "initial checkpoint", "init checkpoint",
            "load from", "load_from", "loaded from", "loading from",
            "transfer from", "transfer_from", "transferred from", "transferring from",
            "resume from", "resume_from", "resumed from", "resuming from",
            "adapted from", "adapted_from", "adaptation", "adaptations",
            "modified from", "modified_from", "modification", "modifications",
            "trained on", "trained_on", "training", "train on", "trained",
            "initialized from", "initialized_from", "initialization", "initializations",
            "weights from", "weights_from", "weight initialization", "weight init",
            "transfer learning", "transfer_learning", "transfer-learning",
            "knowledge distillation", "knowledge_distillation", "distillation",
            "model zoo", "model_zoo", "modelzoo", "model repository",
            "huggingface", "hugging face", "hf_model", "hf model", "hf_model_id",
            "transformers", "transformer model", "transformer models", "transformer",
            "bert", "gpt", "t5", "roberta", "distilbert", "albert", "electra",
            "downstream", "downstream task", "downstream_task", "downstream tasks",
            "upstream", "upstream model", "upstream_model", "upstream models",
            "ancestor", "ancestors", "ancestor model", "ancestral",
            "predecessor", "predecessors", "predecessor model", "predecessors",
            "root model", "root_model", "root", "roots",
            "seed model", "seed_model", "seed", "seeds",
            "variant", "variants", "variant of", "variation",
            "version", "versions", "version of", "v1", "v2", "v3",
            "clone", "cloned", "cloned from", "cloning",
            "copy", "copied", "copied from", "copying",
            "replicate", "replicated", "replicated from", "replication",
            "reproduce", "reproduced", "reproduced from", "reproduction",
            "reimplementation", "re-implementation", "reimplement",
            "port", "ported", "ported from", "porting",
            "migration", "migrated", "migrated from", "migrating",
            "evolution", "evolved", "evolved from", "evolving",
            "descendant", "descendants", "descendant of",
            "offspring", "offsprings", "offspring of",
            "child", "children", "child model", "child models",
            "sibling", "siblings", "sibling model", "sibling models",
            "family", "families", "model family", "model families",
            "generation", "generations", "generation of",
            "iteration", "iterations", "iteration of",
            "variant", "variants", "variant of",
            "edition", "editions", "edition of",
            "release", "releases", "release of",
            "version", "versions", "version of",
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
