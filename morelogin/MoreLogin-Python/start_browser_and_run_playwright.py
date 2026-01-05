"""
Description:
Used to start the profile browser, then connected to the browser with cdp and try google search.

Note: To use this interface, you need to start the MoreLogin client and successfully log in.
MoreLogin version number cannot be lower than 2.32

Documentation:
https://docs.morelogin.com/l/en/interface-documentation/browser-profile#1_start_browser_profile
"""

import time
from playwright.sync_api import sync_playwright, Playwright
import traceback

import requests


def main():
    with sync_playwright() as playwright:
        run(playwright)


def run(playwright: Playwright):
    try:
        # browser's order num, you can get it from profile list page: Numerical order
        unique_id = 1
        # browser profile id, please check API-demo: list_browser_profiles.py
        env_id = ""
        cdp_url = start(env_id, unique_id)

        if cdp_url is None:
            return

        operation(cdp_url, playwright)

        # wait 10 second
        time.sleep(10)

        # try close env
        stop(env_id, unique_id)
        print("env closed")

    except:
        error = traceback.format_exc()
        print("run-error: " + error)


# start a browser profile, and return cdp-url
# if browser already opened, the browser will auto bring to front
def start(envId, uniqueId):
    # Send the envId(profile ID) or the uniqueId(profile order number).
    # If both are sent, the profile ID takes precedence.
    data = {"envId": envId, "uniqueId": uniqueId}
    response = requests.post("http://localhost:40000/api/env/start", json=data).json()

    if response["code"] != 0:
        print(
            f"code: {response['code']}, error: {response['msg']}, request_id: {response['requestId']}"
        )
        print("please check envId")
        return

    port = response["data"]["debugPort"]
    print("env open result:", response["data"])
    return "http://127.0.0.1:" + port


# open page and operation
def operation(cdp_url, playwright):
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    ctx = browser.contexts[0]

    # try open page
    page1 = ctx.new_page()
    page1.goto("https://ipinfo.io")

    page2 = ctx.new_page()
    page2.goto("https://www.google.com/")
    print(page2.title)
    page2.fill('[name="q"]', "MoreLogin")
    page2.press('[name="q"]', "Enter")
    # page2.keyboard.press('Enter')
    print("search executed")

    # try close and clear resource
    # page1.close()
    # page2.close()


# close a browser profile
def stop(envId, uniqueId):
    # Send the envId(profile ID) or the uniqueId(profile order number).
    # If both are sent, the profile ID takes precedence.
    data = {"envId": envId, "uniqueId": uniqueId}
    response = requests.post("http://localhost:40000/api/env/close", json=data).json()
    if response["code"] == -1:
        print(
            f"code: {response['code']}, error: {response['msg']}, request_id: {response['requestId']}"
        )
        return False
    return True


if __name__ == "__main__":
    main()
