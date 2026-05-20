from loguru import logger


def create_engine(config):
    mode = getattr(config, 'mode', 'adb') if config else 'adb'

    if mode == "browser":
        from reelax.core.browser import BrowserSession
        logger.info("Engine mode: Browser (Playwright)")
        return BrowserSession(config)

    from reelax.core.scroller import ScrollEngine
    logger.info("Engine mode: Phone (ADB)")
    return ScrollEngine(config)
