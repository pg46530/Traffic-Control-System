def get_dynamic_scalar_class(mib_scalar_instance_class):
    """
    Factory function to create a DynamicScalar class that inherits from
    the dynamically loaded MibScalarInstance.
    """
    class DynamicScalar(mib_scalar_instance_class):
        def __init__(self, name, instId, syntax, agent, attr_name):
            # Initialize the PySNMP MibScalarInstance parent class
            super().__init__(name, instId, syntax)
            # Store the reference to the main agent and the target attribute
            self.agent = agent
            self.attr_name = attr_name

        def readGet(self, varBind, **context):
            name, val = varBind
            
            # Fetch the most up-to-date value from the agent's memory
            new_val = getattr(self.agent, self.attr_name)
            
            # Return the OID with the new cloned value
            return name, self.syntax.clone(new_val)
            
    return DynamicScalar

def get_dynamic_column_class(mib_table_column_class):
    """
    Factory function to create a DynamicColumn class that inherits from
    the dynamically loaded MibTableColumn or MibScalarInstance.
    """
    class DynamicColumn(mib_table_column_class):
        def __init__(self, name, instId, syntax, agent, table_name, attr_name):
            super().__init__(name, instId, syntax)
            self.agent = agent
            self.table_name = table_name  # The dictionary name in CentralSystem ('roads' or 'connections')
            self.attr_name = attr_name    # The specific key to fetch ('vehicleCount', 'capacity', etc)

        def readGet(self, varBind, **context):
            name, val = varBind
            
            # extract the last integer of the OID as the row index (e.g. roadId 1)
            row_id = int(name[-1])

            # Navigate through the agent's dictionaries to find the correct row and column attribute
            table_dict = getattr(self.agent, self.table_name)
            
            if row_id in table_dict:
                row_data = table_dict[row_id]
                new_val = row_data[self.attr_name]
                return name, self.syntax.clone(new_val)
            else:
                # Standard PySNMP response if row is completely missing
                from pysnmp.smi.error import NoSuchInstanceError
                raise NoSuchInstanceError(name=name)

    return DynamicColumn
