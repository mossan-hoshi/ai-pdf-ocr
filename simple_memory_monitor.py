#!/usr/bin/env python3
"""
シンプルなメモリ監視ユーティリティ

標準ライブラリのみを使用したメモリ使用量監視機能です。
"""

import gc
import logging
import tracemalloc
from typing import Optional


class SimpleMemoryMonitor:
    """標準ライブラリのみを使用するシンプルなメモリ監視クラス"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.peak_memory = 0
        try:
            # tracemalloc を開始
            tracemalloc.start()
            self.initial_snapshot = tracemalloc.take_snapshot()
            self.tracemalloc_available = True
        except Exception as e:
            self.logger.warning(f"tracemalloc初期化に失敗しました: {e}")
            self.tracemalloc_available = False
            self.initial_snapshot = None

    def log_memory_usage(self, context: str = ""):
        """メモリ使用量をログ出力（tracemalloc使用）"""
        if not self.tracemalloc_available:
            self.logger.debug(f"メモリ監視 [{context}]: tracemalloc無効")
            return

        try:
            # 現在のスナップショットを取得
            current_snapshot = tracemalloc.take_snapshot()

            # メモリ使用量の統計を取得
            stats = current_snapshot.statistics("lineno")

            # 総メモリ使用量を計算
            total_size = sum(stat.size for stat in stats)
            total_mb = total_size / 1024 / 1024

            # ピークメモリを更新
            if total_mb > self.peak_memory:
                self.peak_memory = total_mb

            self.logger.info(f"メモリ使用量 [{context}]: {total_mb:.1f}MB (ピーク: {self.peak_memory:.1f}MB)")

        except Exception as e:
            self.logger.error(f"メモリ使用量取得エラー: {e}")

    def force_garbage_collection(self):
        """ガベージコレクションを強制実行"""
        before_count = len(gc.get_objects())
        collected = gc.collect()
        after_count = len(gc.get_objects())

        self.logger.debug(
            f"ガベージコレクション実行: {collected}個回収, " f"オブジェクト数 {before_count} -> {after_count}"
        )

    def log_memory_summary(self):
        """メモリ使用量の要約をログ出力"""
        if not self.tracemalloc_available:
            self.logger.info("=== メモリ使用量要約 ===")
            self.logger.info("tracemalloc無効のため詳細情報なし")
            return

        try:
            current_snapshot = tracemalloc.take_snapshot()

            # 最も多くメモリを使用しているファイルのトップ10
            top_stats = current_snapshot.statistics("filename")[:10]

            self.logger.info("=== メモリ使用量要約 ===")
            self.logger.info(f"ピークメモリ使用量: {self.peak_memory:.1f}MB")
            self.logger.info("上位メモリ使用ファイル:")

            for index, stat in enumerate(top_stats, 1):
                size_mb = stat.size / 1024 / 1024
                self.logger.info(f"{index:2d}. {stat.traceback.format()[-1].strip()} - {size_mb:.1f}MB")

        except Exception as e:
            self.logger.error(f"メモリ要約取得エラー: {e}")

    def get_memory_diff(self):
        """初期状態からのメモリ使用量の差分を取得"""
        if not self.tracemalloc_available or self.initial_snapshot is None:
            return 0

        try:
            current_snapshot = tracemalloc.take_snapshot()
            top_stats = current_snapshot.compare_to(self.initial_snapshot, "lineno")

            # 差分の統計
            total_diff = sum(stat.size_diff for stat in top_stats)
            diff_mb = total_diff / 1024 / 1024

            return diff_mb
        except Exception:
            return 0

    def __del__(self):
        """デストラクタでtracemalloc停止"""
        if self.tracemalloc_available:
            try:
                tracemalloc.stop()
            except Exception:
                pass


def check_memory_availability(required_mb: int = 500) -> bool:
    """メモリ可用性をチェック（簡易版）"""
    try:
        # /proc/meminfoを読み取り（Linuxのみ）
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()

        mem_available = None
        for line in lines:
            if line.startswith("MemAvailable:"):
                # KB単位で取得してMBに変換
                mem_available = int(line.split()[1]) / 1024
                break

        if mem_available is None:
            return True  # 不明な場合は処理を継続

        return mem_available > required_mb

    except Exception:
        return True  # エラーの場合は処理を継続


def get_optimal_batch_size(total_pages: int) -> int:
    """最適なバッチサイズを計算（簡易版）"""
    if total_pages <= 10:
        return 1
    elif total_pages <= 50:
        return 2
    elif total_pages <= 100:
        return 3
    else:
        return 5  # 大容量PDFは小さなバッチサイズで
