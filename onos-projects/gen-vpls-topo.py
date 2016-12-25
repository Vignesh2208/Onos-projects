#!/usr/bin/env python

from mininet.cli import CLI
from mininet.node import Host
from mininet.net import Mininet
from mininet.node import RemoteController

from collections import defaultdict
from readTopoConfiguration import *
import httplib2
import json
import urllib

controllerIP = '172.17.0.137'
controllerPort = 6653
networkCfgPort = 8181

baseURL = "http://" + controllerIP + ":" + str(networkCfgPort) + "/onos/v1/"
userName = "karaf"
passwd = "karaf"
requestHandler = httplib2.Http()
requestHandler.add_credentials(userName, passwd)


class VLANHost(Host):
    def config(self, vlan=100, **params):
        self.nVlanInterfaces = 0
        self.nodeId = 0
        self.vlanInterfaceNames = []
        r = super(VLANHost, self).config(**params)

        return r

    def setNodeId(self, nodeId):
        self.nodeId = nodeId

    def addVlanInterface(self, vlanId):
        # targetIntfName = "h" + str(self.nodeId) + "-eth" + str(self.nVlanInterfaces)
        targetIntfName = "h" + str(self.nodeId) + "-eth0"

        self.nVlanInterfaces = 1
        # self.nVlanInterfaces = self.nVlanInterfaces + 1
        self.configVlanInterface(targetIntfName, vlanId)

    def getInterfaceMAC(self, hostId, intfId):
        mac = "00:" + str(hex(hostId)[2:]) + ":00:00:00:" + str(hex(intfId)[2:])
        return mac

    def configVlanInterface(self, targetIntfName, vlanId):
        intf = targetIntfName
        print "Target intf Name = ", targetIntfName
        self.cmd('ip link set ' + str(intf) + ' address ' + self.getInterfaceMAC(self.nodeId, self.nVlanInterfaces))
        self.cmd('ifconfig %s inet 0' % intf)

        vlanIntfName = intf + "." + str(vlanId)
        vlanIntfIP = "10." + str(vlanId) + ".0" + "." + str(self.nodeId)

        # create VLAN interface
        print self.cmd('vconfig add %s %d' % (intf, vlanId))
        # configure new VLAN interface
        cmdToRun = "ifconfig " + vlanIntfName + " " + vlanIntfIP + " " + "netmask 255.255.0.0"
        # cmdToRun = 'ifconfig ' + vlanIntfName + ' inet ' + (intfIP + "/8")
        print self.cmd(cmdToRun)
        self.vlanInterfaceNames.append(vlanIntfName)


def push_network_cfg_ports_conf(switch_port_mapping):

    net_conf_dict = {}
    ports_conf = {}
    vpls_dict = defaultdict(list)

    j = 0
    for onos_switch_id in switch_port_mapping:
        for key in switch_port_mapping[onos_switch_id]:
            if key == "nPorts":
                continue

            port_name = "of:" + str(onos_switch_id) + "/" + str(key)
            port_value = {"interfaces": []}

            for port_intf_tuple in switch_port_mapping[onos_switch_id][key]:

                vpls_dict["vpls" + str(port_intf_tuple[1])].append(port_intf_tuple[0])

                port_value["interfaces"].append({"name": port_intf_tuple[0],
                                                 "vlan": port_intf_tuple[1]})

            ports_conf[port_name] = port_value

    net_conf_dict = {"ports": ports_conf}

    network_cfg_url = baseURL + "network/configuration/"

    resp, content = requestHandler.request(network_cfg_url, "POST",
                                           headers={'Content-type': 'application/json; charset=UTF-8'},
                                           body=json.dumps(net_conf_dict))

    return vpls_dict


def push_network_cfg_vpls_conf(vpls_dict):

    print "vpls_dict:", vpls_dict

    net_conf_dict = {}

    vpls_list = []
    for vpls_name in vpls_dict:

        this_vpls = {"name": vpls_name, "interfaces": vpls_dict[vpls_name]}
        vpls_list.append(this_vpls)

    net_conf_dict = {"apps": {"org.onosproject.vpls": {"vpls": {"vplsList": vpls_list}}}}

    network_cfg_url = baseURL + "network/configuration/"

    resp, content = requestHandler.request(network_cfg_url, "POST",
                                           headers={'Content-type': 'application/json; charset=UTF-8'},
                                           body=json.dumps(net_conf_dict))


