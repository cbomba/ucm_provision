from wxcadm import Webex

class WebexClient:

    def __init__(self, access_token: str):
        self.api = Webex(access_token=access_token)

    def create_location(self, name: str, address: dict):
        return self.api.locations.create(
            name=name,
            address=address
        )

    def list_locations(self):
        return self.api.locations.list()

    def create_calling_location(self, location_id):
        return self.api.telephony.locations.enable(location_id)