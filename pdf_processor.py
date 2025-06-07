import logging
from pathlib import Path
from typing import List

import fitz

from data_structures import PageOCRResult


def get_japanese_font_name() -> str:
    return "japan"


def has_japanese_characters(text: str) -> bool:
    for char in text:
        code = ord(char)
        if 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FAF or 0xFF65 <= code <= 0xFF9F:
            return True
    return False


def select_appropriate_font(text: str) -> str:
    if has_japanese_characters(text):
        return get_japanese_font_name()
    else:
        return "helv"


def adjust_font_size_for_direction(font_size: float, direction: str) -> float:
    return font_size * 0.9 if direction == "vertical" else font_size


def convert_pdf_to_images(pdf_path: Path, dpi: int = 300) -> List[fitz.Pixmap]:
    logger = logging.getLogger(__name__)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

    logger.info(f"PDFファイルを開きます: {pdf_path}")
    logger.info(f"DPI設定: {dpi}")

    try:
        pdf_document = fitz.open(pdf_path)
        logger.info(f"PDFページ数: {pdf_document.page_count}")
        pixmaps = []

        for page_num in range(pdf_document.page_count):
            logger.debug(f"ページ {page_num + 1}/{pdf_document.page_count} を処理中...")
            page = pdf_document[page_num]
            mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            pix = page.get_pixmap(matrix=mat)
            pixmaps.append(pix)
            logger.debug(f"ページ {page_num + 1}: {pix.width}x{pix.height} pixels, {pix.n}チャンネル")

        pdf_document.close()
        logger.info(f"PDF変換完了: {len(pixmaps)} ページ")
        return pixmaps

    except Exception as e:
        logger.error(f"PDF変換エラー: {e}")
        raise


def convert_single_page_to_image(pdf_path: Path, page_number: int, dpi: int = 300) -> fitz.Pixmap:
    logger = logging.getLogger(__name__)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

    try:
        pdf_document = fitz.open(pdf_path)
        if page_number < 0 or page_number >= pdf_document.page_count:
            raise ValueError(f"無効なページ番号: {page_number} (総ページ数: {pdf_document.page_count})")

        page = pdf_document[page_number]
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat)
        pdf_document.close()

        logger.debug(f"ページ {page_number + 1}: {pix.width}x{pix.height} pixels")
        return pix

    except Exception as e:
        logger.error(f"ページ {page_number + 1} の変換エラー: {e}")
        raise


def get_pdf_info(pdf_path: Path) -> dict:
    logger = logging.getLogger(__name__)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")

    try:
        pdf_document = fitz.open(pdf_path)
        info = {
            "page_count": pdf_document.page_count,
            "is_encrypted": pdf_document.is_encrypted,
            "metadata": pdf_document.metadata,
            "page_sizes": [],
        }

        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            info["page_sizes"].append({"page": page_num + 1, "width": page.rect.width, "height": page.rect.height})

        pdf_document.close()
        logger.info(f"PDF情報取得完了: {info['page_count']} ページ")
        return info

    except Exception as e:
        logger.error(f"PDF情報取得エラー: {e}")
        raise


