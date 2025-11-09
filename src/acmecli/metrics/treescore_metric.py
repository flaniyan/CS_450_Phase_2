import time
from ..types import MetricValue
from .base import register


class TreescoreMetric:
    name = "Treescore"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        parents = self._extract_parents(meta)
        
        scores = []
        for p in parents:
            try:
                s = float(p.get("score"))
            except (TypeError, ValueError, AttributeError):
                continue
            if 0.0 <= s <= 1.0:
                scores.append(s)

        if len(scores) > 0:
            avg = sum(scores) / len(scores)
            avg = max(0.0, min(1.0, avg))
            value = avg
        else:
            value = 0.0
        
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)

    def _extract_parents(self, meta: dict) -> list:
        parents = []
        
        if meta.get("parents"):
            parents.extend(meta.get("parents") if isinstance(meta.get("parents"), list) else [meta.get("parents")])
        
        lineage = meta.get("lineage")
        if lineage:
            if isinstance(lineage, dict):
                if lineage.get("parents"):
                    lineage_parents = lineage.get("parents")
                    if isinstance(lineage_parents, list):
                        parents.extend(lineage_parents)
                    else:
                        parents.append(lineage_parents)
            elif isinstance(lineage, list):
                parents.extend(lineage)
        
        if meta.get("lineage_parents"):
            lineage_parents = meta.get("lineage_parents")
            if isinstance(lineage_parents, list):
                parents.extend(lineage_parents)
            else:
                parents.append(lineage_parents)
        
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
                    if not any(p.get("id") == base_model for p in parents if isinstance(p, dict)):
                        parents.append({"id": base_model, "score": None})
        
        lineage_metadata = meta.get("lineage_metadata")
        if lineage_metadata and isinstance(lineage_metadata, dict):
            base_model = lineage_metadata.get("base_model")
            if base_model and isinstance(base_model, str):
                if not any(p.get("id") == base_model for p in parents if isinstance(p, dict)):
                    parents.append({"id": base_model, "score": None})
        
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
