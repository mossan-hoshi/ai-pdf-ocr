"""
PDF OCR & Text Overlay Tool

このプログラムは、PDFファイルを受け取り、AI-OCR「yomitoku」を用いて
各ページの文字認識を行い、検索可能なPDFを生成します。
"""

import argparse
import logging
import sys
from pathlib import Path

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

        # TODO: Step 3以降の処理を実装（OCR処理とテキスト埋め込み）
        logger.info("TODO: OCR処理とテキスト埋め込み機能の実装が必要です")

        logger.info("処理が完了しました")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
