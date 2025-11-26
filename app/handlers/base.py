from playwright.async_api import Page

class BaseHandler:
    def can_handle(self, page: Page) -> bool:
        raise NotImplementedError

    async def solve(self, page: Page, **kwargs):
        raise NotImplementedError
