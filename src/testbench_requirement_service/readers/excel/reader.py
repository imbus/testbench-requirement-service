from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sanic.exceptions import NotFound

from testbench_requirement_service.log import logger
from testbench_requirement_service.models.requirement import (
    BaselineObject,
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributeResponse,
)
from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader
from testbench_requirement_service.readers.excel.config import (
    ExcelRequirementReaderConfig,
    ExcelRequirementReaderProjectConfig,
    UserDefinedAttributeConfig,
)
from testbench_requirement_service.readers.excel.utils import (
    build_extendedrequirementobject_from_row_data,
    build_placeholder_extendedrequirementobject,
    build_requirement_tree_from_dataframe,
    build_requirementversionobject_from_row_data,
    get_config_for_user_defined_attribute,
    is_placeholder_node,
    read_data_frame_from_file_path,
)
from testbench_requirement_service.readers.utils import load_reader_config_from_path


@dataclass
class DataFrameBufferEntry:
    data_frame: pd.DataFrame
    last_accessed_at: float
    file_mtime: float
    size_bytes: int


class ExcelRequirementReader(AbstractRequirementReader):
    CONFIG_CLASS = ExcelRequirementReaderConfig

    def __init__(self, config: ExcelRequirementReaderConfig):
        self.config = config
        self._buffer_catalog: dict[str, DataFrameBufferEntry] = {}
        self._buffer_size_bytes = 0
        self._buffer_lock = threading.RLock()
        self._start_buffer_cleanup_thread()

    def project_exists(self, project: str) -> bool:
        return self._get_project_path(project).exists()

    def baseline_exists(self, project: str, baseline: str) -> bool:
        try:
            return self._get_baseline_path(project, baseline).exists()
        except Exception as e:
            logger.debug("Could not resolve baseline path for '%s/%s': %s", project, baseline, e)
            return False

    def get_projects(self) -> list[str]:
        if not self.config.requirementsDataPath.exists():
            return []
        return [p.name for p in self.config.requirementsDataPath.iterdir() if p.is_dir()]

    def get_baselines(self, project: str) -> list[BaselineObject]:
        baselines = []
        for file in self._iter_baseline_files(project):
            stat_result = file.stat()
            baseline = BaselineObject(
                name=file.stem,
                date=datetime.fromtimestamp(stat_result.st_mtime, timezone.utc),
                type="UNLOCKED",
            )
            baselines.append(baseline)
        return sorted(baselines, key=lambda b: b.date, reverse=True)

    def _iter_baseline_files(self, project: str):
        allowed_suffixes = self._get_allowed_suffixes_for_project(project)
        files = [
            file
            for file in self._get_files_in_project_path(project)
            if file.suffix in allowed_suffixes and not self._is_temp_baseline_file(file)
        ]
        files.sort(key=lambda file: file.stat().st_mtime, reverse=True)
        yield from files

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = self._get_dataframe(baseline_path, config)
        requirement_tree = build_requirement_tree_from_dataframe(df, config)

        stat_result = baseline_path.stat()
        return BaselineObjectNode(
            name=baseline,
            date=datetime.fromtimestamp(stat_result.st_mtime, timezone.utc),
            type="CURRENT",
            children=requirement_tree,
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        udf_definitions: list[UserDefinedAttribute] = []
        for udf_config in self.config.udf_configs:
            udf_definitions.append(
                UserDefinedAttribute(name=udf_config.name, valueType=udf_config.type)
            )
        return udf_definitions

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        if not requirement_keys:
            return []

        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = self._get_dataframe(baseline_path, config)

        keys_df = pd.DataFrame([key.model_dump() for key in requirement_keys])
        filtered_df = pd.merge(df, keys_df, on=["id", "version"], how="inner")

        udf_configs: dict[str, UserDefinedAttributeConfig] = {}
        for name in attribute_names:
            udf_config = get_config_for_user_defined_attribute(name, config)
            if udf_config is None:
                continue
            udf_configs[name] = udf_config

        udfs_list: list[UserDefinedAttributeResponse] = []

        for row in filtered_df.to_dict(orient="records"):
            key = RequirementKey(id=row["id"], version=row["version"])
            user_defined_attributes: list[UserDefinedAttribute] = []

            for name, udf_config in udf_configs.items():
                if name not in row:
                    continue

                udf: dict[str, Any] = {"name": name, "valueType": udf_config.type}

                udf_value: str = row[name]

                if udf["valueType"] == "STRING":
                    udf["stringValue"] = udf_value
                if udf["valueType"] == "ARRAY":
                    sep = config.arrayValueSeparator
                    udf["stringValues"] = udf_value.split(sep) if udf_value else []
                if udf["valueType"] == "BOOLEAN":
                    udf["booleanValue"] = udf_value == udf_config.trueValue

                user_defined_attributes.append(UserDefinedAttribute(**udf))

            udfs_list.append(
                UserDefinedAttributeResponse(key=key, userDefinedAttributes=user_defined_attributes)
            )

        return udfs_list

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        if is_placeholder_node(key):
            return build_placeholder_extendedrequirementobject(key, baseline)

        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)
        extended_requirement = self._find_extended_requirement_in_file(
            baseline_path, config, baseline, key
        )
        if extended_requirement is not None:
            return extended_requirement

        for baseline_file in self._iter_other_baseline_files(project, baseline_path):
            extended_requirement = self._find_extended_requirement_in_file(
                baseline_file, config, baseline, key
            )
            if extended_requirement is not None:
                return extended_requirement

        raise NotFound("Requirement not found")

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        if is_placeholder_node(key):
            return []

        config = self._get_config_for_project(project)
        requirement_versions: list[RequirementVersionObject] = []
        seen_versions: set[str] = set()

        for baseline_file in self._iter_baseline_files(project):
            df = self._get_dataframe(baseline_file, config)
            filtered_df = df[df["id"] == key.id]
            for row in filtered_df.to_dict(orient="records"):
                requirement_version = build_requirementversionobject_from_row_data(row, config)
                if requirement_version.name in seen_versions:
                    continue
                seen_versions.add(requirement_version.name)
                requirement_versions.append(requirement_version)

        requirement_versions.sort(key=lambda version: version.date)
        return requirement_versions

    def _find_extended_requirement_in_file(
        self,
        baseline_file: Path,
        config: ExcelRequirementReaderConfig,
        baseline: str,
        key: RequirementKey,
    ) -> ExtendedRequirementObject | None:
        df = self._get_dataframe(baseline_file, config)
        filtered_df = df[(df["id"] == key.id) & (df["version"] == key.version)]
        if filtered_df.empty:
            return None
        row_data = filtered_df.iloc[0].to_dict()
        return build_extendedrequirementobject_from_row_data(row_data, config, baseline)

    def _iter_other_baseline_files(self, project: str, baseline_file: Path):
        return (file for file in self._iter_baseline_files(project) if file != baseline_file)

    def _get_project_path(self, project: str) -> Path:
        return self.config.requirementsDataPath / project

    def _get_baseline_path(self, project: str, baseline: str) -> Path:
        file_path: Path | None = next(
            (file for file in self._iter_baseline_files(project) if file.stem == baseline),
            None,
        )
        if file_path is None:
            allowed_suffixes = self._get_allowed_suffixes_for_project(project)
            raise NotFound(
                f"Baseline file {(self._get_project_path(project) / baseline).resolve()} "
                f"with suffixes {allowed_suffixes} not found."
            )
        return file_path

    def _get_config_for_project(self, project: str) -> ExcelRequirementReaderConfig:
        project_config_path = self._get_project_path(project) / f"{project}.properties"
        if project_config_path.exists():
            project_config = load_reader_config_from_path(
                project_config_path, ExcelRequirementReaderProjectConfig
            )
            return self.config.model_copy(update=project_config.model_dump(exclude_unset=True))
        return self.config

    def _get_allowed_suffixes_for_project(self, project: str) -> list:
        config = self._get_config_for_project(project)
        if config.useExcelDirectly:
            return [".xls", ".xlsx"]
        return config.baselineFileExtensions

    def _get_files_in_project_path(self, project: str, pattern: str = "*"):
        config = self._get_config_for_project(project)
        if config.baselinesFromSubfolders:
            return self._get_project_path(project).rglob(pattern)
        return self._get_project_path(project).glob(pattern)

    def _is_temp_baseline_file(self, file_path: Path) -> bool:
        name = file_path.name
        if name in {".DS_Store"}:
            return True
        if name.startswith(("~$", "._", ".~lock.")):
            return True
        if name.endswith((".tmp", ".swp", ".bak", "~")):
            return True
        return name.startswith(".~lock.") and name.endswith("#")

    def _get_dataframe(self, file_path: Path, config: ExcelRequirementReaderConfig) -> pd.DataFrame:
        max_age_seconds, max_size_bytes = self._get_buffer_limits(config)

        if max_age_seconds <= 0 or max_size_bytes <= 0:
            return read_data_frame_from_file_path(file_path, config)

        cache_key = file_path.as_posix()
        current_mtime = file_path.stat().st_mtime

        with self._buffer_lock:
            self._purge_expired_entries(max_age_seconds)
            entry = self._buffer_catalog.get(cache_key)
            if entry and entry.file_mtime == current_mtime:
                entry.last_accessed_at = time.time()
                return entry.data_frame
            if entry and entry.file_mtime != current_mtime:
                logger.debug(
                    "Refreshing buffered dataframe '%s': source file modified.",
                    file_path,
                )

        df = read_data_frame_from_file_path(file_path, config)
        size_bytes = int(df.memory_usage(index=True, deep=True).sum())
        now = time.time()

        with self._buffer_lock:
            existing_entry = self._buffer_catalog.get(cache_key)
            if existing_entry:
                self._buffer_size_bytes -= existing_entry.size_bytes

            self._buffer_catalog[cache_key] = DataFrameBufferEntry(
                data_frame=df,
                last_accessed_at=now,
                file_mtime=current_mtime,
                size_bytes=size_bytes,
            )
            self._buffer_size_bytes += size_bytes

            logger.info(
                "Buffered dataframe '%s' (%.2f MiB). Total buffer: %.2f MiB",
                file_path,
                size_bytes / (1024**2),
                self._buffer_size_bytes / (1024**2),
            )

            self._enforce_buffer_size_limit(max_size_bytes)
        return df

    def _get_buffer_limits(self, config: ExcelRequirementReaderConfig) -> tuple[float, int]:
        max_age_minutes = float(getattr(config, "bufferMaxAgeMinutes", 0) or 0)
        max_size_mib = float(getattr(config, "bufferMaxSizeMiB", 0) or 0)
        return max_age_minutes * 60, int(max_size_mib * 1024**2)

    def _get_buffer_cleanup_interval_seconds(self, config: ExcelRequirementReaderConfig) -> float:
        return float(getattr(config, "bufferCleanupIntervalMinutes", 0) or 0) * 60

    def _purge_expired_entries(self, max_age_seconds: float) -> None:
        if max_age_seconds <= 0:
            return
        now = time.time()
        expired_keys = [
            key
            for key, entry in self._buffer_catalog.items()
            if now - entry.last_accessed_at >= max_age_seconds
        ]

        if not expired_keys:
            return

        for key in expired_keys:
            entry = self._buffer_catalog.pop(key)
            self._buffer_size_bytes -= entry.size_bytes

        logger.info(
            "Purged %d buffered dataframe(s). Total buffer: %.2f MiB",
            len(expired_keys),
            self._buffer_size_bytes / (1024**2),
        )

    def _enforce_buffer_size_limit(self, max_size_bytes: int) -> None:
        if max_size_bytes <= 0 or self._buffer_size_bytes <= max_size_bytes:
            return

        target_size_bytes = int(max_size_bytes * 0.8)
        removed = 0

        for key, entry in sorted(
            self._buffer_catalog.items(), key=lambda item: item[1].last_accessed_at
        ):
            if self._buffer_size_bytes <= target_size_bytes:
                break
            self._buffer_catalog.pop(key)
            self._buffer_size_bytes -= entry.size_bytes
            removed += 1

        if removed:
            logger.info(
                "Evicted %d buffered dataframe(s) to enforce size limit. Total buffer: %.2f MiB",
                removed,
                self._buffer_size_bytes / (1024**2),
            )

    def _start_buffer_cleanup_thread(self) -> None:
        interval_seconds = self._get_buffer_cleanup_interval_seconds(self.config)
        max_age_seconds, _ = self._get_buffer_limits(self.config)

        if interval_seconds <= 0 or max_age_seconds <= 0:
            return

        def _cleanup_loop() -> None:
            while True:
                time.sleep(interval_seconds)
                try:
                    with self._buffer_lock:
                        self._purge_expired_entries(max_age_seconds)
                except Exception as exc:
                    logger.warning("Buffer cleanup task failed: %s", exc)

        thread = threading.Thread(target=_cleanup_loop, name="excel-buffer-cleanup", daemon=True)
        thread.start()
