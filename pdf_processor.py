"""
PDF処理モジュール

PDFファイルの読み込み、ページごとの画像変換、
検索可能なPDF生成機能を提供します。
"""

import logging
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from data_structures import PageOCRResult


def convert_pdf_to_images(pdf_path: Path, dpi: int = 300) -> List[fitz.Pixmap]:
    """
    PDFファイルを各ページごとに画像（Pixmap）に変換する

    Args:
        pdf_path (Path): 変換するPDFファイルのパス
        dpi (int): 画像変換時のDPI（デフォルト: 300）

    Returns:
        List[fitz.Pixmap]: 各ページのPixmapオブジェクトのリスト

    Raises:
        FileNotFoundError: PDFファイルが見つからない場合
        Exception: PDF読み込みまたは変換時のエラー
    """
    logger = logging.getLogger(__name__)

    # ファイル存在確認
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

    logger.info(f"PDFファイルを開きます: {pdf_path}")
    logger.info(f"DPI設定: {dpi}")

    try:
        # PDFファイルを開く
        pdf_document = fitz.open(pdf_path)
        logger.info(f"PDFページ数: {pdf_document.page_count}")

        pixmaps = []

        # 各ページを画像に変換
        for page_num in range(pdf_document.page_count):
            logger.debug(f"ページ {page_num + 1}/{pdf_document.page_count} を処理中...")

            # ページオブジェクトを取得
            page = pdf_document.load_page(page_num)

            # DPIに基づいてスケール行列を作成
            # デフォルトは72 DPIなので、指定されたDPIとの比率を計算
            scale = dpi / 72.0
            matrix = fitz.Matrix(scale, scale)

            # ページをPixmapに変換
            pixmap = page.get_pixmap(matrix=matrix)

            # ページサイズ情報をログ出力
            logger.debug(f"ページ {page_num + 1}: サイズ {pixmap.width}x{pixmap.height} px")

            pixmaps.append(pixmap)

        # PDFドキュメントを閉じる
        pdf_document.close()

        logger.info(f"PDF画像変換が完了しました。変換されたページ数: {len(pixmaps)}")
        return pixmaps

    except Exception as e:
        logger.error(f"PDF画像変換中にエラーが発生しました: {e}")
        # ドキュメントが開かれている場合は閉じる
        try:
            if "pdf_document" in locals():
                pdf_document.close()
        except Exception:
            pass
        raise


def get_pdf_info(pdf_path: Path) -> dict:
    """
    PDFファイルの基本情報を取得する

    Args:
        pdf_path (Path): PDFファイルのパス

    Returns:
        dict: PDF情報（ページ数、メタデータなど）
    """
    logger = logging.getLogger(__name__)

    try:
        pdf_document = fitz.open(pdf_path)

        info = {
            "page_count": pdf_document.page_count,
            "metadata": pdf_document.metadata,
            "is_encrypted": pdf_document.is_encrypted,
            "is_pdf": pdf_document.is_pdf,
        }

        # 各ページのサイズ情報を取得
        page_sizes = []
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            rect = page.rect
            page_sizes.append(
                {
                    "page": page_num + 1,
                    "width": rect.width,
                    "height": rect.height,
                }
            )

        info["page_sizes"] = page_sizes

        pdf_document.close()

        logger.debug(f"PDF情報を取得しました: {info}")
        return info

    except Exception as e:
        logger.error(f"PDF情報取得中にエラーが発生しました: {e}")
        raise


def save_pixmap_as_image(pixmap: fitz.Pixmap, output_path: Path, format: str = "png") -> None:
    """
    Pixmapを画像ファイルとして保存する（デバッグ用）

    Args:
        pixmap (fitz.Pixmap): 保存するPixmapオブジェクト
        output_path (Path): 出力ファイルパス
        format (str): 画像フォーマット（png, jpg, webpなど）
    """
    logger = logging.getLogger(__name__)

    try:
        # フォーマットに応じた拡張子を確認
        if format.lower() == "png":
            image_data = pixmap.tobytes("png")
        elif format.lower() in ["jpg", "jpeg"]:
            image_data = pixmap.tobytes("jpeg")
        elif format.lower() == "webp":
            image_data = pixmap.tobytes("webp")
        else:
            raise ValueError(f"サポートされていない画像フォーマット: {format}")

        # ファイルに保存
        with open(output_path, "wb") as f:
            f.write(image_data)

        logger.debug(f"画像を保存しました: {output_path}")

    except Exception as e:
        logger.error(f"画像保存中にエラーが発生しました: {e}")
        raise