def runTopology(topo_tuples_list, nGrids, nSwitchesPerGrid, nHostsPerSwitch):

    print "*** Reading Topology Config"
    HostNodes, SwitchPortVlanMapping, SwitchConnections = parseTopoTuples(topo_tuples_list)

    os.system("sudo mn -c")

    push_network_cfg_vpls_conf({})

    net = Mininet(autoSetMacs=True)
    c1 = net.addController('c1', controller=RemoteController, ip=controllerIP, port=controllerPort)

    SwitchObjs = {}
    HostObjs = {}

    print "*** Adding Switches"

    switchList = sorted(list(SwitchPortVlanMapping.keys()), key=lambda switch_number: int(switch_number[1:]))
    print "switchList = ", switchList
    for onosSwitchId in switchList:
        switchName = getSwitchName(onosSwitchId)
        switch = net.addSwitch(switchName)
        SwitchObjs[switchName] = switch

    switchList = sorted(list(SwitchObjs.keys()), key=lambda switch_number: int(switch_number[1:]))
    hostNodeList = sorted(list(HostNodes.keys()), key=lambda host_number: int(host_number[1:]))

    print "*** Adding Hosts"

    for node in hostNodeList:
        host = net.addHost(node, cls=VLANHost)
        HostObjs[node] = net.getNodeByName(node)

    print "*** Adding Host-Switch Links"

    for node in hostNodeList:
        nIntfs = HostNodes[node]['nIntfs']
        connectedSwitchName = HostNodes[node]['switch']
        assert nIntfs > 0
        assert not isHost(connectedSwitchName)
        assert connectedSwitchName in SwitchObjs.keys()
        i = 0
        while i < 1:
            intfName = node + "-eth" + str(i)
            l = net.addLink(HostObjs[node], SwitchObjs[connectedSwitchName], intfName1=intfName)
            i += 1

    print "*** Adding Switch-Switch Links"

    for connections in SwitchConnections:
        switch1Name = connections[0]
        switch2Name = connections[1]
        assert switch1Name in SwitchObjs.keys()
        assert switch2Name in SwitchObjs.keys()
        net.addLink(SwitchObjs[switch1Name], SwitchObjs[switch2Name])

    #generate and push onos Network Cfg

    vpls_dict = push_network_cfg_ports_conf(SwitchPortVlanMapping)

    print "*** Starting network"
    net.build()

    for hostName in hostNodeList:
        hostId = int(hostName[1:])
        nIntfs = HostNodes[hostName]['nIntfs']
        assert hostName in HostObjs.keys()
        assert nIntfs > 0
        hostObj = HostObjs[hostName]

        hostObj.setNodeId(hostId)
        i = 1
        while i <= nIntfs:
            intfName = hostName + "-eth" + str(i - 1)
            vlanId = HostNodes[hostName]['vlan'][i]
            hostObj.addVlanInterface(vlanId)
            i += 1

    c1.start()
    for switchName in switchList:
        switch = SwitchObjs[switchName]
        switch.start([c1])

    pingHosts(HostObjs, nGrids, nSwitchesPerGrid, nHostsPerSwitch)

    push_network_cfg_vpls_conf(vpls_dict)
    #installControlVlanFlows(controlVlanId, controlVlanTCPDest)

    print "*** Running CLI"
    CLI(net)

    print "*** Stopping network"

    for switchName in switchList:
        switch = SwitchObjs[switchName]
        switch.stop()

    c1.stop()
    net.stop()

