import bpy


def get_unique_properties(collection): # get unique properties for curve objects
    unique_props = set()
    if collection:
        for obj in collection.all_objects:
            if obj and obj.type == 'CURVE':
                for key in obj.keys():
                    if key not in {'_RNA_UI', 'cycles'}:
                        unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context): # update the list when new variable is choosen
    props = context.scene.drill_holes_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop
        update_query_values(props, context)

def update_query_values(props, context): # update the query based on type of variable choosen
    collection = bpy.data.collections.get(props.collection_name)
    if collection and props.data_query_property:
        values = [obj.get(props.data_query_property) for obj in collection.all_objects if obj and props.data_query_property in obj and obj[props.data_query_property] not in [None, '', 'N/A']]
        converted_values = []
        for value in values:
            try:
                converted_values.append(float(value))
            except ValueError:
                converted_values.append(value)

        if converted_values:
            if all(isinstance(value, (float, int)) for value in converted_values):
                props.selected_property_type = 'NUMERICAL'
                props.numerical_min = min(converted_values)
                props.numerical_max = max(converted_values)
            else:
                props.selected_property_type = 'CATEGORICAL'
                props.categorical_values.clear()
                unique_values = set(converted_values)
                for val in unique_values:
                    item = props.categorical_values.add()
                    item.name = val
                    item.selected = True
        else:
            props.selected_property_type = ''
            props.numerical_min = 0
            props.numerical_max = 0
            props.categorical_values.clear()

class CategoricalValue(bpy.types.PropertyGroup): 
    name: bpy.props.StringProperty()
    selected: bpy.props.BoolProperty(default=True)
    
class OBJECT_OT_check_uncheck_all(bpy.types.Operator):
    bl_idname = "object.check_uncheck_all"
    bl_label = "Check/Uncheck All"

    action: bpy.props.EnumProperty(
        items=[
            ('CHECK', "Check All", ""),
            ('UNCHECK', "Uncheck All", "")
        ],
        default='CHECK'
    )

    def execute(self, context):
        props = context.scene.drill_holes_tool
        for item in props.categorical_values:
            item.selected = (self.action == 'CHECK')
        return {'FINISHED'}


class OBJECT_OT_apply_data_query(bpy.types.Operator):
    bl_idname = "object.apply_data_query"
    bl_label = "Apply Data Query"

    def execute(self, context):
        props = context.scene.drill_holes_tool
        collection = bpy.data.collections.get(props.collection_name)
        if not collection:
            print("Collection not found")
            self.report({'ERROR'}, "Collection not found")
            return {'CANCELLED'}

        # Clear previous query
        try:
            for obj in collection.all_objects:
                if obj and obj.type == 'CURVE':
                    obj.hide_set(False)
        except Exception as e:
            print(f"An error occurred while clearing the query: {e}")
            self.report({'ERROR'}, f"An error occurred while clearing the query: {e}")
            return {'CANCELLED'}

        # Apply new query
        try:
            for obj in collection.all_objects:
                if obj is None or obj.type != 'CURVE':
                    continue

                if props.data_query_property in obj:
                    value = obj.get(props.data_query_property, None)
                    if value is None:
                        obj.hide_set(True)
                        continue

                    if isinstance(value, bytes):
                        value = value.decode('utf-8', errors='ignore').strip()
                    else:
                        value = str(value).strip()

                    if value:
                        if props.selected_property_type == 'CATEGORICAL':
                            if not any(item.selected and value == item.name for item in props.categorical_values):
                                obj.hide_set(True)
                            else:
                                obj.hide_set(False)
                        elif props.selected_property_type == 'NUMERICAL':
                            try:
                                query_value = float(value)
                                if query_value < props.numerical_min or query_value > props.numerical_max:
                                    obj.hide_set(True)
                                else:
                                    obj.hide_set(False)
                            except ValueError:
                                obj.hide_set(True)
                    else:
                        obj.hide_set(True)  # Hide objects with None or blank values (ie drill traces)
        except Exception as e:
            print(f"An error occurred: {e}")
            self.report({'ERROR'}, f"An error occurred: {e}")
            return {'CANCELLED'}

        bpy.context.view_layer.update()
        return {'FINISHED'}

