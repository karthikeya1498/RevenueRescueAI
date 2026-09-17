"""Capture the five-minute RevenueRescue AI dashboard walkthrough."""

from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/tmp/revenuerescue-video-python")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/chromium")
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=str(OUTPUT_DIR),
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.goto("http://127.0.0.1:5173", wait_until="networkidle")
    page.wait_for_timeout(20_000)
    page.get_by_role("button", name="Evaluation lab").click()
    page.wait_for_timeout(35_000)
    page.get_by_role("button", name="Agent traces").click()
    page.wait_for_timeout(30_000)
    page.get_by_role("button", name="Asteria Living").click()
    page.wait_for_timeout(45_000)
    page.get_by_role("button", name="×").click()
    page.get_by_role("button", name="Command center").click()
    page.wait_for_timeout(45_000)
    page.get_by_role("button", name="Recovery queue").click()
    page.wait_for_timeout(30_000)
    page.get_by_role("button", name="Northstar Labs").click()
    page.wait_for_timeout(95_000)
    context.close()
    browser.close()

print(OUTPUT_DIR)
