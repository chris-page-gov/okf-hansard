"""Check the rendered contributor tour in Chromium without live dependencies."""

from pathlib import Path
import shutil
import tempfile

from playwright.sync_api import expect, sync_playwright

from build_pages import ROOT, stage_guides


def main():
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
        site = Path(folder)
        stage_guides(site)
        shutil.copyfile(ROOT / "docs/pages/site.css", site / "site.css")
        browser = playwright.chromium.launch()
        try:
            for width in (390, 1440):
                page = browser.new_page(viewport={"width": width, "height": 844})
                page.goto((site / "contributor-tour.html").as_uri())
                expect(page.get_by_role("heading", name="Contributor tour", level=1)).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), width
                page.keyboard.press("Tab")
                page.keyboard.press("Tab")
                phone = page.get_by_role("link", name="Phone Voice demo", exact=True)
                expect(phone).to_be_focused()
                expect(phone).to_have_css("outline-style", "solid")
                expect(phone).to_have_attribute("href", "november/ask.html")
                source = page.get_by_role("link", name="Read the official Lords Report stage debate")
                official = ("https://hansard.parliament.uk/Lords/2026-11-18/debates/"
                            "5EE3BF1A-449E-4D6D-A0CE-F725CE734996/RailwaysBill")
                expect(source).to_be_visible()
                expect(source).to_have_attribute("href", official)
                page.route(official, lambda route: route.fulfill(body="Official source route fixture"))
                source.focus()
                page.keyboard.press("Enter")
                page.wait_for_url(official)
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
