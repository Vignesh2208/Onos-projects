import os
import sys
import json


def throwERROR(msg):
    print "Topo Config Parser ERROR: ", msg
    sys.exit(-1)


def checkLabelFormat(nodeId, line_no):
    if not nodeId.startswith('s') and not nodeId.startswith('h'):
        throwERROR("Incorrect label at line no : " + str(line_no))
    elif not nodeId.startswith('s'):
        splitList = nodeId.split("_")
        assert len(splitList) == 2
        if not int(splitList[0][1:]) >= 1 or not int(splitList[1]) >= 1:
            throwERROR("Incorrect label at line no : " + str(line_no))
    elif not int(nodeId[1:]) >= 1:
        throwERROR("Incorrect label at line no : " + str(line_no))


def isHost(label):
    if label.startswith('h'):
        return True
    return False


def getOnosSwitchId(label):
    switchId = str(label[1:])
    while len(switchId) < 16:
        switchId = "0" + switchId

    return switchId


def getSwitchName(onosSwitchId):
    return "s" + str(int(onosSwitchId))


def getHostId(label):
    splitList = label.split("_")
    assert len(splitList) == 2
    return splitList[0]


def getInterface(label):
    splitList = label.split("_")
    assert len(splitList) == 2
    return int(splitList[1])


def getInterfaceMAC(hostId, intfId):
    mac = str(hex(hostId)[2:]) + ":00:00:00:00:" + str(hex(intfId)[2:])
    return mac

def generateNetworkCfg(filePath, SwitchPortMapping):
    with open(filePath, "w") as f:
        f.write("{\n")
        f.write("	\"ports\": {\n")
        switchList = sorted(list(SwitchPortMapping.keys()))
        j = 0
        for onosSwitchId in switchList:
            i = 1
            nPorts = SwitchPortMapping[onosSwitchId]['nPorts']
            while i <= nPorts:
                f.write("		\"of:" + str(onosSwitchId) + "/" + str(i) + "\" :	{\n")
                f.write("			\"interfaces\"	:	[\n")
                k = 0
                while k < len(SwitchPortMapping[onosSwitchId][i]):
                    f.write("				{\n")
                    f.write(
                        "					\"name\":	\"" + str(SwitchPortMapping[onosSwitchId][i][k][0]) + "\",\n")
                    f.write(
                        "					\"vlan\":	\"" + str(SwitchPortMapping[onosSwitchId][i][k][1]) + "\"\n")

                    if k < len(SwitchPortMapping[onosSwitchId][i]) - 1:
                        f.write("				},\n")
                    else:
                        f.write("				}\n")
                    k = k + 1

                f.write("			]\n")
                if j == len(switchList) - 1 and i == nPorts:
                    f.write("		}\n")
                else:
                    f.write("		},\n")
                i = i + 1
            j = j + 1

        f.write("	}\n}\n")

if __name__ == '__main__':
    print "##########Nodes#########"
    print Nodes
    print "\n\n"
    print "###SwitchPortVlanMapping###"
    print SwitchPortVlanMapping
    print "\n\n"
    print "####SwitchConnections####"
    print SwitchConnections

    generateNetworkCfg('network-cfg.json', SwitchPortVlanMapping)
