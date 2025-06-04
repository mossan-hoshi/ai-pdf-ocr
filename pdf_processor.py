"""
PDF処理モジュール

PDFファイルの読み込み、ページごとの画像変換、
検索可能なPDF生成機能を提供します。
"""

import logging
from pathlib import Path
from typing import List

import fitz  # PyMuPDF


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
