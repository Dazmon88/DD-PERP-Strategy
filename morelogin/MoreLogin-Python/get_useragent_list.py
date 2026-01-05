"""
Description:
Queries the available browser kernel versions.

Note: MoreLogin version number cannot be lower than 2.32

Documentation:
https://docs.morelogin.com/l/en/interface-documentation/browser-profile#9_get_a_list_of_browser_kernel_versions
"""

import traceback
import requests


def main():
    try:
        data = kernel_list()
        if data is not None and len(data) > 0:
            for ua in data:
                if ua["browserType"] == 1:
                    print("chromium version support:", ua["versions"])
                if ua["browserType"] == 2:
                    print("firefox version support:", ua["versions"])
        else:
            print("no ua data found, please call service")

    except:
        error = traceback.format_exc()
        print(f"run-error: {error}")


def kernel_list():
    response = requests.get(
        "http://127.0.0.1:40000/api/env/advanced/ua/versions"
    ).json()

    if response["code"] != 0:
        print(
            f"code: {response['code']}, error: {response['msg']}, request_id: {response['requestId']}"
        )
        return
    return response["data"]


if __name__ == "__main__":
    main()
