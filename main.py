"""
PDF OCR & Text Overlay Tool

このプログラムは、PDFファイルを受け取り、AI-OCR「yomitoku」を用いて
各ページの文字認識を行い、検索可能なPDFを生成します。
"""

import argparse
import logging
import sys
from pathlib import Path

from data_structures import DocumentOCRResult, save_ocr_results
from ocr_processor import OCRProcessor, parse_ocr_results
from pdf_processor import convert_pdf_to_images, get_pdf_info


def setup_logging(verbose: bool = False) -> None:
    """ロギング設定を初期化する"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_arguments() -> argparse.Namespace:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="PDF OCR & Text Overlay Tool - PDFファイルにOCRテキストを埋め込んで検索可能にします",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s input_pdfs/sample.pdf -o output_pdfs
  %(prog)s /path/to/document.pdf --output_dir /path/to/output --verbose
        """,
    )

    parser.add_argument("input_pdf", type=str, help="処理する入力PDFファイルのパス")

    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="output_pdfs",
        help="出力PDFファイルを保存するディレクトリ（デフォルト: output_pdfs）",
    )

    parser.add_argument("--dpi", type=int, default=300, help="PDF画像化時のDPI設定（デフォルト: 300）")

    parser.add_argument("-v", "--verbose", action="store_true", help="詳細なログ出力を有効にする")

    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        choices=["cuda", "cpu"],
        help="OCR処理に使用するデバイス（デフォルト: cuda）",
    )

    parser.add_argument(
        "--test-ocr",
        action="store_true",
        help="最初のページのみでOCR機能をテストする",
    )

    return parser.parse_args()


def validate_input_file(input_pdf: str) -> Path:
    """入力PDFファイルの存在と拡張子を検証する"""
    input_path = Path(input_pdf)

    if not input_path.exists():
        raise FileNotFoundError(f"入力PDFファイルが見つかりません: {input_pdf}")

    if not input_path.is_file():
        raise ValueError(f"指定されたパスはファイルではありません: {input_pdf}")

    if input_path.suffix.lower() != ".pdf":
        raise ValueError(f"PDFファイルを指定してください（現在の拡張子: {input_path.suffix}）")

    return input_path


