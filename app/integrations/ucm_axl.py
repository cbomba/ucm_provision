import requests
from requests.auth import HTTPBasicAuth
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class UcmAxlClient:
    def __init__(self, base_url, username, password, verify_tls=False, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = bool(verify_tls) is True
        self.timeout = timeout

        self.axl_url = f"{self.base_url}/"
        self.axl_version = "14.0" # Adjust as needed for your CUCM version
        self.headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "SOAPAction": f"CUCM:DB ver={self.axl_version}"
        }


    def _post(self, body: str, soap_action: str | None = None):
        headers = self.headers.copy()
        if soap_action:
            headers["SOAPAction"] = soap_action

        print("\n====== AXL RAW REQUEST ======")
        print("URL:", self.axl_url)
        print("SOAPAction:", headers.get("SOAPAction"))
        print("Content-Type:", headers.get("Content-Type"))
        print("AUTH:", f"{self.username}:{'*' * len(self.password)}")
        print("BODY:\n", body.strip())
        print("====== END REQUEST ======\n")


        r = requests.post(
            self.axl_url,
            data=body,
            headers=headers,
            auth=HTTPBasicAuth(self.username, self.password),
            verify=False,
            timeout=self.timeout,
        )
        
        # # 🔍 RESPONSE LOGGING (THIS IS THE KEY PART)
        # print("====== AXL RAW RESPONSE ======")
        # print("HTTP:", r.status_code)
        # print("Content-Type:", r.headers.get("Content-Type"))
        # print("BODY (truncated):\n", r.text[:1000])
        # print("====== END RESPONSE ======\n")

        return r

    def _soap(self, inner: str) -> str:
        return f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                          xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
          <soapenv:Body>
            {inner}
          </soapenv:Body>
        </soapenv:Envelope>
        """


    def remove_op(self, op: str, **kwargs) -> None:
        args_xml = "".join(
            f"<{k}>{escape(str(v))}</{k}>"
            for k, v in kwargs.items()
            if v is not None
        )

        body = self._soap(f"<ns:{op}>{args_xml}</ns:{op}>")

        r = self._post(
            body,
            soap_action=f"CUCM:DB ver={self.axl_version}"
        )

        if r.status_code != 200:
            raise RuntimeError(f"{op} failed: {r.text[:400]}")


    def get_version(self):
        body = f"""
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                            xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
                <soapenv:Header/>
                <soapenv:Body>
                    <ns:getCCMVersion/>
                </soapenv:Body>
            </soapenv:Envelope>
            """

        r = self._post(body)

        if r.status_code != 200:
            raise Exception(f"AXL HTTP {r.status_code}: {r.text[:300]}")

        return r.text
    
    
    def get_region(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getRegion>
                    <name>{name}</name>
                </ns:getRegion>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<region>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_region failed unexpectedly")
    
    
    def add_region(self, name: str, description: str | None = None) -> None:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addRegion>
            <region>
                <name>{name}</name>
            </region>
            </ns:addRegion>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_region failed: {r.text[:400]}")


    def get_location(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getLocation>
                    <name>{name}</name>
                </ns:getLocation>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<location>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_location failed unexpectedly")
    
    
    def add_location(self, name: str, description: str | None = None) -> None:
        desc_xml = f"<description>{description}</description>" if description else ""

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addLocation>
            <location>
                <name>{name}</name>
                <withinAudioBandwidth>0</withinAudioBandwidth>
                <withinVideoBandwidth>0</withinVideoBandwidth>
                <withinImmersiveKbits>0</withinImmersiveKbits>
                <betweenLocations>
                    <betweenLocation>
                        <locationName>Hub_None</locationName>
                        <weight>50</weight>
                        <audioBandwidth>0</audioBandwidth>
                        <videoBandwidth>0</videoBandwidth>
                        <immersiveBandwidth>0</immersiveBandwidth>
                    </betweenLocation>
                </betweenLocations>
            </location>
            </ns:addLocation>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_location failed: {r.text[:400]}")

    
    def get_physicallocation(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getPhysicalLocation>
                    <name>{name}</name>
                </ns:getPhysicalLocation>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<physicalLocation>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_physicalLocation failed unexpectedly")
    
    
    def add_physicallocation(self, name: str, description: str | None = None) -> None:
        desc_xml = f"<description>{description}</description>" if description else ""

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addPhysicalLocation>
            <physicalLocation>
                <name>{name}</name>
                {desc_xml}
            </physicalLocation>
            </ns:addPhysicalLocation>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_physicalLocation failed: {r.text[:400]}")
    
    
    def get_srst(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getSrst>
                    <name>{name}</name>
                </ns:getSrst>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<srst>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_srst failed unexpectedly")
    
    
    def add_srst(self, name: str, ipAddress: str | None = None) -> None:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addSrst>
            <srst>
                <name>{name}</name>
                <port>2000</port>
                <ipAddress>{ipAddress}</ipAddress>
                <SipNetwork>{ipAddress}</SipNetwork>
                <SipPort>5060</SipPort>
                <isSecure>false</isSecure>
            </srst>
            </ns:addSrst>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_srst failed: {r.text[:400]}")
        
    
    def list_partitions(self) -> set[str]:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:listRoutePartition>
                    <searchCriteria>
                        <name>%</name>
                    </searchCriteria>
                    <returnedTags>
                        <name />
                    </returnedTags>
                </ns:listRoutePartition>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            # CUCM returns 500 when no objects exist
            if r.status_code == 500 and "Item not valid" in r.text:
                return set()
            raise RuntimeError(f"list_partitions failed: HTTP {r.status_code}")

        root = ET.fromstring(r.text)

        partitions = set()

        # IMPORTANT: routePartition and name are NOT namespaced
        for p in root.findall(".//routePartition"):
            name = p.find("name")
            if name is not None and name.text:
                partitions.add(name.text.strip())

        print(f"AXL list_partitions: found {len(partitions)} partitions")
        return partitions
    
    def get_partition(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getRoutePartition>
                    <name>{name}</name>
                </ns:getRoutePartition>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<routePartition>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_partition failed unexpectedly")
    
    
    def add_partition(self, name: str, description: str | None = None) -> None:
        desc_xml = f"<description>{description}</description>" if description else ""

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addRoutePartition>
            <routePartition>
                <name>{name}</name>
                {desc_xml}
            </routePartition>
            </ns:addRoutePartition>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_partition failed: {r.text[:400]}")


    def get_css(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getCss>
                    <name>{name}</name>
                </ns:getCss>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<callingSearchSpace>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_css failed unexpectedly")
    
    
    def add_css(self, name: str, members: list[str], description: str | None = None) -> None:
        desc_xml = f"<description>{description}</description>" if description else ""
        members_xml = ""
        if members:
            member_entries = "".join(
                f"<member>"
                f"<routePartitionName>{m}</routePartitionName>"
                f"<index>{i}</index>"
                f"</member>"
                for i, m in enumerate(members, start=1)
            )

            members_xml = f"<members>{member_entries}</members>"

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addCss>
                <css>
                    <name>{name}</name>
                    {desc_xml}
                    {members_xml}
                </css>
            </ns:addCss>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_css failed: {r.text[:400]}")
        
        
    def get_mediaresourcegroup(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getMediaResourceGroup>
                    <name>{name}</name>
                </ns:getMediaResourceGroup>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<mediaResourceGroup>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_mediaResourceGroup failed unexpectedly")
    
    
    def add_mediaresourcegroup(self, name: str, description: str , members: list[str] | None = None) -> None:
        desc_xml = f"<description>{description}</description>" if description else ""
        members_xml = ""
        if members:
            member_entries = "".join(
                f"<member>"
                f"<deviceName>{m}</deviceName>"
                f"</member>"
                for i, m in enumerate(members, start=1)
            )

            members_xml = f"<members>{member_entries}</members>"

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addMediaResourceGroup>
            <mediaResourceGroup>
                <name>{name}</name>
                {desc_xml}
                <multicast>false</multicast>
                {members_xml}
            </mediaResourceGroup>
            </ns:addMediaResourceGroup>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_mediaResourceGroup failed: {r.text[:400]}")


    def get_mediaresourcelist(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getMediaResourceList>
                    <name>{name}</name>
                </ns:getMediaResourceList>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<mediaResourceList>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_mediaResourceList failed unexpectedly")
    
    
    def add_mediaresourcelist(self, name: str, members: list[str] | None = None) -> None:
        members_xml = ""
        if members:
            member_entries = "".join(
                f"<member>"
                f"<mediaResourceGroupName>{m}</mediaResourceGroupName>"
                f"<order>{i}</order>"
                f"</member>"
                for i, m in enumerate(members, start=1)
            )

            members_xml = f"<members>{member_entries}</members>"

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addMediaResourceList>
            <mediaResourceList>
                <name>{name}</name>
                    {members_xml}
            </mediaResourceList>
            </ns:addMediaResourceList>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_mediaResourceList failed: {r.text[:400]}")
        
    
    def get_devicepool(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getDevicePool>
                    <name>{name}</name>
                </ns:getDevicePool>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<devicePool>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_devicePool failed unexpectedly")
    
        
    def add_devicepool(
        self, 
        name: str, 
        datetimeSettingName: str,
        callManagerGroupName: str,
        MediaResourceListName: str, 
        regionName: str, 
        srstName: str,
        locationName: str, 
        physicalLocationName: str,
        deviceMobilityGroupName: str | None = None) -> None:

        srst_xml = ""
        if srstName:
            srst_xml = f"<srstName>{escape(srstName)}</srstName>"
        

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addDevicePool>
            <devicePool>
                <name>{name}</name>
                <dateTimeSettingName>{datetimeSettingName}</dateTimeSettingName>
                <callManagerGroupName>{callManagerGroupName}</callManagerGroupName>
                <mediaResourceListName>{MediaResourceListName}</mediaResourceListName>
                <regionName>{regionName}</regionName>
                <networkLocale>United States</networkLocale>
                {srst_xml}
                <aarNeighborhoodName/>
                <locationName>{locationName}</locationName>
                <physicalLocationName>{physicalLocationName}</physicalLocationName>
                <deviceMobilityGroupName>{deviceMobilityGroupName or ''}</deviceMobilityGroupName>          
            </devicePool>
            </ns:addDevicePool>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_devicepool failed: {r.text[:400]}")
        
        
    def get_devicemobility(self, name: str) -> bool:
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
            <soapenv:Body>
                <ns:getDeviceMobility>
                    <name>{name}</name>
                </ns:getDeviceMobility>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        # Must be 200 AND contain object
        if r.status_code == 200 and "<deviceMobilityInfo>" in r.text:
            return True

        # CUCM standard "not found"
        if r.status_code == 500 and "Item not valid" in r.text:
            return False

        raise RuntimeError(f"get_deviceMobilityInfo failed unexpectedly")
    
        
    def add_devicemobility(self, name: str, subnet: str, mask: str, members: list[str] | None = None) -> None:
        members_xml = ""
        if members:
            member_entries = "".join(
                f"<member>"
                f"<devicePoolName>{m}</devicePoolName>"
                f"</member>"
                for i, m in enumerate(members, start=1)
            )

            members_xml = f"<members>{member_entries}</members>"
            
        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                        xmlns:ns="http://www.cisco.com/AXL/API/{self.axl_version}">
        <soapenv:Body>
            <ns:addDeviceMobility>
            <deviceMobility>
                <name>{name}</name>
                <subNetDetails>
                    <ipv4SubNetDetails>
                        <ipv4Subnet>{subnet}</ipv4Subnet>
                        <ipv4SubNetMaskSz>{mask}</ipv4SubNetMaskSz>
                    </ipv4SubNetDetails>    
                </subNetDetails>
                {members_xml}
            </deviceMobility>
            </ns:addDeviceMobility>
        </soapenv:Body>
        </soapenv:Envelope>
        """

        r = self._post(body)

        if r.status_code != 200:
            raise RuntimeError(f"add_devicemobility failed: {r.text[:400]}")
        
        
    def removeRegion(self, name: str) -> None:
        self.remove_op("removeRegion", name=name)

    def removeLocation(self, name: str) -> None:
        self.remove_op("removeLocation", name=name)

    def removePhysicalLocation(self, name: str) -> None:
        self.remove_op("removePhysicalLocation", name=name)

    def removeSrst(self, name: str) -> None:
        self.remove_op("removeSrst", name=name)

    def removeRoutePartition(self, name: str) -> None:
        self.remove_op("removeRoutePartition", name=name)

    def removeCss(self, name: str) -> None:
        self.remove_op("removeCss", name=name)

    def removeMediaResourceGroup(self, name: str) -> None:
        self.remove_op("removeMediaResourceGroup", name=name)

    def removeMediaResourceList(self, name: str) -> None:
        self.remove_op("removeMediaResourceList", name=name)

    def removeDevicePool(self, name: str) -> None:
        self.remove_op("removeDevicePool", name=name)

    def removeDeviceMobility(self, name: str) -> None:
        self.remove_op("removeDeviceMobility", name=name)