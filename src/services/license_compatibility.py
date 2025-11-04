import re
import json
from typing import Dict, Any, Optional, Tuple
from ..acmecli.github_handler import fetch_github_metadata
from ..acmecli.hf_handler import fetch_hf_metadata
from .s3_service import (
    download_model,
    extract_config_from_model,
    download_from_huggingface,
)


def normalize_license(license_str: str) -> str:
    """Normalize license string to a standard format."""
    if not license_str:
        return ""
    license_lower = license_str.lower().strip()
    # Common variations
    license_mapping = {
        "mit license": "mit",
        "mit-license": "mit",
        "bsd license": "bsd",
        "bsd-2-clause": "bsd",
        "bsd-3-clause": "bsd",
        "apache license": "apache",
        "apache-2.0": "apache-2",
        "apache-2": "apache-2",
        "apache 2.0": "apache-2",
        "gpl license": "gpl",
        "gpl-2.0": "gpl-2",
        "gpl-2": "gpl-2",
        "gpl-3.0": "gpl-3",
        "gpl-3": "gpl-3",
        "lgpl-2.1": "lgpl-2.1",
        "lgpl-2": "lgpl-2.1",
        "lgpl-3.0": "lgpl-3",
        "lgpl-3": "lgpl-3",
        "mpl": "mpl-2.0",
        "mozilla public license": "mpl-2.0",
        "cc0": "cc0-1.0",
        "unlicense": "unlicense",
        "public domain": "public-domain",
        "no license": "no-license",
        "none": "no-license",
        "noassertion": "no-license",
        "null": "no-license",
    }
    for key, value in license_mapping.items():
        if key in license_lower:
            return value
    # Extract license identifier from string
    if "mit" in license_lower:
        return "mit"
    if "bsd" in license_lower:
        return "bsd"
    if "apache" in license_lower:
        return "apache-2"
    if "gpl-3" in license_lower or "gnu general public license v3" in license_lower:
        return "gpl-3"
    if "gpl-2" in license_lower or "gnu general public license v2" in license_lower:
        return "gpl-2"
    if "lgpl-3" in license_lower:
        return "lgpl-3"
    if "lgpl-2" in license_lower or "lgpl-2.1" in license_lower:
        return "lgpl-2.1"
    if "mpl" in license_lower or "mozilla" in license_lower:
        return "mpl-2.0"
    if "cc0" in license_lower:
        return "cc0-1.0"
    if "unlicense" in license_lower:
        return "unlicense"
    return license_lower.replace(" ", "-")[:20]