def create_output_dir(output_dir: str) -> Path:
    """出力ディレクトリを作成する"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not output_path.is_dir():
        raise ValueError(f"出力ディレクトリの作成に失敗しました: {output_dir}")

    return output_path


def generate_output_filename(input_path: Path, output_dir: Path) -> Path:
    """出力ファイル名を生成する"""
    base_name = input_path.stem
    output_filename = f"{base_name}_ocr.pdf"
    return output_dir / output_filename


def test_ocr_processing(pixmap, device: str, logger) -> None:
    """OCR機能のテスト実行"""
    try:
        logger.info("OCRProcessorを初期化中...")

        # OCRProcessorを作成（可視化有効でテスト）
        ocr_processor = OCRProcessor(device=device, visualize=True)

        logger.info("OCR処理を実行中...")
        ocr_result = ocr_processor.perform_ocr(pixmap)

        if ocr_result["success"]:
            logger.info("OCR処理が成功しました")

            # OCR結果を解析
            text_blocks = parse_ocr_results(ocr_result["results"])
            logger.info(f"検出されたテキストブロック数: {len(text_blocks)}")

            # 検出されたテキストの詳細をログ出力
            for i, block in enumerate(text_blocks[:5]):  # 最初の5つのブロックのみ
                text_preview = block["text"][:50] + "..." if len(block["text"]) > 50 else block["text"]
                bbox = block["bbox"]
                confidence = block["confidence"]
                logger.info(
                    f"ブロック {i+1}: '{text_preview}' bbox:[{bbox[0]:.0f}, {bbox[1]:.0f}, {bbox[2]:.0f}, {bbox[3]:.0f}] confidence:{confidence:.3f}"
                )

            if len(text_blocks) > 5:
                logger.info(f"... 他 {len(text_blocks) - 5} 個のテキストブロック")

        else:
            logger.error(f"OCR処理が失敗しました: {ocr_result['error']}")

    except Exception as e:
        logger.error(f"OCRテスト中にエラーが発生しました: {e}")


def perform_ocr_on_all_pages(pixmaps, device: str, logger) -> list:
    """全ページのOCR処理を実行"""
    ocr_results = []

    try:
        logger.info("OCRProcessorを初期化中...")

        # OCRProcessorを作成（全ページ処理では可視化を無効化してパフォーマンス重視）
        ocr_processor = OCRProcessor(device=device, visualize=False)

        total_pages = len(pixmaps)

        for i, pixmap in enumerate(pixmaps, 1):
            logger.info(f"ページ {i}/{total_pages} のOCR処理中...")

            ocr_result = ocr_processor.perform_ocr(pixmap)

            if ocr_result["success"]:
                # OCR結果を解析
                text_blocks = parse_ocr_results(ocr_result["results"])
                logger.info(f"ページ {i}: {len(text_blocks)}個のテキストブロックを検出")

                ocr_results.append({"page_number": i, "text_blocks": text_blocks, "success": True, "error": None})
            else:
                logger.warning(f"ページ {i} のOCR処理が失敗しました: {ocr_result['error']}")
                ocr_results.append(
                    {"page_number": i, "text_blocks": [], "success": False, "error": ocr_result["error"]}
                )

    except Exception as e:
        logger.error(f"OCR処理中にエラーが発生しました: {e}")
        raise

    return ocr_results


def perform_structured_ocr(pixmaps, device: str, input_file: Path, dpi: int, logger) -> DocumentOCRResult:
    """構造化されたOCR処理を実行"""
    try:
        logger.info("構造化OCRProcessorを初期化中...")

        # OCRProcessorを作成
        ocr_processor = OCRProcessor(device=device, visualize=False)

        # 文書全体のOCR処理を実行
        document_result = ocr_processor.process_document(pixmaps, input_file, dpi)

        # 結果の詳細をログ出力
        logger.info(f"OCR処理完了 - 成功: {document_result.successful_pages}/{document_result.total_pages}ページ")
        logger.info(f"総テキストブロック数: {document_result.total_text_blocks}")
        logger.info(f"総処理時間: {document_result.total_processing_time:.2f}秒")

        # 各ページの詳細をログ出力
        for page in document_result.pages:
            if page.success:
                logger.info(
                    f"ページ {page.page_number}: {page.text_count}ブロック, "
                    f"平均信頼度: {page.average_confidence:.3f}"
                )
            else:
                logger.warning(f"ページ {page.page_number}: エラー - {page.error}")

        return document_result

    except Exception as e:
        logger.error(f"構造化OCR処理中にエラーが発生しました: {e}")
        raise


def main() -> None:
    """メイン処理"""
    try:
        # 引数の解析
        args = parse_arguments()

        # ロギング設定
        setup_logging(args.verbose)
        logger = logging.getLogger(__name__)

        logger.info("PDF OCR & Text Overlay Tool を開始します")
        logger.info(f"入力PDFファイル: {args.input_pdf}")
        logger.info(f"出力ディレクトリ: {args.output_dir}")
        logger.info(f"DPI設定: {args.dpi}")

        # 入力ファイルの検証
        input_path = validate_input_file(args.input_pdf)
        logger.info(f"入力PDFファイルを確認しました: {input_path}")

        # 出力ディレクトリの作成
        output_dir = create_output_dir(args.output_dir)
        logger.info(f"出力ディレクトリを準備しました: {output_dir}")

        # 出力ファイル名の生成
        output_path = generate_output_filename(input_path, output_dir)
        logger.info(f"出力ファイル: {output_path}")

        # Step 2: PDFファイルの情報を取得
        logger.info("PDFファイルの情報を取得中...")
        pdf_info = get_pdf_info(input_path)
        logger.info(f"PDFページ数: {pdf_info['page_count']}")
        logger.info(f"暗号化: {'はい' if pdf_info['is_encrypted'] else 'いいえ'}")

        # Step 2: PDFを画像に変換
        logger.info("PDFをページごとに画像に変換中...")
        pixmaps = convert_pdf_to_images(input_path, args.dpi)

        logger.info(f"画像変換が完了しました。変換されたページ数: {len(pixmaps)}")

        # 画像情報をログ出力
        for i, pixmap in enumerate(pixmaps):
            logger.debug(f"ページ {i + 1}: {pixmap.width}x{pixmap.height} pixels")

        # Step 3: OCR処理の実行
        if args.test_ocr:
            logger.info("OCRテストモード: 最初のページのみ処理します")
            test_ocr_processing(pixmaps[0], args.device, logger)
        else:
            logger.info("全ページの構造化OCR処理を開始...")

            # 構造化されたOCR処理を実行
            document_result = perform_structured_ocr(pixmaps, args.device, input_path, args.dpi, logger)

            # OCR結果をJSONファイルに保存
            ocr_output_path = output_dir / f"{input_path.stem}_ocr_results.json"
            save_ocr_results(document_result, ocr_output_path)
            logger.info(f"OCR結果を保存しました: {ocr_output_path}")

            # 文書の統計情報を表示
            logger.info("文書統計:")
            logger.info(f"  - 総ページ数: {document_result.total_pages}")
            logger.info(f"  - 成功ページ数: {document_result.successful_pages}")
            logger.info(f"  - 総テキストブロック数: {document_result.total_text_blocks}")
            logger.info(f"  - 文書文字数: {len(document_result.document_text)}")

        # TODO: Step 5以降の処理を実装（テキスト埋め込み機能）
        if not args.test_ocr:
            logger.info("TODO: テキスト埋め込み機能の実装が必要です")

        logger.info("処理が完了しました")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
