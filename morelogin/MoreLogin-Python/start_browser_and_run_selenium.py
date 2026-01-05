"""
Description:
Used to start the profile browser, then connected to the browser with webdriver and try google search.
Note: To use this interface, you need to start the MoreLogin client and successfully log in.

Documentation:
https://docs.morelogin.com/l/en/interface-documentation/browser-profile#1_start_browser_profile
"""

import time
import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

import traceback


def main():
    try:
        # browser's order num, you can get it from profile list page: Numerical order
        unique_id = 1
        # browser profile id, please check API-demo: list_browser_profiles.py
        env_id = ""
        debug_url, webdriver = start(env_id, unique_id)
        if debug_url is None or webdriver is None:
            return
        driver = connect(debug_url, webdriver)
        operation(driver)

        # wait 10 second
        time.sleep(10)

        # try close env
        stop(env_id, unique_id)
        print("env closed")
    except:
        error = traceback.format_exc()
        print("run-error: " + error)


# connect webdriver with exist browser
def connect(debug_url, webdriver_path):
    print("connecting to " + webdriver_path)

    opts = Options()
    opts.add_experimental_option("debuggerAddress", debug_url)

    # if you need custom chromedriver, you can use these 2 line codes:
    service = Service(executable_path=webdriver_path)
    driver = webdriver.Chrome(service=service, options=opts)
    return driver


# start a browser profile, and return debug-url
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
        return None, None

    return "127.0.0.1:" + response["data"]["debugPort"], response["data"]["webdriver"]


# open page and operation
def operation(driver):
    # new tab, and open google for search
    driver.switch_to.new_window("tab")
    driver.get("https://www.google.com")

    # wait for page loaded
    WebDriverWait(driver, 10)

    # find input element and fill word
    element = driver.find_element("css selector", '[name="q"]')
    element.send_keys("MoreLogin")
    element.send_keys(Keys.RETURN)
    print("search executed")


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
