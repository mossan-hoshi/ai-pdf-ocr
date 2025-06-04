"""
テスト用PDFファイル作成スクリプト

Step 2の機能をテストするためのサンプルPDFファイルを作成します。
"""

from pathlib import Path

import fitz


def create_test_pdf():
    """テスト用のPDFファイルを作成する"""

    # 新しいPDFドキュメントを作成
    doc = fitz.open()

    # ページ1を作成
    page1 = doc.new_page(width=595, height=842)  # A4サイズ

    # テキストを追加
    text1 = """テスト用PDFファイル

これは PDF OCR & Text Overlay Tool のテスト用ファイルです。

ページ1の内容:
• 日本語テキストの認識テスト
• 英語テキストの認識テスト
• 数字の認識テスト: 123456789

This is a test document for PDF OCR processing.
Testing various text elements and layouts."""

    # テキストを挿入
    page1.insert_text((50, 100), text1, fontsize=12, color=(0, 0, 0))

    # ページ2を作成
    page2 = doc.new_page(width=595, height=842)

    # テキストを追加
    text2 = """ページ2の内容

多様なフォントサイズとレイアウトのテスト:

大きなタイトル
中サイズのテキスト
小さなテキスト

表形式のテスト:
項目1    値1
項目2    値2
項目3    値3

特殊文字のテスト: ！@#$%^&*()
日付: 2025年6月3日"""

    # テキストを挿入
    page2.insert_text((50, 100), text2, fontsize=12, color=(0, 0, 0))

    # 大きなタイトルを追加
    page2.insert_text((50, 50), "ページ2のタイトル", fontsize=18, color=(0, 0, 0))

    # 出力ディレクトリを確認
    input_dir = Path("input_pdfs")
    input_dir.mkdir(exist_ok=True)

    # PDFファイルを保存
    output_path = input_dir / "test_sample.pdf"
    doc.save(output_path)
    doc.close()

    print(f"テスト用PDFファイルを作成しました: {output_path}")
    print("ページ数: 2")

    return output_path


if __name__ == "__main__":
    create_test_pdf()
