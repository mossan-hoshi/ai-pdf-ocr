import logging
from typing import List, Tuple

from data_structures import BoundingBox, PageOCRResult, TextBlock


def get_bbox_props(bbox):
    lx, ty, rx, by = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    return lx, ty, rx, by, (lx + rx) / 2, (ty + by) / 2, rx - lx, by - ty


def is_horizontal_overlap(bbox1, bbox2, threshold=0.5):
    lx1, _, rx1, _, _, _, w1, _ = get_bbox_props(bbox1)
    lx2, _, rx2, _, _, _, w2, _ = get_bbox_props(bbox2)
    overlap = max(0, min(rx1, rx2) - max(lx1, lx2))
    return overlap >= w1 * threshold or overlap >= w2 * threshold


def is_vertical_overlap(bbox1, bbox2, threshold=0.5):
    _, ty1, _, by1, _, _, _, h1 = get_bbox_props(bbox1)
    _, ty2, _, by2, _, _, _, h2 = get_bbox_props(bbox2)
    overlap = max(0, min(by1, by2) - max(ty1, ty2))
    return overlap >= h1 * threshold or overlap >= h2 * threshold


def sort_vertical_text_blocks(text_blocks: List[TextBlock]) -> List[TextBlock]:
    logger = logging.getLogger(__name__)
    if not text_blocks:
        return text_blocks

    logger.debug(f"縦書きテキストブロック {len(text_blocks)} 個をソート中...")

    columns = []
    for block in text_blocks:
        added = False
        for column in columns:
            if is_horizontal_overlap(block.bbox, column[0].bbox):
                column.append(block)
                added = True
                break
        if not added:
            columns.append([block])

    logger.debug(f"縦書きテキストで {len(columns)} 列を検出")

    for column in columns:
        column.sort(key=lambda b: get_bbox_props(b.bbox)[1])
    columns.sort(key=lambda col: -get_bbox_props(col[0].bbox)[4])

    result = []
    for column in columns:
        result.extend(column)

    logger.debug(f"縦書きテキストブロックのソート完了: {len(result)} 個")
    return result


def sort_horizontal_text_blocks(text_blocks: List[TextBlock]) -> List[TextBlock]:
    logger = logging.getLogger(__name__)
    if not text_blocks:
        return text_blocks

    logger.debug(f"横書きテキストブロック {len(text_blocks)} 個をソート中...")

    rows = []
    for block in text_blocks:
        added = False
        for row in rows:
            if is_vertical_overlap(block.bbox, row[0].bbox):
                row.append(block)
                added = True
                break
        if not added:
            rows.append([block])

    logger.debug(f"横書きテキストで {len(rows)} 行を検出")

    for row in rows:
        row.sort(key=lambda b: get_bbox_props(b.bbox)[0])
    rows.sort(key=lambda row: get_bbox_props(row[0].bbox)[5])

    result = []
    for row in rows:
        result.extend(row)

    logger.debug(f"横書きテキストブロックのソート完了: {len(result)} 個")
    return result


def calculate_group_bounding_box(text_blocks: List[TextBlock]) -> Tuple[float, float, float, float]:
    if not text_blocks:
        return 0, 0, 0, 0
    min_x = min(block.bbox.x0 for block in text_blocks)
    min_y = min(block.bbox.y0 for block in text_blocks)
    max_x = max(block.bbox.x1 for block in text_blocks)
    max_y = max(block.bbox.y1 for block in text_blocks)
    return min_x, min_y, max_x, max_y


def sort_text_blocks_by_reading_order(page_result: PageOCRResult) -> PageOCRResult:
    logger = logging.getLogger(__name__)

    if not page_result.text_blocks:
        logger.debug("テキストブロックがないため、ソートをスキップします")
        return page_result

    logger.info(
        f"ページ {page_result.page_number}: テキストブロック読み順ソートを開始 ({len(page_result.text_blocks)} 個)"
    )

    merged_text_blocks = merge_overlapping_text_blocks(page_result.text_blocks)

    vertical_blocks = [block for block in merged_text_blocks if block.direction == "vertical"]
    horizontal_blocks = [block for block in merged_text_blocks if block.direction == "horizontal"]

    logger.debug(f"マージ後 - 縦書きブロック: {len(vertical_blocks)} 個, 横書きブロック: {len(horizontal_blocks)} 個")

    sorted_vertical = sort_vertical_text_blocks(vertical_blocks)
    sorted_horizontal = sort_horizontal_text_blocks(horizontal_blocks)

    final_sorted_blocks = []

    if vertical_blocks and horizontal_blocks:
        vertical_bbox = calculate_group_bounding_box(vertical_blocks)
        horizontal_bbox = calculate_group_bounding_box(horizontal_blocks)
        vertical_top, horizontal_top = vertical_bbox[1], horizontal_bbox[1]

        logger.debug(f"縦書きグループ top: {vertical_top:.1f}, 横書きグループ top: {horizontal_top:.1f}")

        if vertical_top <= horizontal_top:
            final_sorted_blocks.extend(sorted_vertical)
            final_sorted_blocks.extend(sorted_horizontal)
            logger.debug("縦書きグループを先に配置")
        else:
            final_sorted_blocks.extend(sorted_horizontal)
            final_sorted_blocks.extend(sorted_vertical)
            logger.debug("横書きグループを先に配置")
    elif vertical_blocks:
        final_sorted_blocks.extend(sorted_vertical)
        logger.debug("縦書きブロックのみを配置")
    elif horizontal_blocks:
        final_sorted_blocks.extend(sorted_horizontal)
        logger.debug("横書きブロックのみを配置")

    for i, block in enumerate(final_sorted_blocks):
        block.block_id = i + 1

    logger.info(f"ページ {page_result.page_number}: テキストブロック読み順ソート完了 ({len(final_sorted_blocks)} 個)")

    return PageOCRResult(
        page_number=page_result.page_number,
        text_blocks=final_sorted_blocks,
        page_width=page_result.page_width,
        page_height=page_result.page_height,
        success=page_result.success,
        error=page_result.error,
        processing_time=page_result.processing_time,
    )


