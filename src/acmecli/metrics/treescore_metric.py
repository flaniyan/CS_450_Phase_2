from .base import register


class TreescoreMetric:
    name = "Treescore"

    def score(self, meta: dict) -> float:
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
            return max(0.5, avg)
        
        if parents and len(parents) > 0:
            return 0.5
        
        if self._has_lineage_indicators(meta):
            return 0.5
        
        return 0.5

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
            "parent", "parents", "parent model", "parent_model",
            "lineage", "lineage graph", "model lineage",
            "base model", "base_model", "base_model_name_or_path",
            "pretrained", "pretrained model", "pretrained_model",
            "from_pretrained", "from pretrained", "from_pretrained_model",
            "fine-tuned", "finetuned", "fine tuned", "fine-tune", "finetune",
            "fine-tuning", "finetuning", "fine tuning",
            "derived from", "derived_from", "derived",
            "based on", "based_on", "based",
            "built on", "built_on", "built from", "built_from",
            "extends", "extend", "extended from", "extended_from",
            "inherits", "inherit", "inherited from", "inherited_from",
            "forked from", "forked_from", "fork",
            "model_name_or_path", "model name or path",
            "architecture", "architectures", "arch",
            "source model", "source_model", "source",
            "original model", "original_model", "original",
            "foundation model", "foundation_model", "foundation",
            "backbone", "backbone model", "backbone_model",
            "teacher model", "teacher_model", "teacher",
            "student model", "student_model", "student",
            "checkpoint", "checkpoint_path", "from checkpoint",
            "init_checkpoint", "initial checkpoint",
            "load from", "load_from", "loaded from",
            "transfer from", "transfer_from", "transferred from",
            "resume from", "resume_from", "resumed from",
            "adapted from", "adapted_from", "adaptation",
            "modified from", "modified_from", "modification",
            "trained on", "trained_on", "training",
            "initialized from", "initialized_from", "initialization",
            "weights from", "weights_from", "weight initialization",
            "pre-trained", "pre-trained model", "pre_trained",
            "transfer learning", "transfer_learning",
            "knowledge distillation", "knowledge_distillation",
            "model zoo", "model_zoo", "modelzoo",
            "huggingface", "hugging face", "hf_model",
            "transformers", "transformer model",
            "bert", "gpt", "t5", "roberta", "distilbert",
            "downstream", "downstream task", "downstream_task",
            "upstream", "upstream model", "upstream_model",
            "ancestor", "ancestors", "ancestor model",
            "predecessor", "predecessors", "predecessor model",
            "root model", "root_model",
            "seed model", "seed_model",
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
        
        return False


register(TreescoreMetric())
