"""
PDF OCR処理用のデータ構造定義

OCR結果とPDF処理で使用する統一的なデータ構造を定義します。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BoundingBox:
    """バウンディングボックスを表すデータクラス"""

    x0: float  # 左上X座標
    y0: float  # 左上Y座標
    x1: float  # 右下X座標
    y1: float  # 右下Y座標

    @property
    def width(self) -> float:
        """幅を計算"""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """高さを計算"""
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        """面積を計算"""
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        """中央座標を計算"""
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def intersection(self, other: "BoundingBox") -> Optional["BoundingBox"]:
        """他のBoundingBoxとの重複領域を計算"""
        x0 = max(self.x0, other.x0)
        y0 = max(self.y0, other.y0)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)

        if x0 < x1 and y0 < y1:
            return BoundingBox(x0, y0, x1, y1)
        return None

    def intersection_area(self, other: "BoundingBox") -> float:
        """他のBoundingBoxとの重複面積を計算"""
        intersection = self.intersection(other)
        return intersection.area if intersection else 0.0

    def overlap_ratio(self, other: "BoundingBox") -> float:
        """自身の面積に対する重複領域の割合を計算"""
        if self.area == 0:
            return 0.0
        return self.intersection_area(other) / self.area

    def to_list(self) -> List[float]:
        """リスト形式で返す [x0, y0, x1, y1]"""
        return [self.x0, self.y0, self.x1, self.y1]

    @classmethod
    def from_list(cls, coords: List[float]) -> "BoundingBox":
        """リストからBoundingBoxを作成"""
        if len(coords) != 4:
            raise ValueError(f"座標は4つの値が必要です: {coords}")
        return cls(coords[0], coords[1], coords[2], coords[3])


@dataclass
class TextBlock:
    """OCRで検出されたテキストブロックを表すデータクラス"""

    text: str  # テキスト内容
    bbox: BoundingBox  # バウンディングボックス
    confidence: float  # 信頼度 (0.0-1.0)
    direction: str = "horizontal"  # テキスト方向
    block_id: Optional[int] = None  # ブロックID

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で返す"""
        return {
            "text": self.text,
            "bbox": self.bbox.to_list(),
            "confidence": self.confidence,
            "direction": self.direction,
            "block_id": self.block_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextBlock":
        """辞書からTextBlockを作成"""
        return cls(
            text=data["text"],
            bbox=BoundingBox.from_list(data["bbox"]),
            confidence=data["confidence"],
            direction=data.get("direction", "horizontal"),
            block_id=data.get("block_id"),
        )


@dataclass
class PageOCRResult:
    """1ページのOCR結果を表すデータクラス"""

    page_number: int  # ページ番号 (1から開始)
    text_blocks: List[TextBlock]  # テキストブロックのリスト
    page_width: float  # ページ幅 (ピクセル)
    page_height: float  # ページ高さ (ピクセル)
    success: bool = True  # 処理成功フラグ
    error: Optional[str] = None  # エラーメッセージ
    processing_time: float = 0.0  # 処理時間（秒）

    @property
    def total_text(self) -> str:
        """全テキストを結合して返す"""
        return " ".join(block.text for block in self.text_blocks)

    @property
    def text_count(self) -> int:
        """テキストブロック数を返す"""
        return len(self.text_blocks)

    @property
    def average_confidence(self) -> float:
        """平均信頼度を計算"""
        if not self.text_blocks:
            return 0.0
        return sum(block.confidence for block in self.text_blocks) / len(self.text_blocks)

    def remove_duplicate_blocks(self, overlap_threshold: float = 0.6) -> int:
        """
        重複テキストブロックを削除する

        条件:
        - bbox領域の6割以上が他テキストブロックに重複している
        - その重複しているテキストブロックよりも自身のbboxが小さい

        Args:
            overlap_threshold: 重複判定の閾値（デフォルト: 0.6 = 60%）

        Returns:
            削除されたブロック数
        """
        if len(self.text_blocks) <= 1:
            return 0

        blocks_to_remove = set()

        for i, block_a in enumerate(self.text_blocks):
            if i in blocks_to_remove:
                continue

            for j, block_b in enumerate(self.text_blocks):
                if i == j or j in blocks_to_remove:
                    continue

                # block_aがblock_bと重複しているかチェック
                overlap_ratio = block_a.bbox.overlap_ratio(block_b.bbox)

                # 重複率が閾値を超え、かつblock_aの方が小さい場合
                if overlap_ratio >= overlap_threshold and block_a.bbox.area < block_b.bbox.area:
                    blocks_to_remove.add(i)
                    break

        # 削除対象のブロックを除外した新しいリストを作成
        original_count = len(self.text_blocks)
        self.text_blocks = [block for i, block in enumerate(self.text_blocks) if i not in blocks_to_remove]

        removed_count = original_count - len(self.text_blocks)
        return removed_count

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で返す"""
        return {
            "page_number": self.page_number,
            "text_blocks": [block.to_dict() for block in self.text_blocks],
            "page_width": self.page_width,
            "page_height": self.page_height,
            "success": self.success,
            "error": self.error,
            "processing_time": self.processing_time,
            "total_text": self.total_text,
            "text_count": self.text_count,
            "average_confidence": self.average_confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageOCRResult":
        """辞書からPageOCRResultを作成"""
        return cls(
            page_number=data["page_number"],
            text_blocks=[TextBlock.from_dict(block) for block in data["text_blocks"]],
            page_width=data["page_width"],
            page_height=data["page_height"],
            success=data.get("success", True),
            error=data.get("error"),
            processing_time=data.get("processing_time", 0.0),
        )


@dataclass
class DocumentOCRResult:
    """文書全体のOCR結果を表すデータクラス"""

    input_file: Path  # 入力PDFファイル
    pages: List[PageOCRResult]  # ページごとのOCR結果
    total_processing_time: float = 0.0  # 総処理時間
    device_used: str = "cpu"  # 使用デバイス
    dpi: int = 300  # DPI設定

    @property
    def total_pages(self) -> int:
        """総ページ数"""
        return len(self.pages)

    @property
    def successful_pages(self) -> int:
        """成功したページ数"""
        return sum(1 for page in self.pages if page.success)

    @property
    def total_text_blocks(self) -> int:
        """全ページの総テキストブロック数"""
        return sum(page.text_count for page in self.pages)

    @property
    def document_text(self) -> str:
        """文書全体のテキスト"""
        return "\n\n".join(page.total_text for page in self.pages if page.success)

    def remove_duplicate_blocks(self, overlap_threshold: float = 0.6) -> Dict[int, int]:
        """
        全ページの重複テキストブロックを削除する

        Args:
            overlap_threshold: 重複判定の閾値（デフォルト: 0.6 = 60%）

        Returns:
            各ページで削除されたブロック数の辞書 {page_number: removed_count}
        """
        removed_counts = {}

        for page in self.pages:
            if page.success and page.text_blocks:
                removed_count = page.remove_duplicate_blocks(overlap_threshold)
                if removed_count > 0:
                    removed_counts[page.page_number] = removed_count

        return removed_counts

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で返す"""
        return {
            "input_file": str(self.input_file),
            "pages": [page.to_dict() for page in self.pages],
            "total_processing_time": self.total_processing_time,
            "device_used": self.device_used,
            "dpi": self.dpi,
            "summary": {
                "total_pages": self.total_pages,
                "successful_pages": self.successful_pages,
                "total_text_blocks": self.total_text_blocks,
                "document_length": len(self.document_text),
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentOCRResult":
        """辞書からDocumentOCRResultを作成"""
        return cls(
            input_file=Path(data["input_file"]),
            pages=[PageOCRResult.from_dict(page) for page in data["pages"]],
            total_processing_time=data.get("total_processing_time", 0.0),
            device_used=data.get("device_used", "cpu"),
            dpi=data.get("dpi", 300),
        )


def convert_legacy_ocr_result(
    page_number: int,
    text_blocks: List[Dict[str, Any]],
    page_width: float,
    page_height: float,
    success: bool = True,
    error: Optional[str] = None,
    processing_time: float = 0.0,
) -> PageOCRResult:
    """
    従来のOCR結果形式から新しいPageOCRResult形式に変換

    Args:
        page_number: ページ番号
        text_blocks: テキストブロックのリスト（辞書形式）
        page_width: ページ幅
        page_height: ページ高さ
        success: 成功フラグ
        error: エラーメッセージ
        processing_time: 処理時間

    Returns:
        PageOCRResult: 変換されたOCR結果
    """
    converted_blocks = []

    for i, block in enumerate(text_blocks):
        text_block = TextBlock(
            text=block["text"],
            bbox=BoundingBox.from_list(block["bbox"]),
            confidence=block["confidence"],
            direction=block.get("direction", "horizontal"),
            block_id=i + 1,
        )
        converted_blocks.append(text_block)

    return PageOCRResult(
        page_number=page_number,
        text_blocks=converted_blocks,
        page_width=page_width,
        page_height=page_height,
        success=success,
        error=error,
        processing_time=processing_time,
    )


def save_ocr_results(results: DocumentOCRResult, output_path: Path) -> None:
    """OCR結果をJSONファイルに保存"""
    import json

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results.to_dict(), f, ensure_ascii=False, indent=2)


def load_ocr_results(input_path: Path) -> DocumentOCRResult:
    """JSONファイルからOCR結果を読み込み"""
    import json

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return DocumentOCRResult.from_dict(data)
