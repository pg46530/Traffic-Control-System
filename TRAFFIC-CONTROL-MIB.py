# SNMP MIB module (TRAFFIC-CONTROL-MIB) expressed in pysnmp data model.
#
# This Python module is designed to be imported and executed by the
# pysnmp library.
#
# See https://www.pysnmp.com/pysnmp for further information.
#
# Notes
# -----
# ASN.1 source file://./TRAFFIC-CONTROL-MIB.mib
# Produced by pysmi-1.6.3 at Sun Apr 19 16:54:11 2026
# On host netsim-vm platform Linux version 6.8.0-94-generic by user netsim
# Using Python version 3.10.12 (main, Mar  3 2026, 11:56:32) [GCC 11.4.0]

if 'mibBuilder' not in globals():
    import sys

    sys.stderr.write(__doc__)
    sys.exit(1)

# Import base ASN.1 objects even if this MIB does not use it

(Integer,
 OctetString,
 ObjectIdentifier) = mibBuilder.importSymbols(
    "ASN1",
    "Integer",
    "OctetString",
    "ObjectIdentifier")

(NamedValues,) = mibBuilder.importSymbols(
    "ASN1-ENUMERATION",
    "NamedValues")
(ConstraintsIntersection,
 ConstraintsUnion,
 SingleValueConstraint,
 ValueRangeConstraint,
 ValueSizeConstraint) = mibBuilder.importSymbols(
    "ASN1-REFINEMENT",
    "ConstraintsIntersection",
    "ConstraintsUnion",
    "SingleValueConstraint",
    "ValueRangeConstraint",
    "ValueSizeConstraint")

# Import SMI symbols from the MIBs this MIB depends on

(ModuleCompliance,
 NotificationGroup,
 ObjectGroup) = mibBuilder.importSymbols(
    "SNMPv2-CONF",
    "ModuleCompliance",
    "NotificationGroup",
    "ObjectGroup")

(Bits,
 Counter32,
 Counter64,
 Gauge32,
 Integer32,
 IpAddress,
 ModuleIdentity,
 MibIdentifier,
 NotificationType,
 ObjectIdentity,
 MibScalar,
 MibTable,
 MibTableRow,
 MibTableColumn,
 TimeTicks,
 Unsigned32,
 experimental,
 iso) = mibBuilder.importSymbols(
    "SNMPv2-SMI",
    "Bits",
    "Counter32",
    "Counter64",
    "Gauge32",
    "Integer32",
    "IpAddress",
    "ModuleIdentity",
    "MibIdentifier",
    "NotificationType",
    "ObjectIdentity",
    "MibScalar",
    "MibTable",
    "MibTableRow",
    "MibTableColumn",
    "TimeTicks",
    "Unsigned32",
    "experimental",
    "iso")

(DisplayString,
 PhysAddress,
 TextualConvention) = mibBuilder.importSymbols(
    "SNMPv2-TC",
    "DisplayString",
    "PhysAddress",
    "TextualConvention")


# MODULE-IDENTITY

trafficControlMIB = ModuleIdentity(
    (1, 3, 6, 1, 3, 2026)
)
if mibBuilder.loadTexts:
    trafficControlMIB.setRevisions(
        ("2026-03-20 00:00",)
    )


# Types definitions


# TEXTUAL-CONVENTIONS



class TrafficLightColorType(TextualConvention, Integer32):
    status = "current"
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        SingleValueConstraint(
            *(1,
              2)
        )
    )
    namedValues = NamedValues(
        *(("red", 1),
          ("green", 2))
    )



# MIB Managed Objects in the order of their OIDs

_TrafficControlObjects_ObjectIdentity = ObjectIdentity
trafficControlObjects = _TrafficControlObjects_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 1)
)
_SimConfig_ObjectIdentity = ObjectIdentity
simConfig = _SimConfig_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 1, 1)
)


class _SimulationStepTime_Type(Integer32):
    """Custom type simulationStepTime based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 3600),
    )


_SimulationStepTime_Type.__name__ = "Integer32"
_SimulationStepTime_Object = MibScalar
simulationStepTime = _SimulationStepTime_Object(
    (1, 3, 6, 1, 3, 2026, 1, 1, 1),
    _SimulationStepTime_Type()
)
simulationStepTime.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    simulationStepTime.setStatus("current")


class _DefaultCrossTrafficRate_Type(Integer32):
    """Custom type defaultCrossTrafficRate based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 100),
    )


_DefaultCrossTrafficRate_Type.__name__ = "Integer32"
_DefaultCrossTrafficRate_Object = MibScalar
defaultCrossTrafficRate = _DefaultCrossTrafficRate_Object(
    (1, 3, 6, 1, 3, 2026, 1, 1, 2),
    _DefaultCrossTrafficRate_Type()
)
defaultCrossTrafficRate.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    defaultCrossTrafficRate.setStatus("current")
_SystemInfo_ObjectIdentity = ObjectIdentity
systemInfo = _SystemInfo_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 1, 2)
)


