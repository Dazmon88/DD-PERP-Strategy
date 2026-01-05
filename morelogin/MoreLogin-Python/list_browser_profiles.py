"""
Description:
Queries the added profile information. Users can query only the profile information to which they have access.

Note: MoreLogin version number cannot be lower than 2.32

Documentation:
https://docs.morelogin.com/l/en/interface-documentation/browser-profile#7_get_a_list_of_browser_profiles
"""

import traceback
import requests


def main():
    try:
        data = {
            "pageNo": 1,  # env list page no
            "pageSize": 5,  # number of profiles per page
            "envName": "",  # env name condition for search
            #'groupId': 123,                 # env group condition for search
        }
        response = requests.post(
            "http://localhost:40000/api/env/page", json=data
        ).json()

        if response["code"] != 0:
            print(
                f"code: {response['code']}, error: {response['msg']}, request_id: {response['requestId']}"
            )
            return

        for env in response["data"]["dataList"]:
            print(env["id"] + ": " + env["envName"])
        else:
            print("no profile found, please check your condition")

    except:
        error = traceback.format_exc()
        print(f"run-error: {error}")


if __name__ == "__main__":
    main()