def create_searchable_pdf_page(pixmap: fitz.Pixmap, ocr_result: PageOCRResult, dpi: int = 300) -> fitz.Document:
    """
    元の画像とOCR結果を使って、検索可能なPDFページを作成する

    Args:
        pixmap (fitz.Pixmap): 元のページ画像
        ocr_result (PageOCRResult): OCR結果データ
        dpi (int): DPI設定（座標変換用）

    Returns:
        fitz.Document: 1ページ分のPDFドキュメント

    Raises:
        Exception: PDF作成時のエラー
    """
    logger = logging.getLogger(__name__)

    try:
        # 新しい空のPDFドキュメントを作成
        doc = fitz.open()

        # OCR結果とPixmapのサイズ情報をログ出力
        logger.info(f"ページ {ocr_result.page_number}: Pixmapサイズ {pixmap.width}x{pixmap.height} px")
        logger.info(
            f"ページ {ocr_result.page_number}: OCR結果サイズ {ocr_result.page_width}x{ocr_result.page_height} px"
        )

        # PDFページサイズを72DPI（PDFポイント）に変換
        # Pixmapは指定DPIで作成されているので、PDFポイントに変換する必要がある
        pdf_width = pixmap.width * 72.0 / dpi
        pdf_height = pixmap.height * 72.0 / dpi

        logger.info(f"ページ {ocr_result.page_number}: PDFサイズ {pdf_width:.1f}x{pdf_height:.1f} points")

        # 適切なサイズでPDFページを作成
        page = doc.new_page(width=pdf_width, height=pdf_height)

        # 背景として元の画像を挿入（ページ全体にフィット）
        page.insert_image(page.rect, pixmap=pixmap)

        # OCR結果の各テキストブロックを透明テキストとして埋め込み
        if ocr_result.text_blocks:
            logger.debug(
                f"ページ {ocr_result.page_number}: {len(ocr_result.text_blocks)} 個のテキストブロックを処理中..."
            )

            # OCR座標をPDF座標に変換するためのスケール計算
            # OCR座標はPixmapと同じピクセル座標系だが、PDFはポイント座標系
            x_scale = pdf_width / ocr_result.page_width
            y_scale = pdf_height / ocr_result.page_height

            logger.debug(f"座標変換スケール: x={x_scale:.3f}, y={y_scale:.3f}")

            # OCR座標 -> PDF座標への変換
            # OCRの座標系はページの左上が原点 (0,0)、右下が (width, height)
            # PDFの座標系もページの左上が原点だが、ポイント単位

            for i, text_block in enumerate(ocr_result.text_blocks):
                try:
                    # バウンディングボックスをOCR座標からPDF座標に変換
                    bbox = text_block.bbox

                    # OCR座標をPDF座標にスケール
                    x0 = bbox.x0 * x_scale
                    y0 = bbox.y0 * y_scale
                    x1 = bbox.x1 * x_scale
                    y1 = bbox.y1 * y_scale

                    # デバッグ用：元の座標と変換後座標をログ出力
                    if i < 3:  # 最初の3つだけログ出力
                        logger.info(f"テキストブロック {i + 1}: '{text_block.text[:30]}...'")
                        logger.info(f"  OCR座標: ({bbox.x0}, {bbox.y0}, {bbox.x1}, {bbox.y1})")
                        logger.info(f"  PDF座標: ({x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f})")

                    # テキストの描画設定
                    text_height = y1 - y0
                    font_size = min(text_height * 0.8, 12)  # フォントサイズは矩形の高さに比例
                    if font_size < 6:
                        font_size = 6  # 最小フォントサイズ

                    # 透明テキストを挿入
                    # insert_textは左下基準なので、y座標を調整
                    text_y = y0 + font_size  # テキストベースライン位置

                    page.insert_text(
                        (x0, text_y),  # テキスト開始位置（左下基準）
                        text_block.text,
                        fontsize=font_size,
                        fontname="helv",
                        color=(1, 1, 1),  # 白色（見えないが検索可能）
                        render_mode=3,  # 3 = invisible text (検索可能だが見えない)
                    )

                    logger.debug(
                        f"テキストブロック {i + 1}/{len(ocr_result.text_blocks)}: "
                        f"'{text_block.text[:20]}...' をPDF座標 ({x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f}) に挿入"
                    )

                except Exception as e:
                    logger.warning(f"テキストブロック {i + 1} の埋め込みに失敗: {e}")
                    continue

        logger.info(f"ページ {ocr_result.page_number}: 検索可能なPDFページの作成が完了")
        return doc

    except Exception as e:
        logger.error(f"検索可能なPDFページ作成中にエラーが発生しました: {e}")
        raise