def extract_model_license(model_id: str, version: str = "1.0.0") -> Optional[str]:
    """Extract license from model (S3 or HuggingFace)."""
    try:
        from .s3_service import list_models, download_model
        from botocore.exceptions import ClientError

        model_content = None
        found_version = None
        try:
            import re

            escaped_name = re.escape(model_id)
            name_pattern = f"^{escaped_name}$"
            result = list_models(name_regex=name_pattern, limit=1)
            if result.get("models"):
                found_version = result["models"][0]["version"]
                try:
                    model_content = download_model(model_id, found_version, "full")
                except:
                    pass
        except:
            pass
        if not model_content:
            for v in [version, "1.0.0", "main", "latest"]:
                try:
                    model_content = download_model(model_id, v, "full")
                    found_version = v
                    if model_content:
                        break
                except:
                    continue
        if not model_content:
            try:
                clean_model_id = model_id
                if model_id.startswith("https://huggingface.co/"):
                    clean_model_id = model_id.replace("https://huggingface.co/", "")
                elif model_id.startswith("http://huggingface.co/"):
                    clean_model_id = model_id.replace("http://huggingface.co/", "")
                hf_meta = fetch_hf_metadata(f"https://huggingface.co/{clean_model_id}")
                if hf_meta:
                    license_info = hf_meta.get("license") or hf_meta.get(
                        "cardData", {}
                    ).get("license", "")
                    if license_info:
                        return normalize_license(str(license_info))
            except:
                pass
        if model_content:
            import zipfile
            import io
            import tempfile
            import os
            import glob

            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, f"{model_id}.zip")
                with open(zip_path, "wb") as f:
                    f.write(model_content)
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                license_patterns = [
                    r'license["\']?\s*[:=]\s*["\']?([^"\']+)["\']?',
                    r'licenses?["\']?\s*[:=]\s*["\']?([^"\']+)["\']?',
                    r'"license"\s*:\s*"([^"]+)"',
                ]
                config = extract_config_from_model(model_content)
                if config:
                    config_str = json.dumps(config)
                    for pattern in license_patterns:
                        matches = re.findall(pattern, config_str, re.IGNORECASE)
                        if matches:
                            return normalize_license(matches[0])
                readme_files = glob.glob(
                    os.path.join(temp_dir, "**", "*readme*"), recursive=True
                )
                readme_files.extend(
                    glob.glob(os.path.join(temp_dir, "**", "*README*"), recursive=True)
                )
                readme_files.extend(
                    glob.glob(os.path.join(temp_dir, "README*"), recursive=False)
                )
                for readme_file in readme_files:
                    try:
                        with open(
                            readme_file, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                            for pattern in license_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    return normalize_license(matches[0])
                    except:
                        pass
                license_files = glob.glob(
                    os.path.join(temp_dir, "**", "*license*"), recursive=True
                )
                license_files.extend(
                    glob.glob(os.path.join(temp_dir, "**", "*LICENSE*"), recursive=True)
                )
                for license_file in license_files:
                    try:
                        with open(
                            license_file, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()[:500].lower()
                            if "mit" in content:
                                return "mit"
                            if "apache" in content:
                                return "apache-2"
                            if (
                                "gpl-3" in content
                                or "gnu general public license version 3" in content
                            ):
                                return "gpl-3"
                            if (
                                "gpl-2" in content
                                or "gnu general public license version 2" in content
                            ):
                                return "gpl-2"
                            if "bsd" in content:
                                return "bsd"
                            if "lgpl" in content:
                                if "2.1" in content or "version 2" in content:
                                    return "lgpl-2.1"
                                return "lgpl-3"
                    except:
                        pass
        return None
    except Exception as e:
        print(f"Error extracting model license: {e}")
        return None


def extract_github_license(github_url: str) -> Optional[str]:
    """Extract license from GitHub repository."""
    try:
        meta = fetch_github_metadata(github_url)
        if not meta:
            return None
        license_spdx = meta.get("license", "")
        if license_spdx:
            return normalize_license(license_spdx)
        readme_text = meta.get("readme_text", "")
        if readme_text:
            license_patterns = [
                r'license["\']?\s*[:=]\s*["\']?([^"\']+)["\']?',
                r'licenses?["\']?\s*[:=]\s*["\']?([^"\']+)["\']?',
                r'"license"\s*:\s*"([^"]+)"',
            ]
            for pattern in license_patterns:
                matches = re.findall(pattern, readme_text, re.IGNORECASE)
                if matches:
                    return normalize_license(matches[0])
        return None
    except Exception as e:
        print(f"Error extracting GitHub license: {e}")
        return None


def check_license_compatibility(
    model_license: Optional[str],
    github_license: Optional[str],
    use_case: str = "fine-tune+inference",
) -> Dict[str, Any]:
    """Check license compatibility for fine-tuning and inference/generation use."""
    result = {
        "compatible": False,
        "model_license": model_license or "unknown",
        "github_license": github_license or "unknown",
        "use_case": use_case,
        "reason": "",
        "restrictions": [],
    }
    if not model_license and not github_license:
        result["reason"] = "No licenses found in model or GitHub repository"
        result["restrictions"].append(
            "Unable to determine compatibility without license information"
        )
        return result
    if not model_license:
        result["reason"] = "Model license not found"
        result["restrictions"].append(
            "Model license is required for compatibility check"
        )
        return result
    if not github_license:
        result["reason"] = "GitHub repository license not found"
        result["restrictions"].append(
            "GitHub license is required for compatibility check"
        )
        return result
    model_lic = normalize_license(model_license)
    github_lic = normalize_license(github_license)
    permissive_licenses = [
        "mit",
        "bsd",
        "apache-2",
        "apache",
        "mpl-2.0",
        "mpl",
        "lgpl-2.1",
        "lgpl-3",
        "cc0-1.0",
        "cc0",
        "unlicense",
        "public-domain",
    ]
    copyleft_licenses = ["gpl-2", "gpl-3", "gpl"]
    restrictive_licenses = ["no-license", "proprietary", "unknown"]
    model_is_permissive = any(lic in model_lic for lic in permissive_licenses)
    model_is_copyleft = any(lic in model_lic for lic in copyleft_licenses)
    model_is_restrictive = any(lic in model_lic for lic in restrictive_licenses)
    github_is_permissive = any(lic in github_lic for lic in permissive_licenses)
    github_is_copyleft = any(lic in github_lic for lic in copyleft_licenses)
    github_is_restrictive = any(lic in github_lic for lic in restrictive_licenses)
    if model_lic == github_lic:
        if model_is_restrictive or github_is_restrictive:
            result["compatible"] = False
            result["reason"] = f"Both licenses are restrictive ({model_lic})"
            result["restrictions"].append(
                "No license or proprietary license prohibits use without explicit permission"
            )
        else:
            result["compatible"] = True
            result["reason"] = f"Both licenses are the same ({model_lic})"
        return result
    if model_is_restrictive or github_is_restrictive:
        result["compatible"] = False
        result["reason"] = (
            f"Restrictive license detected ({model_lic if model_is_restrictive else github_lic})"
        )
        result["restrictions"].append(
            "No license or proprietary license prohibits use without explicit permission"
        )
        return result
    if model_is_permissive and github_is_permissive:
        result["compatible"] = True
        result["reason"] = (
            f"Both licenses are permissive ({model_lic} and {github_lic})"
        )
        return result
    if model_is_copyleft and github_is_copyleft:
        if "gpl-3" in model_lic and "gpl-3" in github_lic:
            result["compatible"] = True
            result["reason"] = (
                "Both are GPL-3.0, compatible but requires derived works to be GPL-3.0"
            )
            result["restrictions"].append(
                "Derived works must be licensed under GPL-3.0"
            )
        elif "gpl-2" in model_lic and "gpl-2" in github_lic:
            result["compatible"] = True
            result["reason"] = (
                "Both are GPL-2.0, compatible but requires derived works to be GPL-2.0"
            )
            result["restrictions"].append(
                "Derived works must be licensed under GPL-2.0"
            )
        else:
            result["compatible"] = False
            result["reason"] = (
                f"Incompatible copyleft licenses ({model_lic} and {github_lic})"
            )
            result["restrictions"].append(
                "Copyleft licenses require derived works to use the same license"
            )
        return result
    if model_is_permissive and github_is_copyleft:
        result["compatible"] = False
        result["reason"] = (
            f"Permissive model license ({model_lic}) incompatible with copyleft GitHub license ({github_lic})"
        )
        result["restrictions"].append(
            f"GitHub license ({github_lic}) requires derived works to be {github_lic}"
        )
        result["restrictions"].append(
            "Fine-tuning creates derived works, which must comply with copyleft requirements"
        )
        return result
    if model_is_copyleft and github_is_permissive:
        result["compatible"] = True
        result["reason"] = (
            f"Copyleft model license ({model_lic}) allows permissive GitHub license ({github_lic})"
        )
        result["restrictions"].append(
            f"Model license ({model_lic}) requires derived works to be {model_lic}"
        )
        result["restrictions"].append(
            "Fine-tuning creates derived works, which must comply with copyleft requirements"
        )
        return result
    if "apache" in model_lic and "apache" in github_lic:
        result["compatible"] = True
        result["reason"] = "Both licenses are Apache variants, compatible"
        return result
    if "bsd" in model_lic and "bsd" in github_lic:
        result["compatible"] = True
        result["reason"] = "Both licenses are BSD variants, compatible"
        return result
    if "mit" in model_lic or "mit" in github_lic:
        if model_is_permissive or github_is_permissive:
            result["compatible"] = True
            result["reason"] = (
                "MIT license is compatible with other permissive licenses"
            )
            return result
    result["compatible"] = False
    result["reason"] = (
        f"License compatibility could not be determined ({model_lic} vs {github_lic})"
    )
    result["restrictions"].append(
        "Consult legal counsel for compatibility determination"
    )
    return result
