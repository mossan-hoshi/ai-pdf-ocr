#!/usr/bin/env python3
"""
PDF OCR & Text Overlay Tool (Memory Optimized)

このプログラムは、PDFファイルを受け取り、AI-OCR「yomitoku」を用いて
各ページの文字認識を行い、検索可能なPDFを生成します。
メモリ使用量を最適化したバージョンです。
"""

import argparse
import gc
import logging
import sys
import time
from pathlib import Path

from data_structures import BoundingBox, DocumentOCRResult, PageOCRResult, TextBlock, load_ocr_results, save_ocr_results
from ocr_processor import OCRProcessor, parse_ocr_results
from pdf_processor import convert_single_page_to_image, create_memory_efficient_searchable_pdf, get_pdf_info
from simple_memory_monitor import SimpleMemoryMonitor, check_memory_availability, get_optimal_batch_size


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
        description="PDF OCR & Text Overlay Tool (Memory Optimized) - PDFファイルにOCRテキストを埋め込んで検索可能にします",
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

    parser.add_argument(
        "--ocr-only",
        action="store_true",
        help="OCR処理のみ実行し、検索可能なPDFは作成しない",
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


def perform_memory_efficient_ocr(input_path: Path, device: str, dpi: int, logger) -> DocumentOCRResult:
    """メモリ効率的なOCR処理を実行"""
    memory_monitor = SimpleMemoryMonitor(logger)
    memory_monitor.log_memory_usage("OCR処理開始")

    try:
        logger.info("メモリ効率的OCRProcessorを初期化中...")

        # メモリ可用性をチェック
        if not check_memory_availability(500):  # 500MB以上必要
            logger.warning("利用可能メモリが少ない状態です。処理が遅くなる可能性があります。")

        # OCRProcessorを作成
        ocr_processor = OCRProcessor(device=device, visualize=False)

        # PDFファイルを開いてページ数を取得
        import fitz

        pdf_document = fitz.open(input_path)
        total_pages = pdf_document.page_count
        pdf_document.close()
        del pdf_document

        logger.info(f"総ページ数: {total_pages}")

        # 推奨バッチサイズを計算
        batch_size = get_optimal_batch_size(total_pages)
        logger.info(f"推奨バッチサイズ: {batch_size}ページ")

        # 結果を格納するリスト
        pages_results = []
        total_processing_time = 0

        # ページごとに処理
        for page_num in range(total_pages):
            logger.info(f"ページ {page_num + 1}/{total_pages} を処理中...")

            # 10ページごとにメモリ使用量をログ出力
            if page_num % 10 == 0:
                memory_monitor.log_memory_usage(f"ページ{page_num + 1}")
                memory_monitor.force_garbage_collection()

            pixmap = None
            try:
                # 1ページずつ画像に変換
                pixmap = convert_single_page_to_image(input_path, page_num, dpi)

                # OCR処理
                start_time = time.time()
                ocr_result = ocr_processor.perform_ocr(pixmap)
                processing_time = time.time() - start_time
                total_processing_time += processing_time

                if ocr_result["success"]:
                    # OCR結果を解析
                    text_blocks = parse_ocr_results(ocr_result["results"])

                    # TextBlockリストを作成
                    page_text_blocks = []
                    for block_data in text_blocks:
                        bbox = BoundingBox(
                            x0=block_data["bbox"][0],
                            y0=block_data["bbox"][1],
                            x1=block_data["bbox"][2],
                            y1=block_data["bbox"][3],
                        )
                        text_block = TextBlock(
                            text=block_data["text"],
                            bbox=bbox,
                            confidence=block_data["confidence"],
                            direction=block_data.get("direction", "horizontal"),
                            block_id=len(page_text_blocks) + 1,
                        )
                        page_text_blocks.append(text_block)

                    page_result = PageOCRResult(
                        page_number=page_num + 1,
                        text_blocks=page_text_blocks,
                        page_width=pixmap.width,
                        page_height=pixmap.height,
                        success=True,
                        processing_time=processing_time,
                    )

                    logger.info(f"ページ {page_num + 1}: {len(text_blocks)}個のテキストブロックを検出")
                else:
                    # 失敗した場合
                    page_result = PageOCRResult(
                        page_number=page_num + 1,
                        text_blocks=[],
                        page_width=pixmap.width if pixmap else 0,
                        page_height=pixmap.height if pixmap else 0,
                        success=False,
                        error=ocr_result["error"],
                        processing_time=processing_time,
                    )
                    logger.warning(f"ページ {page_num + 1} のOCR処理が失敗しました: {ocr_result['error']}")

                pages_results.append(page_result)

            except Exception as e:
                logger.error(f"ページ {page_num + 1} の処理中にエラーが発生しました: {e}")
                # エラーページの結果を作成
                error_page = PageOCRResult(
                    page_number=page_num + 1,
                    text_blocks=[],
                    page_width=0,
                    page_height=0,
                    success=False,
                    error=str(e),
                    processing_time=0,
                )
                pages_results.append(error_page)
            finally:
                # メモリを明示的に解放
                if pixmap:
                    del pixmap
                gc.collect()

        # OCRProcessorのメモリを解放
        ocr_processor.clear_memory()
        del ocr_processor
        gc.collect()

        # DocumentOCRResultを作成
        document_result = DocumentOCRResult(
            input_file=input_path,
            pages=pages_results,
            total_processing_time=total_processing_time,
            device_used=device,
            dpi=dpi,
        )

        logger.info(f"OCR処理完了 - 成功: {document_result.successful_pages}/{document_result.total_pages}ページ")
        logger.info(f"総処理時間: {total_processing_time:.2f}秒")

        memory_monitor.log_memory_usage("OCR処理完了")
        memory_monitor.log_memory_summary()

        return document_result

    except Exception as e:
        logger.error(f"メモリ効率的OCR処理中にエラーが発生しました: {e}")
        memory_monitor.log_memory_usage("OCR処理エラー")
        raise


def main() -> None:
    """メイン処理"""
    memory_monitor = None
    try:
        # 引数の解析
        args = parse_arguments()

        # ロギング設定
        setup_logging(args.verbose)
        logger = logging.getLogger(__name__)

        # メモリ監視を開始
        memory_monitor = SimpleMemoryMonitor(logger)
        memory_monitor.log_memory_usage("プログラム開始")

        logger.info("PDF OCR & Text Overlay Tool (Memory Optimized) を開始します")
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

        # 大容量PDFの警告
        if pdf_info["page_count"] > 100:
            logger.warning(f"大容量PDF ({pdf_info['page_count']}ページ) を処理します。メモリ使用量にご注意ください。")

        memory_monitor.log_memory_usage("PDF情報取得完了")

        # OCR結果の読み込み試行
        ocr_output_path = output_dir / f"{input_path.stem}_ocr_results.json"
        document_result = None

        if ocr_output_path.exists():
            logger.info(f"既存のOCR結果を読み込んでいます: {ocr_output_path}")
            try:
                document_result = load_ocr_results(ocr_output_path)
                logger.info(f"OCR結果を読み込みました: {document_result.total_pages}ページ")
                memory_monitor.log_memory_usage("OCR結果読み込み完了")
            except Exception as e:
                logger.warning(f"OCR結果の読み込みに失敗しました: {e}")
                document_result = None

        # Step 3: OCR処理の実行
        if args.test_ocr:
            logger.info("OCRテストモード: 最初のページのみ処理します")
            # テスト用に1ページのみ処理
            pixmap = convert_single_page_to_image(input_path, 0, args.dpi)
            test_ocr_processing(pixmap, args.device, logger)
            # Pixmapの明示的解放
            del pixmap
            gc.collect()
        elif document_result is None:
            logger.info("全ページの構造化OCR処理を開始...")

            # メモリ効率的な構造化OCR処理を実行
            document_result = perform_memory_efficient_ocr(input_path, args.device, args.dpi, logger)

            # OCR結果をJSONファイルに保存
            save_ocr_results(document_result, ocr_output_path)
            logger.info(f"OCR結果を保存しました: {ocr_output_path}")

            # 文書の統計情報を表示
            logger.info("文書統計:")
            logger.info(f"  - 総ページ数: {document_result.total_pages}")
            logger.info(f"  - 成功ページ数: {document_result.successful_pages}")
            logger.info(f"  - 総テキストブロック数: {document_result.total_text_blocks}")
            logger.info(f"  - 文書文字数: {len(document_result.document_text)}")

            memory_monitor.log_memory_usage("OCR処理完了")
        else:
            logger.info("既存のOCR結果を使用します")

        # Step 5: 検索可能なPDF作成（メモリ効率化）
        if not args.test_ocr and not args.ocr_only and document_result is not None:
            logger.info("Step 5: 検索可能なPDFファイルを作成中...")

            try:
                # メモリ効率的な検索可能PDF作成
                create_memory_efficient_searchable_pdf(input_path, document_result.pages, output_path, args.dpi)
                logger.info(f"検索可能なPDFファイルが作成されました: {output_path}")

                # ファイルサイズを確認
                file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                logger.info(f"出力ファイルサイズ: {file_size:.2f} MB")

                memory_monitor.log_memory_usage("PDF作成完了")

            except Exception as e:
                logger.error(f"検索可能なPDF作成中にエラーが発生しました: {e}")
                raise
        elif args.ocr_only:
            logger.info("OCRのみモード: 検索可能なPDF作成をスキップしました")
        elif document_result is None:
            logger.warning("OCR結果がないため、検索可能なPDF作成をスキップしました")

        logger.info("処理が完了しました")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"エラーが発生しました: {e}")
        if memory_monitor:
            memory_monitor.log_memory_usage("エラー発生時")
        sys.exit(1)
    finally:
        # 最終的なメモリ使用量をログ出力
        if memory_monitor:
            memory_monitor.log_memory_summary()


if __name__ == "__main__":
    main()