def create_searchable_pdf(
    pixmaps: List[fitz.Pixmap], ocr_results: List[PageOCRResult], output_path: Path, dpi: int = 300
) -> None:
    """
    全ページの画像とOCR結果を使って、検索可能なPDFファイルを作成する

    Args:
        pixmaps (List[fitz.Pixmap]): 各ページの画像データ
        ocr_results (List[PageOCRResult]): 各ページのOCR結果
        output_path (Path): 出力PDFファイルのパス
        dpi (int): DPI設定（座標変換用）

    Raises:
        ValueError: ページ数が一致しない場合
        Exception: PDF作成時のエラー
    """
    logger = logging.getLogger(__name__)

    # ページ数の一致確認
    if len(pixmaps) != len(ocr_results):
        raise ValueError(f"画像ページ数 ({len(pixmaps)}) とOCR結果ページ数 ({len(ocr_results)}) が一致しません")

    logger.info(f"検索可能なPDF作成を開始: {len(pixmaps)} ページ")

    try:
        # 最終的な出力用PDFドキュメントを作成
        final_doc = fitz.open()

        for page_num, (pixmap, ocr_result) in enumerate(zip(pixmaps, ocr_results)):
            logger.info(f"ページ {page_num + 1}/{len(pixmaps)} を処理中...")

            # OCR処理が失敗したページの場合は画像のみで処理
            if not ocr_result.success:
                logger.warning(f"ページ {page_num + 1}: OCR結果がないため、画像のみで処理します")
                # 空のOCR結果を作成
                ocr_result = PageOCRResult(
                    page_number=page_num + 1,
                    text_blocks=[],
                    page_width=pixmap.width,
                    page_height=pixmap.height,
                    success=False,
                    error="OCR処理失敗",
                )

            # 1ページ分の検索可能なPDFを作成
            page_doc = create_searchable_pdf_page(pixmap, ocr_result, dpi)

            # 最終ドキュメントにページを追加
            final_doc.insert_pdf(page_doc)

            # 一時的なドキュメントを閉じる
            page_doc.close()

        # 出力ディレクトリを作成（存在しない場合）
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # PDFファイルを保存
        final_doc.save(
            str(output_path), garbage=4, deflate=True, clean=True  # ガベージコレクション  # 圧縮  # クリーンアップ
        )

        final_doc.close()

        logger.info(f"検索可能なPDFファイルの作成が完了: {output_path}")

    except Exception as e:
        logger.error(f"検索可能なPDF作成中にエラーが発生しました: {e}")
        raise


