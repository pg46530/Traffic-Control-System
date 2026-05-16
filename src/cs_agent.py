import os
import json
import time
import asyncio
import argparse
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
        self.total_vehicles_entered = 0
        self.total_vehicles_exited = 0
        self.current_vehicles_in_system = 0
        self.default_cross_traffic_rate = 0
        self.sd_interval = 60   # how often (seconds) the SD recalculates light timings
        self.sd_elapsed = 0    # internal counter tracking time since last SD run
        
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
                self.default_cross_traffic_rate = data['simulation'].get('defaultCrossTrafficRate', 0)
                self.sd_interval = data['simulation'].get('sdInterval', 60)
                
                # Instantiate roadsTable
                for road in data['roads']:
                    road_id = road['roadId']
                    self.roads[road_id] = {
                        'roadName': road['roadName'],
                        'type': road.get('type', 'normal'),
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

    def decision_step(self):
        # SD: recalculate green/red durations proportionally to each road's occupancy
        # The total cycle time (greenDuration + redDuration) is preserved per road
        # New times take effect on the next cycle transition, not immediately
        MIN_GREEN = 10  # minimum green seconds guaranteed to every road
        MIN_RED = 10    # minimum red seconds guaranteed to every road

        for road_id, road in self.roads.items():
            total_cycle = road['greenDuration'] + road['redDuration']

            if total_cycle < MIN_GREEN + MIN_RED:
                total_cycle = MIN_GREEN + MIN_RED

            occupancy = road['vehicleCount'] / road['capacity'] if road['capacity'] > 0 else 0.0
            occupancy = max(0.0, min(1.0, occupancy))

            new_green = int(MIN_GREEN + occupancy * (total_cycle - MIN_GREEN - MIN_RED))
            new_green = max(MIN_GREEN, min(total_cycle - MIN_RED, new_green))
            new_red = total_cycle - new_green

            road['greenDuration'] = new_green
            road['redDuration'] = new_red

    def on_system_status_changed(self, new_status):
        # Called when systemStatus is changed via SNMP SET
        if new_status == 1:  # stopped - reset all simulation stats
            self.sim_elapsed_time = 0
            self.total_vehicles_entered = 0
            self.total_vehicles_exited = 0
            self.current_vehicles_in_system = 0
            self.sd_elapsed = 0
            for road in self.roads.values():
                road['vehicleCount'] = 0
            print("[*] Simulation stats reset to initial state.")

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
        simulationStepTime, systemStatus, simElapsedTime, defaultCrossTrafficRate, \
        totalVehiclesEntered, totalVehiclesExited, currentVehiclesInSystem = self.mib_builder.import_symbols(
            'TRAFFIC-CONTROL-MIB',
            'simulationStepTime', 'systemStatus', 'simElapsedTime',
            'defaultCrossTrafficRate', 'totalVehiclesEntered', 'totalVehiclesExited',
            'currentVehiclesInSystem'
        )

        # Get the dynamic scalar class injected with MibScalarInstance base
        DynamicScalar = get_dynamic_scalar_class(MibScalarInstance)

        # Export the .0 instances and attach them to the agent's OID tree
        self.mib_builder.export_symbols(
            'TRAFFIC-CONTROL-MIB',
            simulationStepTime_inst=DynamicScalar(simulationStepTime.name, (0,), simulationStepTime.syntax, self, 'sim_step_time'),
            systemStatus_inst=DynamicScalar(systemStatus.name, (0,), systemStatus.syntax, self, 'system_status', self.on_system_status_changed),
            simElapsedTime_inst=DynamicScalar(simElapsedTime.name, (0,), simElapsedTime.syntax, self, 'sim_elapsed_time'),
            defaultCrossTrafficRate_inst=DynamicScalar(defaultCrossTrafficRate.name, (0,), defaultCrossTrafficRate.syntax, self, 'default_cross_traffic_rate'),
            totalVehiclesEntered_inst=DynamicScalar(totalVehiclesEntered.name, (0,), totalVehiclesEntered.syntax, self, 'total_vehicles_entered'),
            totalVehiclesExited_inst=DynamicScalar(totalVehiclesExited.name, (0,), totalVehiclesExited.syntax, self, 'total_vehicles_exited'),
            currentVehiclesInSystem_inst=DynamicScalar(currentVehiclesInSystem.name, (0,), currentVehiclesInSystem.syntax, self, 'current_vehicles_in_system')
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

        self.mib_builder.export_symbols('TRAFFIC-CONTROL-MIB', **table_symbols)
        print(f"Table bound successfully for {len(self.roads)} roads and {len(self.connections)} connections.")

    async def simulation_loop(self):
        # SSFR asynchronous loop
        print("[*] Starting Simulation Loop (SSFR)...")
        while True:
            await asyncio.sleep(self.sim_step_time)
            
            if self.system_status != 2:
                continue # simulation is not running
                
            self.sim_elapsed_time += self.sim_step_time

            # Check if max simulation duration was reached
            if self.max_duration > 0 and self.sim_elapsed_time >= self.max_duration:
                print(f"[*] Simulation ended: max duration of {self.max_duration}s reached.")
                self.system_status = 1
                self.sim_elapsed_time = 0
                self.total_vehicles_entered = 0
                self.total_vehicles_exited = 0
                self.current_vehicles_in_system = 0
                continue
            
            # dictionary to save traffic moves to apply before the end of the step
            # so cars don't move multiple times in a single step
            pending_moves = {road_id: 0 for road_id in self.roads}

            for road_id, road in self.roads.items():
                # Source roads inject vehicles at their trafficRate (veic/s)
                if road['type'] == 'source' and road['trafficRate'] > 0:
                    cars_generated = int(road['trafficRate'] * self.sim_step_time)
                    if cars_generated == 0:
                        cars_generated = 1  # guarantee at least 1 per step when rate > 0
                    space_available = road['capacity'] - road['vehicleCount']
                    cars_added = min(cars_generated, space_available)
                    if cars_added > 0:
                        road['vehicleCount'] += cars_added
                        self.total_vehicles_entered += cars_added

                road['colorShiftInterval'] -= self.sim_step_time
                if road['colorShiftInterval'] <= 0:
                    if road['trafficLightColor'] == 2: # Green -> Red
                        road['trafficLightColor'] = 1
                        road['colorShiftInterval'] = road['redDuration']
                    else: # Red -> Green
                        road['trafficLightColor'] = 2
                        road['colorShiftInterval'] = road['greenDuration']

            for road_id, road in self.roads.items():
                # Only move cars if the traffic light is Green (2) and there are carts
                if road['trafficLightColor'] != 2 or road['vehicleCount'] <= 0:
                    continue

                out_conns = [c for c in self.connections.values() if c['originRoadId'] == road_id]

                if not out_conns:
                    # Sink road: evacuate at its own trafficRate (veic/s)
                    evacuated = int(road['trafficRate'] * self.sim_step_time)
                    if evacuated == 0 and road['trafficRate'] > 0:
                        evacuated = 1
                    evacuated = min(evacuated, road['vehicleCount'])
                    road['vehicleCount'] -= evacuated
                    self.total_vehicles_exited += evacuated
                else:
                    # How many cars can cross the traffic light per step
                    cars_per_step = self.default_cross_traffic_rate * self.sim_step_time
                    # Guarantee at least 1 car crosses per step when rate > 0
                    if cars_per_step < 1.0 and self.default_cross_traffic_rate > 0:
                        cars_per_step = 1.0

                    # Sum of all distribution percentages for this road out connections
                    total_distribution_pct = sum(c['trafficDistributionRate'] for c in out_conns)
                    if total_distribution_pct <= 0:
                        continue

                    # Total cars to move this step: capped by how many are actually on the road
                    total_cars_to_cross = min(cars_per_step, road['vehicleCount'])
                    total_cars_to_cross = max(1, int(round(total_cars_to_cross))) if road['vehicleCount'] > 0 else 0
                    if total_cars_to_cross == 0:
                        continue

                    # Distribute total_cars_to_cross to distribute proportionally fo each connection
                    # Uses the Largest-Remainder Method to avoid rounding errors
                    # for example with 1 car and two connections 60%/40%, one connection gets 1 and the other 0
                    exact_per_conn = [total_cars_to_cross * c['trafficDistributionRate'] / total_distribution_pct
                                      for c in out_conns]
                    allocated = [int(e) for e in exact_per_conn]
                    leftover = total_cars_to_cross - sum(allocated)
                    # the leftover cars go to the largest percentage connection
                    priority_order = sorted(range(len(exact_per_conn)),
                                            key=lambda i: exact_per_conn[i] - allocated[i],
                                            reverse=True)
                    for i in range(leftover):
                        allocated[priority_order[i]] += 1

                    for i, conn in enumerate(out_conns):
                        cars_to_move = allocated[i]
                        if cars_to_move <= 0:
                            continue
                        dest_road_id = conn['destinationRoadId']
                        dest_road    = self.roads[dest_road_id]

                        # avoid moving more cars than the ines present on the road
                        cars_to_move = min(cars_to_move, road['vehicleCount'])
                        # pending_moves accounts for cars already reserved by other connections this step
                        free_space_at_dest = (dest_road['capacity'] - dest_road['vehicleCount'] - pending_moves[dest_road_id])
                        cars_to_move = min(cars_to_move, max(0, free_space_at_dest))

                        if cars_to_move > 0:
                            road['vehicleCount']        -= cars_to_move
                            pending_moves[dest_road_id] += cars_to_move

            #  apply pending moves to destinations
            for road_id, incoming_cars in pending_moves.items():
                self.roads[road_id]['vehicleCount'] += incoming_cars

            # Update system vehicle count
            self.current_vehicles_in_system = sum(r['vehicleCount'] for r in self.roads.values())

            # recalculate traffic light durations every sd_interval seconds
            self.sd_elapsed += self.sim_step_time
            if self.sd_elapsed >= self.sd_interval:
                self.sd_elapsed = 0
                self.decision_step()

    def run(self):
        # Method to start the SNMP agent and keep it running
        self.setup_snmp()
        self.bind_scalars()
        self.bind_tables()
        
        try:
            loop = asyncio.get_event_loop()
            
            # Add the simulation loop to the asyncio execution
            loop.create_task(self.simulation_loop())
            
            loop.run_forever()
        except KeyboardInterrupt:
            print("\nShutting down Central System.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Traffic Control Central System')
    parser.add_argument(
        '--config',
        default='traffic-config.json',
        help='Config filename inside src/traffic-configs/ (default: traffic-config.json)'
    )
    args = parser.parse_args()

    configs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'traffic-configs')
    config_path = os.path.join(configs_dir, args.config)

    if not os.path.isfile(config_path):
        print(f"[!] Config file not found: {config_path}")
        raise SystemExit(1)

    sc = CentralSystem(config_path)
    sc.run()