class _SystemStatus_Type(Integer32):
    """Custom type systemStatus based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        SingleValueConstraint(
            *(1,
              2,
              3)
        )
    )
    namedValues = NamedValues(
        *(("stopped", 1),
          ("running", 2),
          ("paused", 3))
    )


_SystemStatus_Type.__name__ = "Integer32"
_SystemStatus_Object = MibScalar
systemStatus = _SystemStatus_Object(
    (1, 3, 6, 1, 3, 2026, 1, 2, 1),
    _SystemStatus_Type()
)
systemStatus.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    systemStatus.setStatus("current")


class _SimElapsedTime_Type(Integer32):
    """Custom type simElapsedTime based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 6000),
    )


_SimElapsedTime_Type.__name__ = "Integer32"
_SimElapsedTime_Object = MibScalar
simElapsedTime = _SimElapsedTime_Object(
    (1, 3, 6, 1, 3, 2026, 1, 2, 2),
    _SimElapsedTime_Type()
)
simElapsedTime.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    simElapsedTime.setStatus("current")
if mibBuilder.loadTexts:
    simElapsedTime.setUnits("seconds")


class _TotalVehiclesEntered_Type(Integer32):
    """Custom type totalVehiclesEntered based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 500),
    )


_TotalVehiclesEntered_Type.__name__ = "Integer32"
_TotalVehiclesEntered_Object = MibScalar
totalVehiclesEntered = _TotalVehiclesEntered_Object(
    (1, 3, 6, 1, 3, 2026, 1, 2, 3),
    _TotalVehiclesEntered_Type()
)
totalVehiclesEntered.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    totalVehiclesEntered.setStatus("current")


class _TotalVehiclesExited_Type(Integer32):
    """Custom type totalVehiclesExited based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 500),
    )


_TotalVehiclesExited_Type.__name__ = "Integer32"
_TotalVehiclesExited_Object = MibScalar
totalVehiclesExited = _TotalVehiclesExited_Object(
    (1, 3, 6, 1, 3, 2026, 1, 2, 4),
    _TotalVehiclesExited_Type()
)
totalVehiclesExited.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    totalVehiclesExited.setStatus("current")


class _CurrentVehiclesInSystem_Type(Integer32):
    """Custom type currentVehiclesInSystem based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 3000),
    )


_CurrentVehiclesInSystem_Type.__name__ = "Integer32"
_CurrentVehiclesInSystem_Object = MibScalar
currentVehiclesInSystem = _CurrentVehiclesInSystem_Object(
    (1, 3, 6, 1, 3, 2026, 1, 2, 5),
    _CurrentVehiclesInSystem_Type()
)
currentVehiclesInSystem.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    currentVehiclesInSystem.setStatus("current")
_TrafficTables_ObjectIdentity = ObjectIdentity
trafficTables = _TrafficTables_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 1, 3)
)
_RoadsTable_Object = MibTable
roadsTable = _RoadsTable_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1)
)
if mibBuilder.loadTexts:
    roadsTable.setStatus("current")
_RoadsEntry_Object = MibTableRow
roadsEntry = _RoadsEntry_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1)
)
roadsEntry.setIndexNames(
    (0, "TRAFFIC-CONTROL-MIB", "roadId"),
)
if mibBuilder.loadTexts:
    roadsEntry.setStatus("current")


class _RoadId_Type(Integer32):
    """Custom type roadId based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 30),
    )


_RoadId_Type.__name__ = "Integer32"
_RoadId_Object = MibTableColumn
roadId = _RoadId_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 1),
    _RoadId_Type()
)
roadId.setMaxAccess("not-accessible")
if mibBuilder.loadTexts:
    roadId.setStatus("current")


class _RoadName_Type(DisplayString):
    """Custom type roadName based on DisplayString"""
    subtypeSpec = DisplayString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(0, 30),
    )


_RoadName_Type.__name__ = "DisplayString"
_RoadName_Object = MibTableColumn
roadName = _RoadName_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 2),
    _RoadName_Type()
)
roadName.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    roadName.setStatus("current")


class _Capacity_Type(Integer32):
    """Custom type capacity based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 100),
    )


_Capacity_Type.__name__ = "Integer32"
_Capacity_Object = MibTableColumn
capacity = _Capacity_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 3),
    _Capacity_Type()
)
capacity.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    capacity.setStatus("current")


class _VehicleCount_Type(Integer32):
    """Custom type vehicleCount based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 100),
    )


_VehicleCount_Type.__name__ = "Integer32"
_VehicleCount_Object = MibTableColumn
vehicleCount = _VehicleCount_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 4),
    _VehicleCount_Type()
)
vehicleCount.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    vehicleCount.setStatus("current")