def convert_single_page_to_image(pdf_path: Path, page_num: int, dpi: int = 300) -> fitz.Pixmap:
    """
    PDFファイルの単一ページを画像（Pixmap）に変換する（メモリ効率化）

    Args:
        pdf_path (Path): 変換するPDFファイルのパス
        page_num (int): ページ番号（0から開始）
        dpi (int): 画像変換時のDPI（デフォルト: 300）

    Returns:
        fitz.Pixmap: 指定ページのPixmapオブジェクト

    Raises:
        FileNotFoundError: PDFファイルが見つからない場合
        Exception: PDF読み込みまたは変換時のエラー
    """
    logger = logging.getLogger(__name__)

    # ファイル存在確認
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

    try:
        # PDFファイルを開く
        pdf_document = fitz.open(pdf_path)

        if page_num >= pdf_document.page_count:
            raise ValueError(f"ページ番号が範囲外です: {page_num} (総ページ数: {pdf_document.page_count})")

        # 指定ページをロード
        page = pdf_document.load_page(page_num)

        # DPIに基づいてスケール行列を作成
        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)

        # ページをPixmapに変換
        pixmap = page.get_pixmap(matrix=matrix)

        # PDFドキュメントを閉じる
        pdf_document.close()

        logger.debug(f"ページ {page_num + 1}: サイズ {pixmap.width}x{pixmap.height} px")
        return pixmap

    except Exception as e:
        logger.error(f"PDF単一ページ変換中にエラーが発生しました: {e}")
        # ドキュメントが開かれている場合は閉じる
        try:
            if "pdf_document" in locals():
                pdf_document.close()
        except Exception:
            pass
        raise


def create_memory_efficient_searchable_pdf(
    input_path: Path, pages_results: List[PageOCRResult], output_path: Path, dpi: int
) -> None:
    """
    メモリ効率的な検索可能PDFを作成

    Args:
        input_path (Path): 元のPDFファイルのパス
        pages_results (List[PageOCRResult]): ページごとのOCR結果
        output_path (Path): 出力PDFファイルのパス
        dpi (int): DPI設定
    """
    logger = logging.getLogger(__name__)

    try:
        logger.info("メモリ効率的な検索可能PDF作成を開始...")

        # 新しいPDFドキュメントを作成
        output_doc = fitz.open()

        total_pages = len(pages_results)

        for i, page_result in enumerate(pages_results):
            logger.info(f"ページ {i + 1}/{total_pages} を処理中...")

            try:
                # 1ページずつ画像に変換
                pixmap = convert_single_page_to_image(input_path, i, dpi)

                # 新しいページを作成
                page_rect = fitz.Rect(0, 0, pixmap.width * 72 / dpi, pixmap.height * 72 / dpi)
                page = output_doc.new_page(width=page_rect.width, height=page_rect.height)

                # 元の画像を背景として挿入
                page.insert_image(page_rect, pixmap=pixmap)

                # OCRテキストを透明レイヤーとして埋め込み
                if page_result.success and page_result.text_blocks:
                    for text_block in page_result.text_blocks:
                        try:
                            # 座標変換
                            x_scale = page_rect.width / page_result.page_width
                            y_scale = page_rect.height / page_result.page_height

                            x1 = text_block.bbox.x0 * x_scale
                            y1 = text_block.bbox.y0 * y_scale
                            y2 = text_block.bbox.y1 * y_scale

                            # フォントサイズ計算
                            text_height = y2 - y1
                            font_size = max(1, text_height * 0.8)

                            # 透明テキストを挿入
                            page.insert_text(
                                point=(x1, y1 + text_height * 0.8),
                                text=text_block.text,
                                fontsize=font_size,
                                render_mode=3,  # 透明テキスト
                                color=(0, 0, 0),
                            )
                        except Exception as e:
                            logger.warning(f"テキストブロック埋め込みエラー (ページ {i + 1}): {e}")

                # メモリを明示的に解放
                del pixmap

            except Exception as e:
                logger.error(f"ページ {i + 1} の処理中にエラーが発生しました: {e}")
                # エラーページの場合は空のページを追加
                page_rect = fitz.Rect(0, 0, 595, 842)  # A4サイズデフォルト
                page = output_doc.new_page(width=page_rect.width, height=page_rect.height)

        # PDFを保存
        logger.info("PDFファイルを保存中...")
        output_doc.save(output_path, garbage=4, deflate=True, clean=True)
        output_doc.close()

        logger.info("メモリ効率的な検索可能PDF作成が完了しました")

    except Exception as e:
        logger.error(f"メモリ効率的PDF作成中にエラーが発生しました: {e}")
        raise