def calculate_overlap_ratio(bbox1, bbox2) -> float:
    lx1, ty1, rx1, by1, _, _, w1, h1 = get_bbox_props(bbox1)
    lx2, ty2, rx2, by2, _, _, w2, h2 = get_bbox_props(bbox2)

    overlap_left, overlap_top = max(lx1, lx2), max(ty1, ty2)
    overlap_right, overlap_bottom = min(rx1, rx2), min(by1, by2)

    if overlap_left >= overlap_right or overlap_top >= overlap_bottom:
        return 0.0

    overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
    area1, area2 = w1 * h1, w2 * h2
    smaller_area = min(area1, area2)

    return overlap_area / smaller_area if smaller_area > 0 else 0.0


def merge_overlapping_text_blocks(text_blocks: List[TextBlock], overlap_threshold: float = 0.5) -> List[TextBlock]:
    logger = logging.getLogger(__name__)

    if len(text_blocks) <= 1:
        return text_blocks

    logger.debug(f"重複テキストブロックのマージを開始: {len(text_blocks)} 個")

    merged_blocks, used_indices = [], set()

    for i, block1 in enumerate(text_blocks):
        if i in used_indices:
            continue

        merge_candidates, merge_indices = [block1], {i}

        for j, block2 in enumerate(text_blocks):
            if j <= i or j in used_indices or block1.direction != block2.direction:
                continue

            overlap_ratio = calculate_overlap_ratio(block1.bbox, block2.bbox)

            if overlap_ratio >= overlap_threshold:
                merge_candidates.append(block2)
                merge_indices.add(j)
                logger.debug(
                    f"ブロック {block1.block_id} と {block2.block_id} をマージ対象に追加 (重複率: {overlap_ratio:.2f})"
                )

        if len(merge_candidates) > 1:
            merged_block = merge_text_blocks(merge_candidates)
            merged_blocks.append(merged_block)
            used_indices.update(merge_indices)
            logger.debug(f"{len(merge_candidates)} 個のブロックをマージして新ブロック {merged_block.block_id} を作成")
        else:
            merged_blocks.append(block1)
            used_indices.add(i)

    logger.debug(f"重複テキストブロックのマージ完了: {len(text_blocks)} → {len(merged_blocks)} 個")
    return merged_blocks


def merge_text_blocks(text_blocks: List[TextBlock]) -> TextBlock:
    if len(text_blocks) == 1:
        return text_blocks[0]

    base_block = max(text_blocks, key=lambda b: b.confidence)

    min_x = min(block.bbox.x0 for block in text_blocks)
    min_y = min(block.bbox.y0 for block in text_blocks)
    max_x = max(block.bbox.x1 for block in text_blocks)
    max_y = max(block.bbox.y1 for block in text_blocks)

    merged_text = max(text_blocks, key=lambda b: len(b.text)).text
    avg_confidence = sum(block.confidence for block in text_blocks) / len(text_blocks)

    return TextBlock(
        text=merged_text,
        bbox=BoundingBox(x0=min_x, y0=min_y, x1=max_x, y1=max_y),
        confidence=avg_confidence,
        direction=base_block.direction,
        block_id=base_block.block_id,
    )


def sort_document_text_blocks(document_result) -> None:
    logger = logging.getLogger(__name__)
    logger.info(f"文書全体のテキストブロック読み順ソートを開始: {len(document_result.pages)} ページ")

    for i, page_result in enumerate(document_result.pages):
        document_result.pages[i] = sort_text_blocks_by_reading_order(page_result)

    logger.info("文書全体のテキストブロック読み順ソート完了")