class _TrafficRate_Type(Integer32):
    """Custom type trafficRate based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 100),
    )


_TrafficRate_Type.__name__ = "Integer32"
_TrafficRate_Object = MibTableColumn
trafficRate = _TrafficRate_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 5),
    _TrafficRate_Type()
)
trafficRate.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    trafficRate.setStatus("current")
_TrafficLightColor_Type = TrafficLightColorType
_TrafficLightColor_Object = MibTableColumn
trafficLightColor = _TrafficLightColor_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 6),
    _TrafficLightColor_Type()
)
trafficLightColor.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    trafficLightColor.setStatus("current")


class _ColorShiftInterval_Type(Integer32):
    """Custom type colorShiftInterval based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 3600),
    )


_ColorShiftInterval_Type.__name__ = "Integer32"
_ColorShiftInterval_Object = MibTableColumn
colorShiftInterval = _ColorShiftInterval_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 7),
    _ColorShiftInterval_Type()
)
colorShiftInterval.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    colorShiftInterval.setStatus("current")


class _GreenDuration_Type(Integer32):
    """Custom type greenDuration based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 3600),
    )


_GreenDuration_Type.__name__ = "Integer32"
_GreenDuration_Object = MibTableColumn
greenDuration = _GreenDuration_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 8),
    _GreenDuration_Type()
)
greenDuration.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    greenDuration.setStatus("current")


class _RedDuration_Type(Integer32):
    """Custom type redDuration based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 3600),
    )


_RedDuration_Type.__name__ = "Integer32"
_RedDuration_Object = MibTableColumn
redDuration = _RedDuration_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 1, 1, 9),
    _RedDuration_Type()
)
redDuration.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    redDuration.setStatus("current")
_RoadConnectionsTable_Object = MibTable
roadConnectionsTable = _RoadConnectionsTable_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 2)
)
if mibBuilder.loadTexts:
    roadConnectionsTable.setStatus("current")
_RoadConnectionsEntry_Object = MibTableRow
roadConnectionsEntry = _RoadConnectionsEntry_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 2, 1)
)
roadConnectionsEntry.setIndexNames(
    (0, "TRAFFIC-CONTROL-MIB", "connectionId"),
)
if mibBuilder.loadTexts:
    roadConnectionsEntry.setStatus("current")


class _ConnectionId_Type(Integer32):
    """Custom type connectionId based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 1000),
    )


_ConnectionId_Type.__name__ = "Integer32"
_ConnectionId_Object = MibTableColumn
connectionId = _ConnectionId_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 2, 1, 1),
    _ConnectionId_Type()
)
connectionId.setMaxAccess("not-accessible")
if mibBuilder.loadTexts:
    connectionId.setStatus("current")


class _OriginRoadId_Type(Integer32):
    """Custom type originRoadId based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 100),
    )


_OriginRoadId_Type.__name__ = "Integer32"
_OriginRoadId_Object = MibTableColumn
originRoadId = _OriginRoadId_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 2, 1, 2),
    _OriginRoadId_Type()
)
originRoadId.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    originRoadId.setStatus("current")


