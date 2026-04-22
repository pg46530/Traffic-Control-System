import os
import json
import time
import asyncio
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.smi import builder, instrum, exval
from pysnmp.carrier.asyncio.dgram import udp

from mib_handlers import get_dynamic_scalar_class, get_dynamic_column_class

class CentralSystem:
    def __init__(self, config_file):
        self.config_file = config_file
        
        self.sim_step_time = 0
        self.max_duration = 0
        self.sim_elapsed_time = 0
        self.system_status = 1  # 1: stopped, 2: running, 3: paused
        
        self.roads = {}
        self.connections = {}
        
        self.load_config()

    def load_config(self):
        print(f"[*] Loading configuration from {self.config_file}...")
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                
                # Instantiate scalars
                self.sim_step_time = data['simulation']['stepTime']
                self.max_duration = data['simulation']['maxDuration']
                
                # Instantiate roadsTable
                for road in data['roads']:
                    road_id = road['roadId']
                    self.roads[road_id] = {
                        'roadName': road['roadName'],
                        'capacity': road['capacity'],
                        'trafficRate': road['trafficRate'],
                        'greenDuration': road['greenDuration'],
                        'redDuration': road['redDuration'],
                        'vehicleCount': 0,           # Initializes at zero
                        'trafficLightColor': 2,      # 1: Red, 2: Green (default to green)
                        'colorShiftInterval': road['greenDuration'] # Time until color change
                    }
                    
                # Instantiate roadConnectionsTable
                for conn in data['connections']:
                    conn_id = conn['connectionId']
                    self.connections[conn_id] = {
                        'originRoadId': conn['originRoadId'],
                        'destinationRoadId': conn['destinationRoadId'],
                        'trafficDistributionRate': conn['trafficDistributionRate']
                    }
                    
            print(f"Loaded {len(self.roads)} Roads and {len(self.connections)} Connections.")
            
        except Exception as e:
            print(f"Error loading configuration: {e}")

    def setup_snmp(self):
        # Configure SNMP Engine, Transports, Security, Context, and load MIBs
        print("Configuring SNMP Engine on port 10161...")
        self.snmp_engine = engine.SnmpEngine()
        
        # Listens on UDP localhost (10161 to avoid sudo requirement)
        config.add_transport(
            self.snmp_engine,
            udp.DOMAIN_NAME,
            udp.UdpTransport().open_server_mode(('127.0.0.1', 10161))
        )
        
        # Add SNMPv2c and the 'public' community
        config.add_v1_system(self.snmp_engine, 'my-area', 'public')
        
        # Grant full permission to the experimental(3).2026 subtree (Traffic Control MIB)
        config.add_vacm_user(self.snmp_engine, 2, 'my-area', 'noAuthNoPriv', (1, 3, 6, 1, 3, 2026), (1, 3, 6, 1, 3, 2026))
        
        self.snmp_context = context.SnmpContext(self.snmp_engine)
        
        # Associate Responders (to support GET, SET, GETNEXT)
        cmdrsp.GetCommandResponder(self.snmp_engine, self.snmp_context)
        cmdrsp.SetCommandResponder(self.snmp_engine, self.snmp_context)
        cmdrsp.NextCommandResponder(self.snmp_engine, self.snmp_context)
        
        # Load our compiled MIB
        print("Loading TRAFFIC-CONTROL-MIB...")
        self.mib_builder = self.snmp_context.get_mib_instrum().get_mib_builder()
        
        # Looks for MIB file (.py) in the parent directory
        mib_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.mib_builder.add_mib_sources(builder.DirMibSource(mib_dir), builder.DirMibSource('.'))
        
        try:
            self.mib_builder.load_modules('TRAFFIC-CONTROL-MIB')
            print("MIB loaded successfully!")
        except Exception as e:
            print(f"Warning: error loading compiled MIB: {e}")

    def bind_scalars(self):
        # Bind Python variables to MIB OIDs for GET requests.
        print("Binding scalar (global) variables...")
        
        MibScalarInstance, = self.mib_builder.import_symbols('SNMPv2-SMI', 'MibScalarInstance')
        
        # Import scalar nodes from MIB
        simulationStepTime, systemStatus, simElapsedTime = self.mib_builder.import_symbols(
            'TRAFFIC-CONTROL-MIB', 
            'simulationStepTime', 
            'systemStatus', 
            'simElapsedTime'
        )

        # Get the dynamic scalar class injected with MibScalarInstance base
        DynamicScalar = get_dynamic_scalar_class(MibScalarInstance)

        # Export the .0 instances and attach them to the agent's OID tree
        self.mib_builder.export_symbols(
            'TRAFFIC-CONTROL-MIB',
            simulationStepTime_inst=DynamicScalar(simulationStepTime.name, (0,), simulationStepTime.syntax, self, 'sim_step_time'),
            systemStatus_inst=DynamicScalar(systemStatus.name, (0,), systemStatus.syntax, self, 'system_status'),
            simElapsedTime_inst=DynamicScalar(simElapsedTime.name, (0,), simElapsedTime.syntax, self, 'sim_elapsed_time')
        )
        print("Scalar bind successfully executed")

    def bind_tables(self):
        # Binds Python dictionaries to MIB OID rows of the roads and connections tables
        print("Binding Table variables...")
        MibScalarInstance, = self.mib_builder.import_symbols('SNMPv2-SMI', 'MibScalarInstance')
        
        # Pull Column definitions from pysnmp compile MIB object
        roadName, capacity, vehicleCount, trafficRate, trafficLightColor, colorShiftInterval, greenDuration, redDuration = self.mib_builder.import_symbols(
            'TRAFFIC-CONTROL-MIB',
            'roadName', 'capacity', 'vehicleCount', 'trafficRate',
            'trafficLightColor', 'colorShiftInterval', 'greenDuration', 'redDuration'
        )

        originRoadId, destinationRoadId, trafficDistributionRate = self.mib_builder.import_symbols(
            'TRAFFIC-CONTROL-MIB',
            'originRoadId', 'destinationRoadId', 'trafficDistributionRate'
        )

        DynamicColumn = get_dynamic_column_class(MibScalarInstance)

        table_symbols = {}
        
        # Iterate over our dictionary to instantiate each row mapping
        # e.g: roadsEntry instances are mapped column by column using their OID length incremented by row index (road_id)
        for road_id, data in self.roads.items():
            instId = (road_id,) # OID Index format tuple
            
            # Map Column objects to their OID index instances
            table_symbols[f"roadName_inst_{road_id}"] = DynamicColumn(roadName.name, instId, roadName.syntax, self, 'roads', 'roadName')
            table_symbols[f"capacity_inst_{road_id}"] = DynamicColumn(capacity.name, instId, capacity.syntax, self, 'roads', 'capacity')
            table_symbols[f"vehicleCount_inst_{road_id}"] = DynamicColumn(vehicleCount.name, instId, vehicleCount.syntax, self, 'roads', 'vehicleCount')
            table_symbols[f"trafficRate_inst_{road_id}"] = DynamicColumn(trafficRate.name, instId, trafficRate.syntax, self, 'roads', 'trafficRate')
            table_symbols[f"trafficLightColor_inst_{road_id}"] = DynamicColumn(trafficLightColor.name, instId, trafficLightColor.syntax, self, 'roads', 'trafficLightColor')
            table_symbols[f"colorShiftInterval_inst_{road_id}"] = DynamicColumn(colorShiftInterval.name, instId, colorShiftInterval.syntax, self, 'roads', 'colorShiftInterval')
            table_symbols[f"greenDuration_inst_{road_id}"] = DynamicColumn(greenDuration.name, instId, greenDuration.syntax, self, 'roads', 'greenDuration')
            table_symbols[f"redDuration_inst_{road_id}"] = DynamicColumn(redDuration.name, instId, redDuration.syntax, self, 'roads', 'redDuration')

        # Bind roadConnectionsTable
        for conn_id, conn_data in self.connections.items():
            instId = (conn_id,)
            table_symbols[f"originRoadId_inst_{conn_id}"] = DynamicColumn(originRoadId.name, instId, originRoadId.syntax, self, 'connections', 'originRoadId')
            table_symbols[f"destinationRoadId_inst_{conn_id}"] = DynamicColumn(destinationRoadId.name, instId, destinationRoadId.syntax, self, 'connections', 'destinationRoadId')
            table_symbols[f"trafficDistributionRate_inst_{conn_id}"] = DynamicColumn(trafficDistributionRate.name, instId, trafficDistributionRate.syntax, self, 'connections', 'trafficDistributionRate')

        # Perform one big export to MIB builder tree
        self.mib_builder.export_symbols('TRAFFIC-CONTROL-MIB', **table_symbols)
        print(f"Table bound successfully for {len(self.roads)} roads and {len(self.connections)} connections.")

    def run(self):
        # Method to start the SNMP agent and keep it running
        self.setup_snmp()
        self.bind_scalars()
        self.bind_tables()
        
        try:
            loop = asyncio.get_event_loop()
            loop.run_forever()
        except KeyboardInterrupt:
            print("\n Shutting down Central System.")

if __name__ == "__main__":
    sc = CentralSystem("traffic-config.json")
    sc.run()

