# -*- coding: utf-8 -*-
"""全局日志器

用法:
    from app.common import logger
    logger.info("...")
    logger.exception("...")  # 在 except 块中使用, 自动带堆栈
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger("lab-agent")
