# PDF OCR & Text Overlay Tool

## 1. 概要 (Overview)

このリポジトリは、PDFファイルを受け取り、AI-OCR「[yomitoku](https://github.com/kotaro-kinoshita/yomitoku)」を用いて各ページの文字認識を行います。その後、認識したテキストとその位置情報を、元のPDF画像上に透明なテキストレイヤーとして正確に埋め込み、検索可能なPDF（Transparent/Searchable PDF）を生成するためのPythonプログラムです。

GitHub Copilotと連携してステップバイステップで開発を進めることを想定し、詳細な仕様と開発手順をTODOリストとして記載しています。

## 2. 主な機能 (Features)

- **入力**: 1つのPDFファイル
- **処理**:
    1.  PDFの各ページを画像に変換します。
    2.  変換された各画像に対し、`yomitoku` を用いて高度なOCR（レイアウト解析を含む）を実行します。
    3.  元のページ画像を背景として新しいPDFを作成します。
    4.  OCR結果（テキストとバウンディングボックス座標）を、背景画像上の正確な位置に透明なテキストとして埋め込みます。
- **出力**: OCRテキストが埋め込まれ、テキスト選択や検索が可能になった新しいPDFファイル。

## 3. 技術スタック (Tech Stack)

| 目的            | ライブラリ       | 選定理由                                                                                                                                                             |
| :-------------- | :--------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OCRエンジン** | `yomitoku`       | 高度な日本語レイアウト解析機能を持つAI-OCRであり、本プロジェクトの要件に適しているため。                                                                             |
| **PDF操作**     | `PyMuPDF (fitz)` | 外部依存が少なく高速。PDFの画像化、画像とテキストの合成、座標指定による精密なテキスト描画、透明度設定など、本プロジェクトで必要な機能を網羅しているため。            |
| **PDF画像化**   | `PyMuPDF (fitz)` | `pdf2image`も有力候補ですが、`PyMuPDF`は後続のPDF作成処理とライブラリを統一でき、Popplerのような外部プログラムへの依存がないため、環境構築がよりシンプルになります。 |

## 4. 環境構築 (Setup)

このプロジェクトは Poetry を使用して依存関係を管理します。`yomitoku` は PyTorch に依存するため、お使いの環境（特にCUDAの有無）に合わせてインストールしてください。

### 前提条件
- Python 3.8 以上
- Poetry ([インストール手順](https://python-poetry.org/docs/#installation))

### インストール手順

1.  **リポジトリのクローン:**
    ```bash
    git clone https://github.com/mossan-hoshi/ai-pdf-ocr.git
    cd ai-pdf-ocr
    ```

2.  **Poetry で依存関係をインストール:**
    
    **CPU版の場合:**
    ```bash
    poetry install --extras cpu
    ```
    
    **CUDA版の場合:**
    ```bash
    poetry install --extras cuda
    ```
    
    *PyTorch のバージョンとCUDAの対応については [PyTorch公式サイト](https://pytorch.org/get-started/locally/) をご確認ください。*

3.  **仮想環境のアクティベート:**
    ```bash
    poetry shell
    ```

4.  **プログラムの実行:**
    ```bash
    poetry run python main.py <path/to/your/input.pdf> --output_dir <path/to/output_directory>
    ```
    
    または、仮想環境をアクティベートした後：
    ```bash
    python main.py <path/to/your/input.pdf> --output_dir <path/to/output_directory>
    ```

## 5. 開発TODOリスト (Development TODOs)

Copilotと共に、以下のステップを順番に実装・テストしていくことを推奨します。

### □ Step 1: プロジェクトの基本構造と設定

- [ ] `main.py` ファイルを作成します。
- [ ] `input_pdfs` フォルダと `output_pdfs` フォルダを作成します。
- [ ] `main.py` に、基本的な引数パーサー (`argparse`) を設定し、入力PDFのパスと出力先フォルダを受け取れるようにします。（例: `python main.py input_pdfs/sample.pdf -o output_pdfs`）
- [ ] ロギング設定 (`logging`) を追加し、処理の進捗がコンソールに表示されるようにします。

### □ Step 2: PDFをページごとに画像へ変換する機能の実装

- [ ] `pdf_processor.py` ファイルを作成します。
- [ ] `PyMuPDF (fitz)` を使用して、指定されたPDFファイルを開き、各ページを画像（PIL.Imageオブジェクトまたはピクセルマップ）に変換する関数 `convert_pdf_to_images` を実装します。
    - **入力**: PDFファイルのパス、DPI (例: 300)
    - **処理**: `fitz.open(pdf_path)` でPDFを開き、ループで各ページ (`page`) を `page.get_pixmap(dpi=DPI)` を使ってピクセルマップに変換します。
    - **出力**: ピクセルマップオブジェクト (`fitz.Pixmap`) のリスト。
- [ ] `main.py` からこの関数を呼び出し、指定したPDFが画像リストに変換されることを確認します。

### □ Step 3: 1枚の画像に対して `yomitoku` でOCRを実行する機能の実装

- [ ] `ocr_processor.py` ファイルを作成します。
- [ ] `yomitoku` の `DocumentAnalyzer` を初期化し、1枚の画像（ピクセルマップまたは画像ファイル）に対してOCRを実行する非同期関数 `perform_ocr` を実装します。
    - **入力**: `fitz.Pixmap` オブジェクト
    - **処理**:
        1. Pixmapを `yomitoku` が扱える形式（例: `numpy.ndarray`）に変換します。
        2. `analyzer.run(img=image_array)` を呼び出してOCR結果 `results` を取得します。
    - **出力**: `results` オブジェクト。
- [ ] `main.py` の中で、Step 2で得られた最初のページの画像に対してこの関数を呼び出し、`results` オブジェクトが取得できることを確認します。（`asyncio.run()` を使って非同期関数を実行します）

### □ Step 4: OCR結果の解析とデータ構造の定義

- [ ] `ocr_processor.py` に、`results` オブジェクトを解析して、テキストとバウンディングボックス（bbox）の情報を抽出する関数 `parse_ocr_results` を実装します。
    - **注意**: `yomitoku` の `results` オブジェクトの正確な構造はドキュメントに明記されていません。`results` オブジェクトの属性を `dir()` や `vars()` で調べるか、CLIでJSON出力した結果を参考に、テキストブロックのリストを抽出する処理を実装する必要があります。
    - **想定される処理**:
        - `results` 内のテキストブロック (`TextBlock`) のような要素をループ処理します。
        - 各ブロックから、テキスト内容 (`text`) とバウンディングボックス (`bbox`) を取得します。`bbox` は `[x0, y0, x1, y1]` 形式のピクセル座標と想定します。
    - **出力**: `[{'text': '...', 'bbox': [x0, y0, x1, y1]}, ...]` のような辞書のリスト。
- [ ] `main.py` でこの関数を呼び出し、OCR結果が期待通りのデータ構造に整形されることを確認します。

### □ Step 5: 新規PDFに画像と透明テキストを埋め込む機能の実装

- [ ] `pdf_processor.py` に、元の画像とOCR結果データを使って、検索可能なPDFページを1ページ作成する関数 `create_searchable_pdf_page` を実装します。
    - **入力**: 元のページ画像 (`fitz.Pixmap`)、OCR結果の辞書リスト (Step 4の出力)、DPI
    - **処理**:
        1.  `fitz.open()` で新しい空のPDFドキュメントを作成します。
        2.  `doc.new_page()` で、元の画像と同じサイズのページを作成します (`width=pix.width`, `height=pix.height`)。
        3.  `page.insert_image(page.rect, pixmap=pix)` で、元のページ画像を背景としてページ全体に挿入します。
        4.  OCR結果の辞書リストをループ処理します。
        5.  各テキスト要素について、ピクセル座標 (`bbox`) をPDFのポイント座標に変換します。
            - スケール係数: `scale = 72.0 / DPI`
            - `x_point = x_pixel * scale`, `y_point = y_pixel * scale`
            - `PyMuPDF` の `Shape` オブジェクト (`page.new_shape()`) を使ってテキストを描画します。`Shape` は左上原点の座標系を持つため、座標変換が直感的です。
            - `rect = fitz.Rect(bbox[0]*scale, bbox[1]*scale, bbox[2]*scale, bbox[3]*scale)`
            - `shape.insert_textbox(rect, item['text'], ...)` のようにテキストボックスを挿入します。
        6.  **テキストを透明にする**: `shape.finish(fill_opacity=0, stroke_opacity=0)` を使って、テキストの塗りも線も透明に設定します。
        7.  `shape.commit()` で変更を適用します。
    - **出力**: 1ページ分のPDFデータ（`fitz.Document` オブジェクトまたはそのバイトデータ）。

### □ Step 6: 全ての処理を統合

- [ ] `main.py` のメイン処理を完成させます。
- [ ] 入力PDFの全ページに対してループ処理を行います。
    1.  `convert_pdf_to_images` で全ページを画像化 (Step 2)。
    2.  各画像に対して `perform_ocr` -> `parse_ocr_results` を実行 (Step 3 & 4)。
    3.  新しい空の `fitz.Document` を作成します。
    4.  各ページの画像とOCR結果を使って `create_searchable_pdf_page` のロジックを適用し、ページを1枚ずつ新しいドキュメントに追加していきます。
    5.  最終的に完成したドキュメントを `doc.save(output_path, garbage=4, deflate=True)` で保存します。
- [ ] エラーハンドリング (`try...except`) を追加し、特定のページでOCRが失敗した場合などの処理を考慮します。

## 6. 使い方 (Usage)

```bash
poetry run python main.py <path/to/your/input.pdf> --output_dir <path/to/output_directory>
```

または、仮想環境をアクティベートした後：
```bash
poetry shell
python main.py <path/to/your/input.pdf> --output_dir <path/to/output_directory>
```

例:
```bash
poetry run python main.py ./input_pdfs/sample.pdf -o ./output_pdfs
```
成功すると、`./output_pdfs` ディレクトリに `sample_ocr.pdf` のような名前で、テキストが埋め込まれたPDFファイルが生成されます。