def installControlVlanFlows(controlVlanId, controlVlanTCPDest):

    getFlowsUrl = baseURL + "flows"
    resp, content = requestHandler.request(getFlowsUrl, "GET")

    vplsFlows = json.loads(content)

    for flow in vplsFlows['flows']:
        deleteFlowUrl = baseURL + "flows/" + urllib.quote(flow["deviceId"]) + "/" + flow["id"]

        # print "Flow = ", flow
        resp, content = requestHandler.request(deleteFlowUrl, "DELETE")
        flowCriteria = flow["selector"]["criteria"]
        for criteria in flowCriteria:
            if criteria["type"] == "VLAN_VID":
                vlanId = criteria["vlanId"]
                if vlanId == controlVlanId:

                    newTCPDestCriteria = {}
                    newTCPDestCriteria["type"] = "TCP_DST"
                    newTCPDestCriteria["tcpPort"] = controlVlanTCPDest
                    flowCriteria.append(newTCPDestCriteria)

                    break

    print "Updated Flows for controlVlan"
    updatedFlows = json.dumps(vplsFlows)
    updateFlowUrl = baseURL + "flows/"
    resp, content = requestHandler.request(updateFlowUrl, "POST",
                                           headers={'Content-type': 'application/json; charset=UTF-8'},
                                           body=updatedFlows)


def pingEnclaveHostPairs(HostObjs, hostIds, vlanId):
    assert vlanId <= 256
    for i in xrange(len(hostIds)):

        #j = (i + 1) % len(hostIds)

        for j in xrange(len(hostIds)):
            if i == j:
                continue

            srcHostName = "h" + str(hostIds[i])
            dstHostName = "h" + str(hostIds[j])
            assert srcHostName in HostObjs.keys()
            assert dstHostName in HostObjs.keys()

            dstHostIp = "10." + str(vlanId) + ".0." + str(hostIds[j])
            srcHostInterface = srcHostName + "-eth0." + str(vlanId)
            srcHost = HostObjs[srcHostName]
            dstHost = HostObjs[dstHostName]
            pingCmd = "ping -c 3 -I " + srcHostInterface + " " + dstHostIp
            srcHost.cmd(pingCmd)


def pingHosts(HostObjs, nGrids, nSwitchesPerGrid, nHostsPerSwitch):
    nSwitches = nSwitchesPerGrid * nGrids
    nHosts = nSwitches * nHostsPerSwitch
    nHostsPerGrid = nSwitchesPerGrid * nHostsPerSwitch

    controlSwitch = nSwitches + 1
    controlHost = nHosts + 1
    i = 1
    while i <= nHosts + 1 - nHostsPerSwitch:
        enclaveHosts = range(i, i + nHostsPerSwitch, 1)
        assert len(enclaveHosts) == nHostsPerSwitch

        switchId = int((i - 1) / nHostsPerSwitch) + 1
        enclaveVlanId = switchId
        print "Pinging hosts in enclave: ", enclaveVlanId
        pingEnclaveHostPairs(HostObjs, enclaveHosts, enclaveVlanId)
        i = i + nHostsPerSwitch

    controlVlanHosts = range(1, controlHost + 1, nHostsPerSwitch)
    assert len(controlVlanHosts) == nSwitches + 1
    print "pinging control vlan hosts .."
    pingEnclaveHostPairs(HostObjs, controlVlanHosts, controlVlanId)


def genUGridTopoTuples(nGrids, nSwitchesPerGrid, nHostsPerSwitch, controlVlanId):

    nSwitches = nSwitchesPerGrid * nGrids
    nHosts = nSwitches * nHostsPerSwitch
    nHostsPerGrid = nSwitchesPerGrid * nHostsPerSwitch

    controlSwitch = nSwitches + 1
    controlHost = nHosts + 1

    topo_tuples_list = []

    topo_tuples_list.append(("h" + str(controlHost) + "_1",
                             "s" + str(controlSwitch),
                             str(controlVlanId)))

    for i in xrange(1, nHosts + 1):
        switchId = int((i - 1) / nHostsPerSwitch) + 1
        uGridId = int((i - 1) / nHostsPerGrid) + 1
        enclaveVlanId = switchId

        if i % nHostsPerSwitch == 1:
            topo_tuples_list.append(("h" + str(i) + "_1",
                                     "s" + str(switchId),
                                     str(enclaveVlanId)))

            topo_tuples_list.append(("h" + str(i) + "_2",
                                     "s" + str(switchId),
                                     str(controlVlanId)))

            if switchId <= uGridId * nSwitchesPerGrid - 1:
                topo_tuples_list.append(("s" + str(switchId),
                                         "s" + str(switchId + 1)))

            elif switchId == uGridId * nSwitchesPerGrid:
                topo_tuples_list.append(("s" + str(switchId),
                                         "s" + str(controlSwitch)))

                topo_tuples_list.append(("s" + str(switchId),
                                         "s" + str((uGridId - 1) * nSwitchesPerGrid + 1)))
        else:
            topo_tuples_list.append(("h" + str(i) + "_1",
                                     "s" + str(switchId),
                                     str(enclaveVlanId)))

    return topo_tuples_list


