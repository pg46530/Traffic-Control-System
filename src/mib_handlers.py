def get_dynamic_scalar_class(mib_scalar_instance_class):
    """
    Factory function to create a DynamicScalar class that inherits from
    the dynamically loaded MibScalarInstance.
    """
    class DynamicScalar(mib_scalar_instance_class):
        def __init__(self, name, instId, syntax, agent, attr_name, on_write_callback=None):
            # Initialize the PySNMP MibScalarInstance parent class
            super().__init__(name, instId, syntax)
            # Store the reference to the main agent and the target attribute
            self.agent = agent
            self.attr_name = attr_name
            self.on_write_callback = on_write_callback

        def readGet(self, varBind, **context):
            name, val = varBind
            
            # Fetch the most up-to-date value from the agent's memory
            new_val = getattr(self.agent, self.attr_name)
            
            # Return the OID with the new cloned value
            return name, self.syntax.clone(new_val)

        def writeTest(self, varBind, **context):
            # Test if the value is acceptable (syntax is already validated by pysnmp)
            pass

        def writeCommit(self, varBind, **context):
            # Commit the new value to the agent's memory
            name, val = varBind
            
            # For trafficLightColor enum the integer conversion is required,
            if hasattr(val, 'clone'): # MibScalar/Column syntax types
                 py_val = int(val) if val.__class__.__name__ == 'Integer32' else val.prettyPrint()
                 try:
                     py_val = int(py_val)
                 except ValueError:
                     pass
            else:
                 py_val = int(val)
            
            setattr(self.agent, self.attr_name, py_val)

            if self.on_write_callback:
                self.on_write_callback(py_val)
            
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

        def writeTest(self, varBind, **context):
            pass

        def writeCommit(self, varBind, **context):
            name, val = varBind
            row_id = int(name[-1])

            table_dict = getattr(self.agent, self.table_name)

            if row_id in table_dict:
                try:
                    py_val = int(val)
                except Exception:
                    py_val = str(val)
                
                # saves the new value back to the agent's dictionary
                table_dict[row_id][self.attr_name] = py_val
            else:
                from pysnmp.smi.error import NoSuchInstanceError
                raise NoSuchInstanceError(name=name)

    return DynamicColumn