class _DestinationRoadId_Type(Integer32):
    """Custom type destinationRoadId based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(1, 100),
    )


_DestinationRoadId_Type.__name__ = "Integer32"
_DestinationRoadId_Object = MibTableColumn
destinationRoadId = _DestinationRoadId_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 2, 1, 3),
    _DestinationRoadId_Type()
)
destinationRoadId.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    destinationRoadId.setStatus("current")


class _TrafficDistributionRate_Type(Integer32):
    """Custom type trafficDistributionRate based on Integer32"""
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 100),
    )


_TrafficDistributionRate_Type.__name__ = "Integer32"
_TrafficDistributionRate_Object = MibTableColumn
trafficDistributionRate = _TrafficDistributionRate_Object(
    (1, 3, 6, 1, 3, 2026, 1, 3, 2, 1, 4),
    _TrafficDistributionRate_Type()
)
trafficDistributionRate.setMaxAccess("read-write")
if mibBuilder.loadTexts:
    trafficDistributionRate.setStatus("current")
_TrafficControlConformance_ObjectIdentity = ObjectIdentity
trafficControlConformance = _TrafficControlConformance_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 2)
)
_TrafficControlGroups_ObjectIdentity = ObjectIdentity
trafficControlGroups = _TrafficControlGroups_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 2, 1)
)
_TrafficControlCompliances_ObjectIdentity = ObjectIdentity
trafficControlCompliances = _TrafficControlCompliances_ObjectIdentity(
    (1, 3, 6, 1, 3, 2026, 2, 2)
)

# Managed Objects groups

trafficControlScalarGroup = ObjectGroup(
    (1, 3, 6, 1, 3, 2026, 2, 1, 1)
)
trafficControlScalarGroup.setObjects(
      *(("TRAFFIC-CONTROL-MIB", "simulationStepTime"),
        ("TRAFFIC-CONTROL-MIB", "defaultCrossTrafficRate"),
        ("TRAFFIC-CONTROL-MIB", "systemStatus"),
        ("TRAFFIC-CONTROL-MIB", "simElapsedTime"),
        ("TRAFFIC-CONTROL-MIB", "totalVehiclesEntered"),
        ("TRAFFIC-CONTROL-MIB", "totalVehiclesExited"),
        ("TRAFFIC-CONTROL-MIB", "currentVehiclesInSystem"))
)
if mibBuilder.loadTexts:
    trafficControlScalarGroup.setStatus("current")

trafficControlRoadsGroup = ObjectGroup(
    (1, 3, 6, 1, 3, 2026, 2, 1, 2)
)
trafficControlRoadsGroup.setObjects(
      *(("TRAFFIC-CONTROL-MIB", "roadName"),
        ("TRAFFIC-CONTROL-MIB", "capacity"),
        ("TRAFFIC-CONTROL-MIB", "vehicleCount"),
        ("TRAFFIC-CONTROL-MIB", "trafficRate"),
        ("TRAFFIC-CONTROL-MIB", "trafficLightColor"),
        ("TRAFFIC-CONTROL-MIB", "colorShiftInterval"),
        ("TRAFFIC-CONTROL-MIB", "greenDuration"),
        ("TRAFFIC-CONTROL-MIB", "redDuration"))
)
if mibBuilder.loadTexts:
    trafficControlRoadsGroup.setStatus("current")

trafficControlConnectionsGroup = ObjectGroup(
    (1, 3, 6, 1, 3, 2026, 2, 1, 3)
)
trafficControlConnectionsGroup.setObjects(
      *(("TRAFFIC-CONTROL-MIB", "originRoadId"),
        ("TRAFFIC-CONTROL-MIB", "destinationRoadId"),
        ("TRAFFIC-CONTROL-MIB", "trafficDistributionRate"))
)
if mibBuilder.loadTexts:
    trafficControlConnectionsGroup.setStatus("current")


# Notification objects


# Notifications groups


# Agent capabilities


# Module compliance

trafficControlCompliance = ModuleCompliance(
    (1, 3, 6, 1, 3, 2026, 2, 2, 1)
)
trafficControlCompliance.setObjects(
      *(("TRAFFIC-CONTROL-MIB", "trafficControlScalarGroup"),
        ("TRAFFIC-CONTROL-MIB", "trafficControlRoadsGroup"),
        ("TRAFFIC-CONTROL-MIB", "trafficControlConnectionsGroup"))
)
if mibBuilder.loadTexts:
    trafficControlCompliance.setStatus(
        "current"
    )


# Export all MIB objects to the MIB builder

mibBuilder.exportSymbols(
    "TRAFFIC-CONTROL-MIB",
    **{"TrafficLightColorType": TrafficLightColorType,
       "trafficControlMIB": trafficControlMIB,
       "trafficControlObjects": trafficControlObjects,
       "simConfig": simConfig,
       "simulationStepTime": simulationStepTime,
       "defaultCrossTrafficRate": defaultCrossTrafficRate,
       "systemInfo": systemInfo,
       "systemStatus": systemStatus,
       "simElapsedTime": simElapsedTime,
       "totalVehiclesEntered": totalVehiclesEntered,
       "totalVehiclesExited": totalVehiclesExited,
       "currentVehiclesInSystem": currentVehiclesInSystem,
       "trafficTables": trafficTables,
       "roadsTable": roadsTable,
       "roadsEntry": roadsEntry,
       "roadId": roadId,
       "roadName": roadName,
       "capacity": capacity,
       "vehicleCount": vehicleCount,
       "trafficRate": trafficRate,
       "trafficLightColor": trafficLightColor,
       "colorShiftInterval": colorShiftInterval,
       "greenDuration": greenDuration,
       "redDuration": redDuration,
       "roadConnectionsTable": roadConnectionsTable,
       "roadConnectionsEntry": roadConnectionsEntry,
       "connectionId": connectionId,
       "originRoadId": originRoadId,
       "destinationRoadId": destinationRoadId,
       "trafficDistributionRate": trafficDistributionRate,
       "trafficControlConformance": trafficControlConformance,
       "trafficControlGroups": trafficControlGroups,
       "trafficControlScalarGroup": trafficControlScalarGroup,
       "trafficControlRoadsGroup": trafficControlRoadsGroup,
       "trafficControlConnectionsGroup": trafficControlConnectionsGroup,
       "trafficControlCompliances": trafficControlCompliances,
       "trafficControlCompliance": trafficControlCompliance}
)