class OBJECT_OT_reset_query(bpy.types.Operator):
    bl_idname = "object.reset_query"
    bl_label = "Reset Query"

    def execute(self, context):
        props = context.scene.drill_holes_tool
        collection = bpy.data.collections.get(props.collection_name)
        if not collection:
            print("Collection not found")
            self.report({'ERROR'}, "Collection not found")
            return {'CANCELLED'}

        try:
            for obj in collection.all_objects:
                if obj and obj.type == 'CURVE':
                    obj.hide_set(False)
        except Exception as e:
            print(f"An error occurred: {e}")
            self.report({'ERROR'}, f"An error occurred: {e}")
            return {'CANCELLED'}

        bpy.context.view_layer.update()
        return {'FINISHED'}

class OBJECT_PT_custom_panel(bpy.types.Panel):
    bl_label = "Drill Data Query"
    bl_idname = "DATAQUERY_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_parent_id = "GEOMOD_PT_drilling_category"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        mytool = context.scene.drill_holes_tool

        layout.prop_search(mytool, "collection_name", bpy.data, "collections", text="Choose Drill Hole Collection")
        if mytool.available_properties:
            layout.prop(mytool, "data_query_property", text="Query Property")
            
            if mytool.selected_property_type == 'CATEGORICAL':
                # buttons for checking/unchecking all
                row = layout.row(align=True)
                row.operator("object.check_uncheck_all", text="Check All").action = 'CHECK'
                row.operator("object.check_uncheck_all", text="Uncheck All").action = 'UNCHECK'
                
                # checkboxes for each categorical value
                for item in mytool.categorical_values:
                    layout.prop(item, "selected", text=item.name)
            elif mytool.selected_property_type == 'NUMERICAL':
                layout.prop(mytool, "numerical_min", text="Minimum Value")
                layout.prop(mytool, "numerical_max", text="Maximum Value")
            
            layout.operator("object.apply_data_query", text="Apply Query", icon='PLAY')
            layout.operator("object.reset_query", text="Reset Query")


class DrillHolesToolProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    data_query_property: bpy.props.EnumProperty(
        name="Data Query Property",
        description="Select a property for querying",
        items=lambda self, context: [(prop.name, prop.name, "") for prop in context.scene.drill_holes_tool.available_properties],
        update=update_query_values
    )
    selected_property_type: bpy.props.StringProperty()
    categorical_values: bpy.props.CollectionProperty(type=CategoricalValue)
    numerical_min: bpy.props.FloatProperty(name="Minimum Value")
    numerical_max: bpy.props.FloatProperty(name="Maximum Value")

def register():
    bpy.utils.register_class(CategoricalValue)
    bpy.utils.register_class(DrillHolesToolProperties)
    bpy.utils.register_class(OBJECT_OT_apply_data_query)
    bpy.utils.register_class(OBJECT_OT_reset_query)
    bpy.utils.register_class(OBJECT_OT_check_uncheck_all)  
    bpy.utils.register_class(OBJECT_PT_custom_panel)
    bpy.types.Scene.drill_holes_tool = bpy.props.PointerProperty(type=DrillHolesToolProperties)

def unregister():
    bpy.utils.unregister_class(CategoricalValue)
    bpy.utils.unregister_class(DrillHolesToolProperties)
    bpy.utils.unregister_class(OBJECT_OT_apply_data_query)
    bpy.utils.unregister_class(OBJECT_OT_reset_query)
    bpy.utils.unregister_class(OBJECT_OT_check_uncheck_all)  
    bpy.utils.unregister_class(OBJECT_PT_custom_panel)
    del bpy.types.Scene.drill_holes_tool


if __name__ == "__main__":
    register()
