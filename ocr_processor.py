"""
OCR処理を担当するモジュール

yomitokuのDocumentAnalyzerを使用してPDF画像に対しOCR処理を実行し、
テキストとバウンディングボックス情報を抽出します。
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import fitz  # PyMuPDF
import numpy as np

try:
    from yomitoku import DocumentAnalyzer
except ImportError as e:
    logging.error(f"yomitokuのインポートに失敗しました: {e}")
    logging.error("pip install yomitoku または poetry install --extras cpu/cuda を実行してください")
    raise

from data_structures import DocumentOCRResult, PageOCRResult, convert_legacy_ocr_result

logger = logging.getLogger(__name__)


class OCRProcessor:
    """
    yomitokuを使用してOCR処理を実行するクラス
    """

    def __init__(self, device: str = "cuda", visualize: bool = False):
        """
        OCRProcessorの初期化

        Args:
            device (str): 計算デバイス ("cuda" または "cpu")
            visualize (bool): 可視化結果を生成するかどうか
        """
        self.device = device
        self.visualize = visualize
        self.analyzer = None

        logger.info(f"OCRProcessor初期化 - device: {device}, visualize: {visualize}")

    def _initialize_analyzer(self) -> None:
        """
        DocumentAnalyzerの遅延初期化
        初回使用時にモデルをロードします
        """
        if self.analyzer is None:
            logger.info("DocumentAnalyzerを初期化しています...")
            try:
                self.analyzer = DocumentAnalyzer(visualize=self.visualize, device=self.device)
                logger.info("DocumentAnalyzerの初期化が完了しました")
            except Exception as e:
                logger.error(f"DocumentAnalyzerの初期化に失敗しました: {e}")
                raise

    def pixmap_to_numpy(self, pixmap: fitz.Pixmap) -> np.ndarray:
        """
        PyMuPDFのPixmapをnumpy配列に変換

        Args:
            pixmap (fitz.Pixmap): PyMuPDFのPixmapオブジェクト

        Returns:
            np.ndarray: BGRフォーマットの画像配列 (OpenCV形式)
        """
        try:
            # Pixmapのバイトデータを取得
            pix_data = pixmap.samples

            # 画像の形状を取得
            width = pixmap.width
            height = pixmap.height
            stride = pixmap.stride

            # numpy配列に変換
            if pixmap.n == 4:  # RGBA
                img_array = np.frombuffer(pix_data, dtype=np.uint8).reshape(height, stride // 4, 4)
                # RGBAからBGRに変換 (アルファチャンネルを除去)
                img_array = img_array[:, :width, [2, 1, 0]]  # RGBA -> BGR
            elif pixmap.n == 3:  # RGB
                img_array = np.frombuffer(pix_data, dtype=np.uint8).reshape(height, stride // 3, 3)
                # RGBからBGRに変換
                img_array = img_array[:, :width, [2, 1, 0]]  # RGB -> BGR
            elif pixmap.n == 1:  # Grayscale
                img_array = np.frombuffer(pix_data, dtype=np.uint8).reshape(height, stride)
                img_array = img_array[:, :width]
                # グレースケールをBGRに変換
                img_array = np.stack([img_array, img_array, img_array], axis=2)
            else:
                raise ValueError(f"サポートされていないチャンネル数: {pixmap.n}")

            # 配列のcontiguousメモリレイアウトを確保
            img_array = np.ascontiguousarray(img_array, dtype=np.uint8)

            logger.debug(f"Pixmap変換完了 - shape: {img_array.shape}, dtype: {img_array.dtype}")
            return img_array

        except Exception as e:
            logger.error(f"Pixmap変換エラー: {e}")
            raise

    async def perform_ocr_async(self, pixmap: fitz.Pixmap) -> Dict[str, Any]:
        """
        非同期OCR処理を実行

        Args:
            pixmap (fitz.Pixmap): PyMuPDFのPixmapオブジェクト

        Returns:
            Dict[str, Any]: OCR結果を含む辞書
                - 'success': 処理成功フラグ
                - 'results': DocumentAnalyzerの結果オブジェクト
                - 'ocr_vis': OCR可視化画像 (visualize=Trueの場合)
                - 'layout_vis': レイアウト可視化画像 (visualize=Trueの場合)
                - 'error': エラーメッセージ (失敗時)
        """
        try:
            # DocumentAnalyzerの初期化（遅延初期化）
            self._initialize_analyzer()

            # PixmapをOpenCV形式の画像に変換
            img_array = self.pixmap_to_numpy(pixmap)

            logger.debug(f"OCR処理開始 - 画像サイズ: {img_array.shape}")

            # yomitokuでOCR実行
            if self.visualize:
                results, ocr_vis, layout_vis = self.analyzer(img_array)

                return {
                    "success": True,
                    "results": results,
                    "ocr_vis": ocr_vis,
                    "layout_vis": layout_vis,
                    "error": None,
                }
            else:
                results, _, _ = self.analyzer(img_array)

                return {"success": True, "results": results, "ocr_vis": None, "layout_vis": None, "error": None}

        except Exception as e:
            error_msg = f"OCR処理中にエラーが発生しました: {e}"
            logger.error(error_msg)
            return {"success": False, "results": None, "ocr_vis": None, "layout_vis": None, "error": error_msg}

    def perform_ocr(self, pixmap: fitz.Pixmap) -> Dict[str, Any]:
        """
        OCR処理を実行

        Args:
            pixmap (fitz.Pixmap): PyMuPDFのPixmapオブジェクト

        Returns:
            Dict[str, Any]: OCR結果を含む辞書
                - 'success': 処理成功フラグ
                - 'results': DocumentAnalyzerの結果オブジェクト
                - 'ocr_vis': OCR可視化画像 (visualize=Trueの場合)
                - 'layout_vis': レイアウト可視化画像 (visualize=Trueの場合)
                - 'error': エラーメッセージ (失敗時)
        """
        try:
            # DocumentAnalyzerの初期化（遅延初期化）
            self._initialize_analyzer()

            # PixmapをOpenCV形式の画像に変換
            img_array = self.pixmap_to_numpy(pixmap)

            logger.debug(f"OCR処理開始 - 画像サイズ: {img_array.shape}")

            # yomitokuでOCR実行
            if self.visualize:
                results, ocr_vis, layout_vis = self.analyzer(img_array)

                return {
                    "success": True,
                    "results": results,
                    "ocr_vis": ocr_vis,
                    "layout_vis": layout_vis,
                    "error": None,
                }
            else:
                results, _, _ = self.analyzer(img_array)

                return {"success": True, "results": results, "ocr_vis": None, "layout_vis": None, "error": None}

        except Exception as e:
            error_msg = f"OCR処理中にエラーが発生しました: {e}"
            logger.error(error_msg)
            return {"success": False, "results": None, "ocr_vis": None, "layout_vis": None, "error": error_msg}

    def perform_ocr_structured(self, pixmap: fitz.Pixmap, page_number: int) -> PageOCRResult:
        """
        OCR処理を実行し、構造化されたPageOCRResultを返す

        Args:
            pixmap (fitz.Pixmap): PyMuPDFのPixmapオブジェクト
            page_number (int): ページ番号

        Returns:
            PageOCRResult: 構造化されたOCR結果
        """
        start_time = time.time()

        try:
            # 従来のOCR処理を実行
            ocr_result = self.perform_ocr(pixmap)

            if ocr_result["success"]:
                # OCR結果を解析
                text_blocks = parse_ocr_results(ocr_result["results"])

                # 新しいデータ構造に変換
                result = convert_legacy_ocr_result(
                    page_number=page_number,
                    text_blocks=text_blocks,
                    page_width=float(pixmap.width),
                    page_height=float(pixmap.height),
                    success=True,
                    error=None,
                    processing_time=time.time() - start_time,
                )

                logger.info(
                    f"ページ {page_number}: {result.text_count}個のテキストブロックを検出 "
                    f"(平均信頼度: {result.average_confidence:.3f})"
                )

                return result

            else:
                return PageOCRResult(
                    page_number=page_number,
                    text_blocks=[],
                    page_width=float(pixmap.width),
                    page_height=float(pixmap.height),
                    success=False,
                    error=ocr_result["error"],
                    processing_time=time.time() - start_time,
                )

        except Exception as e:
            logger.error(f"ページ {page_number} のOCR処理でエラー: {e}")
            return PageOCRResult(
                page_number=page_number,
                text_blocks=[],
                page_width=float(pixmap.width) if pixmap else 0.0,
                page_height=float(pixmap.height) if pixmap else 0.0,
                success=False,
                error=str(e),
                processing_time=time.time() - start_time,
            )

    def process_document(self, pixmaps: List[fitz.Pixmap], input_file: Path, dpi: int = 300) -> DocumentOCRResult:
        """
        文書全体のOCR処理を実行

        Args:
            pixmaps: PDFページのPixmapリスト
            input_file: 入力PDFファイルのパス
            dpi: DPI設定

        Returns:
            DocumentOCRResult: 文書全体のOCR結果
        """
        start_time = time.time()

        logger.info(f"文書OCR処理開始: {len(pixmaps)}ページ")

        pages = []
        for i, pixmap in enumerate(pixmaps, 1):
            logger.info(f"ページ {i}/{len(pixmaps)} を処理中...")
            page_result = self.perform_ocr_structured(pixmap, i)
            pages.append(page_result)

        total_time = time.time() - start_time

        result = DocumentOCRResult(
            input_file=input_file, pages=pages, total_processing_time=total_time, device_used=self.device, dpi=dpi
        )

        logger.info(
            f"文書OCR処理完了: {result.successful_pages}/{result.total_pages}ページ成功, "
            f"{result.total_text_blocks}個のテキストブロック検出, "
            f"処理時間: {total_time:.2f}秒"
        )

        return result


def parse_ocr_results(results) -> List[Dict[str, Any]]:
    """
    yomitokuのOCR結果を解析して、テキストとバウンディングボックス情報を抽出

    Args:
        results: yomitokuのDocumentAnalyzerの結果オブジェクト

    Returns:
        List[Dict[str, Any]]: テキストブロックのリスト
            各要素は以下の形式:
            {
                'text': str,  # テキスト内容
                'bbox': [x0, y0, x1, y1],  # バウンディングボックス座標
                'confidence': float,  # 信頼度
                'direction': str  # テキストの方向 ('horizontal' or 'vertical')
            }
    """
    text_blocks = []

    try:
        # DocumentAnalyzerSchemaからwords情報を取得
        if hasattr(results, "words") and results.words:
            for word in results.words:
                # word.pointsは4点の座標 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                # これをbbox [x0, y0, x1, y1] 形式に変換
                points = word.points
                if len(points) == 4:
                    # 4点から最小外接矩形を計算
                    xs = [point[0] for point in points]
                    ys = [point[1] for point in points]
                    x0, y0 = min(xs), min(ys)
                    x1, y1 = max(xs), max(ys)

                    text_block = {
                        "text": word.content,
                        "bbox": [x0, y0, x1, y1],
                        "confidence": getattr(word, "rec_score", 1.0),  # 認識スコア
                        "direction": getattr(word, "direction", "horizontal"),  # テキスト方向
                    }
                    text_blocks.append(text_block)

        # 段落情報も追加（paragraphs）
        if hasattr(results, "paragraphs") and results.paragraphs:
            for paragraph in results.paragraphs:
                if hasattr(paragraph, "contents") and paragraph.contents:
                    # paragraphのboxは [x0, y0, x1, y1] 形式
                    bbox = paragraph.box if hasattr(paragraph, "box") else [0, 0, 0, 0]

                    text_block = {
                        "text": paragraph.contents,
                        "bbox": bbox,
                        "confidence": 1.0,  # 段落レベルでは固定値
                        "direction": getattr(paragraph, "direction", "horizontal"),
                    }
                    text_blocks.append(text_block)

        logger.info(f"OCR結果解析完了 - {len(text_blocks)}個のテキストブロックを検出")

    except Exception as e:
        logger.error(f"OCR結果の解析中にエラーが発生しました: {e}")
        logger.debug(f"results型: {type(results)}")
        logger.debug(f"results属性: {dir(results) if hasattr(results, '__dict__') else 'N/A'}")

    return text_blocks


def create_test_processor(device: str = "cpu", visualize: bool = False) -> OCRProcessor:
    """
    テスト用のOCRProcessorインスタンスを作成

    Args:
        device (str): 計算デバイス
        visualize (bool): 可視化フラグ

    Returns:
        OCRProcessor: 設定済みのOCRProcessorインスタンス
    """
    return OCRProcessor(device=device, visualize=visualize)


if __name__ == "__main__":
    # 簡単なテスト実行例
    logging.basicConfig(level=logging.INFO)

    print("OCRProcessorのテスト実行...")

    # テスト用プロセッサを作成
    processor = create_test_processor(device="cpu", visualize=True)

    print("OCRProcessorの作成が完了しました")
    print("実際のOCR処理を実行するには、main.pyから呼び出してください")
