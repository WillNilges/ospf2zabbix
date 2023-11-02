import os
import requests


class O2ZExplorer:
    def __init__(self):
        self.url = os.getenv("P2Z_OSPF_API_URL", default="")
        self.enrolling_link_floor = int(os.getenv("P2Z_LINK_FLOOR", default=10))

    def extract_routes_count(self, data):
        routes_count = {}

        areas = data.get("areas", {})
        for area_key, area_value in areas.items():
            routers = area_value.get("routers", {})
            for router_ip, router_info in routers.items():
                links = router_info.get("links", {})
                if links.get("router") == None:
                    continue
                link_ct = len(links.get("router"))
                routes_count[router_ip] = link_ct
        return routes_count

    def fetch_ospf_json(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            return None