def parseTopoTuples(topo_tuples_list):
    Nodes = {}
    SwitchPortVlanMapping = {}
    SwitchConnections = []
    for fieldsList in topo_tuples_list:

        if len(fieldsList) != 2 and len(fieldsList) != 3:
            continue

        srcId = fieldsList[0]
        dstId = fieldsList[1]

        if srcId.startswith('s') and dstId.startswith('s'):
            SwitchConnections.append((srcId, dstId))
        else:
            try:
                vlanId = int(fieldsList[2])
            except:
                pass

            if isHost(srcId):
                intf = getInterface(srcId)
                srcId = getHostId(srcId)
                if srcId not in Nodes.keys():
                    Nodes[srcId] = {}
                    Nodes[srcId]['vlan'] = {}
                    Nodes[srcId]['nIntfs'] = 0

            elif srcId not in SwitchPortVlanMapping.keys():
                SwitchPortVlanMapping[getOnosSwitchId(srcId)] = {}
                SwitchPortVlanMapping[getOnosSwitchId(srcId)]['nPorts'] = 0

            if isHost(dstId):
                intf = getInterface(srcId)
                dstId = getHostId(dstId)
                if dstId not in Nodes.keys():
                    Nodes[dstId] = {}
                    Nodes[dstId]['vlan'] = {}
                    Nodes[dstId]['nIntfs'] = 0

            elif dstId not in SwitchPortVlanMapping.keys():
                SwitchPortVlanMapping[getOnosSwitchId(dstId)] = {}
                SwitchPortVlanMapping[getOnosSwitchId(dstId)]['nPorts'] = 0

            if isHost(srcId):
                Nodes[srcId]['nIntfs'] = Nodes[srcId]['nIntfs'] + 1
                Nodes[srcId]['vlan'][intf] = vlanId
                Nodes[srcId]['switch'] = dstId

            if isHost(dstId):
                Nodes[dstId]['nIntfs'] = Nodes[dstId]['nIntfs'] + 1
                Nodes[dstId]['vlan'][intf] = vlanId
                Nodes[dstId]['switch'] = srcId

    nodeList = sorted(list(Nodes.keys()), key=lambda host_number: int(host_number[1:]))

    for node in nodeList:
        nIntfs = Nodes[node]['nIntfs']
        assert nIntfs > 0
        assert isHost(Nodes[node]['switch']) == False

        connectedSwitch = getOnosSwitchId(Nodes[node]['switch'])
        portNo = SwitchPortVlanMapping[connectedSwitch]['nPorts'] + 1
        SwitchPortVlanMapping[connectedSwitch][portNo] = []
        SwitchPortVlanMapping[connectedSwitch]['nPorts'] = SwitchPortVlanMapping[connectedSwitch]['nPorts'] + 1

        i = 1
        while i <= nIntfs:
            if i not in Nodes[node]['vlan'].keys():
                throwERROR("Missing Interface " + str(i) + " for host " + str(node))

            vlanId = Nodes[node]['vlan'][i]

            intfName = node + "-eth0." + str(vlanId)
            SwitchPortVlanMapping[connectedSwitch][portNo].append((intfName, vlanId))
            i += 1

    return Nodes, SwitchPortVlanMapping, SwitchConnections

if __name__ == '__main__':

    nGrids = 1
    nSwitchesPerGrid = 3  # >= 2
    nHostsPerSwitch = 4 # >= 2
    controlVlanId = 255
    controlVlanTCPDest = 20000

    topo_tuples_list = genUGridTopoTuples(nGrids, nSwitchesPerGrid, nHostsPerSwitch, controlVlanId)
    runTopology(topo_tuples_list, nGrids, nSwitchesPerGrid, nHostsPerSwitch)
