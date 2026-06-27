"""文物检索服务模块。

桥接视觉描述（VisualDescription）与百炼知识库检索，
将视觉描述文本发送到百炼视觉检索应用，解析返回的匹配结果。

核心流程：
1. 从 VisualDescription 构建检索 prompt
2. 调用百炼视觉检索应用（挂视觉指纹知识库）
3. 解析返回的 JSON → ArtifactMatchResult
4. 根据匹配置信度决定后续讲解策略
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from services.bailian_app_service import BailianAppService
from services.vision_service import VisualDescription


@dataclass(frozen=True)
class ArtifactMatchResult:
    """知识库检索匹配结果。

    由百炼视觉检索应用返回，包含匹配到的文物 ID 和置信度。

    Attributes:
        match_id: 匹配到的文物 ID（如 yingguo_yuying），none 表示未匹配
        match_name: 匹配到的文物名称（如 应国玉鹰）
        confidence: 匹配置信度 (0.0~1.0)
        evidence: 匹配依据说明
        raw_response: 百炼应用原始返回文本（调试用）
    """
    match_id: str = "none"
    match_name: str = "无"
    confidence: float = 0.0
    evidence: str = ""
    raw_response: str = ""

    @property
    def is_matched(self) -> bool:
        """是否匹配置信度足够高，可以进行具体讲解。"""
        return self.match_id != "none" and self.confidence >= 0.6

    def to_dict(self) -> dict[str, Any]:
        """转为字典格式。"""
        return asdict(self)


class ArtifactSearchService:
    """文物检索服务。

    将 VisualDescription 发送到百炼视觉检索应用（挂视觉指纹知识库），
    获取最匹配的文物 ID 和名称。

    Attributes:
        bailian: 百炼视觉检索应用服务实例
    """

    def __init__(self, bailian_vision_service: BailianAppService):
        """初始化文物检索服务。

        Args:
            bailian_vision_service: 百炼视觉检索应用实例（挂视觉指纹知识库）
        """
        self.bailian = bailian_vision_service

    def search(self, desc: VisualDescription) -> ArtifactMatchResult:
        """同步检索最匹配的文物。

        Web 路由应优先使用 ``search_async``。

        Args:
            desc: 视觉描述

        Returns:
            ArtifactMatchResult: 匹配结果
        """
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("ArtifactSearchService.search() 不能在事件循环中调用，请改用 search_async()")
        return asyncio.run(self.search_async(desc))

    async def search_async(self, desc: VisualDescription) -> ArtifactMatchResult:
        """异步检索最匹配的文物。

        Args:
            desc: 视觉描述

        Returns:
            ArtifactMatchResult: 匹配结果
        """
        total_start = time.perf_counter()
        prompt = self._build_search_prompt(desc)
        print(f"[SEARCH] 检索 prompt 长度={len(prompt)}", flush=True)

        try:
            response = await self.bailian.ask_async(prompt)
        except Exception as exc:
            print(f"[SEARCH] 百炼调用异常 error={exc}", flush=True)
            return ArtifactMatchResult(evidence=f"检索调用异常: {exc}")

        result = self._parse_response(response)
        print(
            f"[SEARCH] match_id={result.match_id} match_name={result.match_name} "
            f"confidence={result.confidence:.2f} cost={time.perf_counter() - total_start:.3f}s",
            flush=True,
        )
        return result

    def _build_search_prompt(self, desc: VisualDescription) -> str:
        """构建知识库检索 prompt。

        将 VisualDescription 的各字段组合为检索文本，
        发送到百炼视觉检索应用进行语义匹配。

        Args:
            desc: 视觉描述

        Returns:
            str: 检索 prompt
        """
        parts = []
        parts.append("请在知识库中找到与以下视觉描述最匹配的文物。")
        parts.append("")
        parts.append(f"视觉描述：{desc.visual_description}")
        parts.append(f"类别：{desc.category}")
        if desc.shape_features:
            parts.append(f"形态特征：{' '.join(desc.shape_features)}")
        if desc.decoration_features:
            parts.append(f"纹饰特征：{' '.join(desc.decoration_features)}")
        if desc.color_material:
            parts.append(f"颜色材质：{' '.join(desc.color_material)}")
        if desc.search_keywords:
            parts.append(f"关键词：{' '.join(desc.search_keywords)}")
        if desc.risk:
            parts.append(f"注意：{desc.risk}")

        parts.append("")
        parts.append("规则：")
        parts.append("- 只根据视觉描述的相似度匹配，不依赖年代、历史等非视觉信息")
        parts.append("- 有充分匹配依据时才给出匹配，否则返回无匹配")
        parts.append("- 不要编造文物名称，只使用知识库中已有的标准名称")
        parts.append("- 只返回 JSON，不要额外文字")
        parts.append("")
        parts.append('匹配成功返回：{"match_id":"yingguo_yuying","match_name":"应国玉鹰","confidence":0.85,"evidence":"双翼展开、浅色玉质、线刻纹饰与知识库描述高度吻合"}')
        parts.append('无匹配返回：{"match_id":"none","match_name":"无","confidence":0.0,"evidence":"知识库中无匹配的视觉描述"}')

        return "\n".join(parts)

    def _parse_response(self, text: str) -> ArtifactMatchResult:
        """解析百炼视觉检索应用的响应。

        尝试从响应中提取 JSON 匹配结果。

        Args:
            text: 百炼应用返回的原始文本

        Returns:
            ArtifactMatchResult: 解析后的匹配结果
        """
        if not text or not text.strip():
            return ArtifactMatchResult(evidence="检索返回为空", raw_response=text)

        cleaned = text.strip()
        # 去除 Markdown 代码块包装
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # 正则提取第一个 JSON 对象
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if not match:
                return ArtifactMatchResult(
                    evidence=f"无法解析检索结果: {text[:200]}",
                    raw_response=text,
                )
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return ArtifactMatchResult(
                    evidence=f"JSON 解析失败: {text[:200]}",
                    raw_response=text,
                )

        if not isinstance(data, dict):
            return ArtifactMatchResult(evidence="检索结果格式异常", raw_response=text)

        match_id = str(data.get("match_id") or "none").strip()
        match_name = str(data.get("match_name") or "无").strip()
        if match_id == "none":
            match_name = "无"

        confidence = 0.0
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            pass
        confidence = max(0.0, min(1.0, confidence))

        evidence = str(data.get("evidence") or "").strip()

        return ArtifactMatchResult(
            match_id=match_id,
            match_name=match_name,
            confidence=confidence,
            evidence=evidence,
            raw_response=text,
        )