def create_searchable_pdf_page(pixmap: fitz.Pixmap, ocr_result: PageOCRResult, dpi: int = 300) -> fitz.Document:
    logger = logging.getLogger(__name__)
    try:
        doc = fitz.open()
        logger.info(f"ページ {ocr_result.page_number}: Pixmapサイズ {pixmap.width}x{pixmap.height} px")
        logger.info(
            f"ページ {ocr_result.page_number}: OCR結果サイズ {ocr_result.page_width}x{ocr_result.page_height} px"
        )

        pdf_width = pixmap.width * 72.0 / dpi
        pdf_height = pixmap.height * 72.0 / dpi
        logger.info(f"ページ {ocr_result.page_number}: PDFサイズ {pdf_width:.1f}x{pdf_height:.1f} points")

        page = doc.new_page(width=pdf_width, height=pdf_height)
        page.insert_image(page.rect, pixmap=pixmap)

        if ocr_result.text_blocks:
            logger.debug(
                f"ページ {ocr_result.page_number}: {len(ocr_result.text_blocks)}個のテキストブロックを処理中..."
            )

            x_scale = pdf_width / ocr_result.page_width
            y_scale = pdf_height / ocr_result.page_height
            logger.debug(f"座標変換スケール: x={x_scale:.3f}, y={y_scale:.3f}")

            for i, text_block in enumerate(ocr_result.text_blocks):
                try:
                    x0, y0, x1, y1 = (
                        text_block.bbox.x0 * x_scale,
                        text_block.bbox.y0 * y_scale,
                        text_block.bbox.x1 * x_scale,
                        text_block.bbox.y1 * y_scale,
                    )
                    text_width, text_height = x1 - x0, y1 - y0

                    if text_width < 1 or text_height < 1:
                        logger.debug(f"テキストブロック {i + 1}: サイズが小さすぎるためスキップ")
                        continue

                    font_size = min(text_height * 0.8, 12)
                    font_size = max(font_size, 6)
                    font_size = adjust_font_size_for_direction(font_size, text_block.direction)

                    fontname = select_appropriate_font(text_block.text)
                    logger.debug(
                        f"テキストブロック {i + 1}: フォント='{fontname}', サイズ={font_size:.1f}, 方向={text_block.direction}"
                    )

                    text_y = y0 + font_size
                    page.insert_text(
                        (x0, text_y),
                        text_block.text,
                        fontsize=font_size,
                        fontname=fontname,
                        color=(1, 1, 1),
                        render_mode=3,
                    )

                    # 詳細なデバッグ情報
                    logger.debug(
                        f"埋め込み完了 {i+1}/{len(ocr_result.text_blocks)}: '{text_block.text[:50]}...' at ({x0:.1f},{y0:.1f}) font={fontname} size={font_size:.1f}"
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
    logger = logging.getLogger(__name__)
    if len(pixmaps) != len(ocr_results):
        raise ValueError(f"画像ページ数 ({len(pixmaps)}) とOCR結果ページ数 ({len(ocr_results)}) が一致しません")

    logger.info(f"検索可能なPDF作成を開始: {len(pixmaps)} ページ")

    try:
        final_doc = fitz.open()

        for i, (pixmap, ocr_result) in enumerate(zip(pixmaps, ocr_results)):
            logger.info(f"ページ {i + 1}/{len(pixmaps)} を処理中...")

            if not ocr_result.success:
                logger.warning(f"ページ {i + 1}: OCR失敗のため画像のみでページ作成")
                empty_result = PageOCRResult(
                    page_number=i + 1,
                    text_blocks=[],
                    page_width=float(pixmap.width),
                    page_height=float(pixmap.height),
                    success=True,
                    error=None,
                    processing_time=0.0,
                )
                page_doc = create_searchable_pdf_page(pixmap, empty_result, dpi)
            else:
                page_doc = create_searchable_pdf_page(pixmap, ocr_result, dpi)

            final_doc.insert_pdf(page_doc)
            page_doc.close()

        logger.info(f"PDFファイルを保存中: {output_path}")
        final_doc.save(output_path, garbage=4, deflate=True, clean=True)
        final_doc.close()

        logger.info(f"検索可能なPDF作成完了: {output_path}")
        logger.info(f"ファイルサイズ: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    except Exception as e:
        logger.error(f"検索可能なPDF作成中にエラーが発生しました: {e}")
        raise


def embed_ocr_text_blocks(page: fitz.Page, text_blocks: List[dict], x_scale: float, y_scale: float) -> int:
    logger = logging.getLogger(__name__)
    embedded_count = 0

    for i, block in enumerate(text_blocks):
        try:
            text = block.get("text", "").strip()
            if not text:
                continue

            bbox = block.get("bbox", [0, 0, 0, 0])
            x0, y0, x1, y1 = bbox[0] * x_scale, bbox[1] * y_scale, bbox[2] * x_scale, bbox[3] * y_scale

            text_width, text_height = x1 - x0, y1 - y0
            if text_width < 1 or text_height < 1:
                continue

            direction = block.get("direction", "horizontal")
            font_size = max(min(text_height * 0.8, 12), 6)
            font_size = adjust_font_size_for_direction(font_size, direction)
            fontname = select_appropriate_font(text)

            text_y = y0 + font_size
            page.insert_text((x0, text_y), text, fontsize=font_size, fontname=fontname, color=(1, 1, 1), render_mode=3)

            embedded_count += 1
            logger.debug(f"テキスト埋め込み {i + 1}: '{text[:20]}...' (フォント: {fontname})")

        except Exception as e:
            logger.warning(f"テキストブロック {i + 1} の埋め込みに失敗: {e}")
            continue

    return embedded_count


def create_memory_efficient_searchable_pdf(
    input_pdf_path: Path, ocr_results: List[PageOCRResult], output_path: Path, dpi: int = 300
) -> None:
    logger = logging.getLogger(__name__)
    logger.info(f"メモリ効率的な検索可能PDF作成を開始: {input_pdf_path}")

    try:
        final_doc = fitz.open()

        for page_result in ocr_results:
            logger.info(f"ページ {page_result.page_number} を処理中...")

            pixmap = convert_single_page_to_image(input_pdf_path, page_result.page_number - 1, dpi)

            if page_result.success and page_result.text_blocks:
                page_doc = create_searchable_pdf_page(pixmap, page_result, dpi)
            else:
                logger.warning(f"ページ {page_result.page_number}: OCR失敗のため画像のみでページ作成")
                empty_result = PageOCRResult(
                    page_number=page_result.page_number,
                    text_blocks=[],
                    page_width=float(pixmap.width),
                    page_height=float(pixmap.height),
                    success=True,
                    error=None,
                    processing_time=0.0,
                )
                page_doc = create_searchable_pdf_page(pixmap, empty_result, dpi)

            final_doc.insert_pdf(page_doc)
            page_doc.close()
            del pixmap

        logger.info(f"PDFファイルを保存中: {output_path}")
        final_doc.save(output_path, garbage=4, deflate=True, clean=True)
        final_doc.close()

        logger.info(f"メモリ効率的な検索可能PDF作成完了: {output_path}")
        logger.info(f"ファイルサイズ: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    except Exception as e:
        logger.error(f"メモリ効率的な検索可能PDF作成中にエラーが発生しました: {e}")
        raise
