import bpy
import tempfile
import os
import bmesh
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from collections import defaultdict

magenta_colors = ["blue", "lightgreen", "yellow", "orange", "red", "magenta"]
magenta_continuous_cmap = LinearSegmentedColormap.from_list("magenta_continuous_ramp", magenta_colors)
plt.register_cmap(name="magenta_continuous_ramp", cmap=magenta_continuous_cmap)

def get_unique_properties(collection): # find properties for drill hole curve objects
    unique_props = set()
    for obj in collection.all_objects:
        if obj.type == 'CURVE':
            for key in obj.keys():
                if key not in {'_RNA_UI', 'cycles'}:
                    unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context):  # Update the list for the selected variable
    props = context.scene.my_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        # Get unique properties and sort them alphabetically
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop
        update_property_type_and_color_ramp(props, context)

color_ramp_items = []


def get_color_ramp_items(self, context):
    return color_ramp_items

def update_property_type_and_color_ramp(props, context): # dynamic color ramp options
    collection = bpy.data.collections.get(props.collection_name)
    if collection and props.selected_property:
        values = [obj[props.selected_property] for obj in collection.all_objects if props.selected_property in obj and obj[props.selected_property] not in [None, '', 'N/A']]
        global color_ramp_items
        converted_values = []
        for value in values:
            try:
                converted_values.append(float(value))
            except ValueError:
                converted_values.append(value)

        if all(isinstance(value, (float, int)) for value in converted_values):  # drop-down list for numerical color ramps ##### can add any matplotlib color-ramp 
            props.selected_property_type = 'NUMERICAL'
            color_ramp_items = [
                ('viridis', 'viridis', ''),
                ('Reds', 'Reds', ''),
                ('hot_r', 'hot_r', ''),
                ('Spectral_r', 'Spectral_r', ''),
                ('jet', 'jet', ''),
                ('plasma', 'plasma', ''),
                ('inferno', 'inferno', ''),
                ('magma', 'magma', ''),
                ('coolwarm', 'coolwarm', ''),
                ('bwr', 'bwr', ''),
                ('magenta_continuous_ramp', 'Spectral_Magenta', '')  # this one is custom
            ]
            print(f"Property '{props.selected_property}' is classified as NUMERICAL")
        else: # drop down list for categorical color ramps
            props.selected_property_type = 'CATEGORICAL'
            color_ramp_items = [('tab10', 'Tab10', ''), ('tab20', 'Tab20', '')]
            print(f"Property '{props.selected_property}' is classified as CATEGORICAL")

    if context.area:
        context.area.tag_redraw()

class OBJECT_OT_apply_color_changes(bpy.types.Operator): # main operator, misleading name here
    bl_idname = "object.apply_color_changes"
    bl_label = "Apply Color Changes"

    def execute(self, context):
        props = context.scene.my_tool
        collection = bpy.data.collections.get(props.collection_name)
        if not collection:
            print("Collection not found")
            self.report({'ERROR'}, "Collection not found")
            return {'CANCELLED'}

        # Cache all curve objects that have the selected property
        all_objects = [
            obj for obj in collection.all_objects 
            if obj.type == 'CURVE' and props.selected_property in obj
        ]

        property_type, property_data = self.get_property_type_and_data(collection, props.selected_property)
        log_scale_property_type, log_scale_property_data = self.get_property_type_and_data(collection, props.log_scale_property)

        if props.contacts_to_point and property_type == 'CATEGORICAL':
            from collections import defaultdict

            # Create collection name based on the selected property
            contacts_collection_name = f"Conatacts_{props.selected_property}"

            # Ensure the '[selected_property]_contacts' collection exists, create if not
            contacts_collection = bpy.data.collections.get(contacts_collection_name)
            if not contacts_collection:
                contacts_collection = bpy.data.collections.new(contacts_collection_name)
                bpy.context.scene.collection.children.link(contacts_collection)

            # Build a map of upper vertex positions to objects
            upper_vertex_map = defaultdict(list)

            for obj in all_objects:
                curve = obj.data
                if curve.splines and len(curve.splines[0].points) == 2:
                    spline = curve.splines[0]
                    points = spline.points
                    upper_vertex = points[0] if points[0].co.z > points[1].co.z else points[1]
                    position = tuple(round(coord, 6) for coord in upper_vertex.co.xyz)
                    upper_vertex_map[position].append(obj)

            # iterate over all objects to find contacts
            for obj in all_objects:
                obj_property_value = obj.get(props.selected_property, None)
                curve = obj.data

                if curve.splines and len(curve.splines[0].points) == 2:
                    spline = curve.splines[0]
                    points = spline.points

                    lower_vertex = points[0] if points[0].co.z < points[1].co.z else points[1]
                    position = tuple(round(coord, 6) for coord in lower_vertex.co.xyz)
                    contact = False

                    # Retrieve objects with upper vertices at the same position
                    potential_contacts = upper_vertex_map.get(position, [])
                    for other_obj in potential_contacts:
                        if other_obj != obj:
                            other_obj_property_value = other_obj.get(props.selected_property, None)
                            if obj_property_value and other_obj_property_value and obj_property_value != other_obj_property_value:
                                contact = True
                                break

                    # Create disc if contact detected
                    if contact:
                        self.create_disc_at_vertex(lower_vertex.co, obj_property_value, contacts_collection, obj)
        

        color_map = {}
        normalization = None
        for obj in collection.all_objects:
            if obj.type == 'CURVE' and props.selected_property in obj:
                value = obj.get(props.selected_property, "").strip()
                if value:
                    try:
                        float_value = float(value) if property_type == 'NUMERICAL' else value
                        color, cmap, norm = self.map_color(float_value, props.color_ramp_options, property_type, property_data, props)
                        color_map[value] = color  # Store color for legend creation
                        self.apply_color(obj, color)
                        if norm:  # Store the normalization used only if it's defined
                            normalization = norm
                        if props.log_scale and props.log_scale_property in obj:
                            size_value_str = obj[props.log_scale_property]
                            try:
                                size_value = float(size_value_str)
                                max_value = max(log_scale_property_data['values'])
                                min_value = min(log_scale_property_data['values'])
                                min_size = 2 * props.size_multiplier # 2 and 12 set as bounds to start, maybe make this a user input?
                                max_size = 12 * props.size_multiplier

                                if props.use_full_data_range:
                                    size_value = min_size + ((size_value - min_value) / (max_value - min_value)) * (max_size - min_size)
                                else:
                                    size_value = min_size + (np.log1p(size_value) / np.log1p(max_value)) * (max_size - min_size)
                                
                                obj.data.bevel_depth = size_value
                            except ValueError:
                                # If size_value_str cannot be converted to float, use default size
                                obj.data.bevel_depth = props.size
                        else:
                            obj.data.bevel_depth = props.size
                        obj.name = value
                    except ValueError:
                        continue
                else:
                    self.apply_default_settings(obj)
                    obj.name = "Drill Trace"
            

        
        bpy.context.view_layer.update()

        if props.legend:
            self.create_legend_image(props.color_ramp_options, property_data['values'], property_type, color_map, props.selected_property, normalization)
            self.show_legend_in_image_editor()

        return {'FINISHED'}

    def create_disc_at_vertex(self, location, obj_property_value, contacts_collection, source_obj):
        
        disc_mesh = self.create_disc_mesh(20, f"{obj_property_value}_contact")
        disc_obj = bpy.data.objects.new(f"{obj_property_value}_contact", disc_mesh)
        contacts_collection.objects.link(disc_obj)
        
        # Set the location of the disc
        disc_obj.location = (location.x, location.y, location.z)

        # Add the custom property 'name' to the disc
        disc_obj['name'] = obj_property_value

        # Copy custom properties from the source object
        self.copy_custom_properties(disc_obj, source_obj)

        return disc_obj

    def create_disc_mesh(self, radius, name):
        # Create a flat disc as point object
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=32)
        bm.to_mesh(mesh)
        bm.free()
        return mesh

    def copy_custom_properties(self, disc_obj, source_obj):
        # List of properties to copy
        properties_to_copy = ['azimuth', 'dip', 'polarity']
        
        if "_RNA_UI" not in disc_obj:
            disc_obj["_RNA_UI"] = {}

        for prop in properties_to_copy:
            
            if prop in source_obj:
                disc_obj[prop] = source_obj[prop]
            else:
                # Set default values ONLY if the property doesn't exist already
                if prop == 'azimuth':
                    disc_obj[prop] = 0
                elif prop == 'dip':
                    disc_obj[prop] = 0
                elif prop == 'polarity':
                    disc_obj[prop] = 1  

            # Add RNA UI definitions 
            if prop not in disc_obj["_RNA_UI"]:
                if prop == 'azimuth':
                    disc_obj["_RNA_UI"][prop] = {"max": 360, "description": "Azimuth (0-360)", "override_library_create": True}
                elif prop == 'dip':
                    disc_obj["_RNA_UI"][prop] = {"max": 90, "description": "Dip (0-90)", "override_library_create": True}
                elif prop == 'polarity':
                    disc_obj["_RNA_UI"][prop] = {"max": 1, "description": "Polarity (0-1)", "override_library_create": True}

    def apply_default_settings(self, obj): # default to trace for 'no data' cells
        obj.data.bevel_depth = 0
        obj.data.materials.clear()

    def get_property_type_and_data(self, collection, prop_name):
        raw_values = [obj[prop_name] for obj in collection.all_objects if prop_name in obj and obj[prop_name] not in [None, '', 'N/A']]
        converted_values = []
        for value in raw_values:
            try:
                converted_values.append(float(value))
            except ValueError:
                ##print("values not float")
                continue

        if converted_values:
            min_val = np.min(converted_values)
            max_val = np.max(converted_values)
            return ('NUMERICAL', {'min': min_val, 'max': max_val, 'values': converted_values})
        else:
            print("propname2;", prop_name)
            unique_values = list(set(raw_values))
            return ('CATEGORICAL', {'values': unique_values})

    def map_color(self, value, cmap_name, property_type, property_data, props):
        cmap = plt.get_cmap(cmap_name)
        norm = None  # Initialize norm to None
        if property_type == 'NUMERICAL' and 'values' in property_data:
            if props.adjust_for_outliers:
                q75, q25 = np.percentile(property_data['values'], [75, 25])
                iqr = q75 - q25
                lower_bound = q25 - (props.scaling_factor * iqr)
                upper_bound = q75 + (props.scaling_factor * iqr)

                filtered_values = [v for v in property_data['values'] if lower_bound <= v <= upper_bound]
                min_val = min(filtered_values) if filtered_values else q25
                max_val = max(filtered_values) if filtered_values else q75
            else:
                min_val = property_data['min']
                max_val = property_data['max']

            norm = plt.Normalize(min_val, max_val)
            normalized_value = norm(float(value)) if max_val > min_val else 0.0
        elif property_type == 'CATEGORICAL':
            unique_categories = property_data['values']
            category_index = unique_categories.index(value)
            normalized_value = category_index / (len(unique_categories) - 1) if len(unique_categories) > 1 else 0.0
        else:
            normalized_value = 0.5

        rgba_color = cmap(normalized_value)
        return rgba_color, cmap, norm


    def apply_color(self, object, color):
        if not object.data.materials:
            material = bpy.data.materials.new(name="CurveMaterial")
            material.use_nodes = True
            emission = material.node_tree.nodes.new(type='ShaderNodeEmission')
            material.node_tree.links.new(emission.outputs['Emission'], material.node_tree.nodes.get('Material Output').inputs['Surface'])
            object.data.materials.append(material)
        else:
            material = object.data.materials[0]

        emission = material.node_tree.nodes.get('Emission')
        if not emission:
            emission = material.node_tree.nodes.new(type='ShaderNodeEmission')
            material.node_tree.links.new(emission.outputs['Emission'], material.node_tree.nodes.get('Material Output').inputs['Surface'])
        emission.inputs['Color'].default_value = (color[0], color[1], color[2], 1)

    def create_legend_image(self, cmap_name, values, property_type, color_map, property_name, normalization):
        fig, ax = plt.subplots(figsize=(2, 2))  
        cmap = plt.get_cmap(cmap_name)

        if property_type == 'NUMERICAL':
            norm = normalization  # Use the stored normalization
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax)
            cbar.locator = plt.MaxNLocator(nbins=5)  # add tick markers
            cbar.update_ticks()
        else:
            unique_values = sorted(set(values))
            colors = [color_map[val] for val in unique_values]
            patches = [plt.plot([],[], marker="o", ms=10, ls="", mec=None, color=colors[i], 
                label="{:s}".format(unique_values[i]) )[0]  for i in range(len(unique_values))]
            ax.legend(handles=patches)

        ax.set_title(property_name)  # Sets the title of the legend to the propname
        ax.axis('off')
        plt.tight_layout()
        
        # Create a temporary file to store the legend
        temp_dir = tempfile.gettempdir()  
        self.legend_path = os.path.join(temp_dir, "legend.png")  
    
        plt.savefig(self.legend_path, bbox_inches='tight', pad_inches=0.35, dpi=210)  
        plt.close(fig)



    def show_legend_in_image_editor(self): # creates a legend that populates in the image editor. You need to switch to image editor to view it
        bpy.ops.image.open(filepath=self.legend_path)
        image = bpy.data.images.load(self.legend_path)

        # Check if 'IMAGE_EDITOR' exists
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = {
                            'area': area,
                            'region': region,
                            'space_data': area.spaces.active,
                            'screen': bpy.context.screen,
                            'window': bpy.context.window,
                        }
                        bpy.context.window_manager.windows.update()
                        area.spaces.active.image = image
                        with bpy.context.temp_override(**override): # override each time legend is created
                            bpy.ops.image.view_all()
                        return

class OBJECT_PT_custom_panel(bpy.types.Panel): # UI panel 
    bl_label = "Manage Drill Holes"
    bl_idname = "IMPORT_PT_panel_manage"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'  
    bl_parent_id = "GEOMOD_PT_drilling_category"  
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        mytool = context.scene.my_tool

        layout.prop_search(mytool, "collection_name", bpy.data, "collections", text="Choose Drill Hole Collection")
        if mytool.available_properties:
            layout.prop(mytool, "selected_property", text="Attribute")
            if mytool.selected_property:
                layout.prop(mytool, "color_ramp_options", text="Color Ramp")
                layout.prop(mytool, "size", text="Size")
                if mytool.selected_property_type == 'CATEGORICAL':
                    layout.prop(mytool, "contacts_to_point", text="Contacts to Points")
                if mytool.selected_property_type == 'NUMERICAL':
                    layout.prop(mytool, "adjust_for_outliers", text="Colormap Normalization")
                    if mytool.adjust_for_outliers:
                        layout.prop(mytool, "scaling_factor", text="IQR Scaling Factor")
                layout.prop(mytool, "log_scale", text="Log Scale Sizing")
                if mytool.log_scale:
                    layout.prop(mytool, "log_scale_property", text="Log Scale Attribute")
                    layout.prop(mytool, "use_full_data_range", text="Switch to Linear Scale")
                    layout.prop(mytool, "size_multiplier", text="Size Multiplier")
                layout.prop(mytool, "legend", text="Legend")
                layout.operator("object.apply_color_changes", text="Render", icon='PLAY')

class MyProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    selected_property: bpy.props.EnumProperty(
        name="Selected Property",
        description="Select a property for coloring",
        items=lambda self, context: [(prop.name, prop.name, "") for prop in context.scene.my_tool.available_properties],
        update=update_property_type_and_color_ramp
    )
    selected_property_type: bpy.props.StringProperty()
    color_ramp_options: bpy.props.EnumProperty(
        name="Color Ramp",
        description="Choose a color ramp",
        items=get_color_ramp_items
    )
    adjust_for_outliers: bpy.props.BoolProperty(
        name="Adjust for Outliers",
        description="Enable to normalize color distribution by removing outliers",
        default=False
    )
    scaling_factor: bpy.props.FloatProperty(
        name="Scaling Factor",
        description="Scaling factor for outlier adjustment",
        default=3.0,
        min=1.0,
        max=100.0
    )
    size: bpy.props.FloatProperty(
        name="Size",
        description="Bevel depth for the curve objects",
        default=5.0,
        min=0.0,
        max=50.0
    )
    log_scale: bpy.props.BoolProperty(
        name="Log Scale",
        description="Enable logarithmic scaling for object size",
        default=False
    )
    log_scale_property: bpy.props.EnumProperty(
        name="Log Scale Property",
        description="Select a property for logarithmic scaling",
        items=lambda self, context: [(prop.name, prop.name, "") for prop in context.scene.my_tool.available_properties]
    )
    use_full_data_range: bpy.props.BoolProperty(
        name="Use Full Data Range",
        description="Use the full range of the data for size scaling",
        default=False
    )
    size_multiplier: bpy.props.FloatProperty(
        name="Size Multiplier",
        description="Multiplier for min and max sizes",
        default=1.0,
        min=0.005,
        max=10.0
    )
    legend: bpy.props.BoolProperty(
        name="Legend",
        description="Display legend in the scene",
        default=False
    )
    contacts_to_point: bpy.props.BoolProperty(
        name="Contacts to Point",
        description="Create spheres at contacts between different curves",
        default=False
    )

def register():
    bpy.utils.register_class(MyProperties)
    bpy.utils.register_class(OBJECT_OT_apply_color_changes)
    bpy.utils.register_class(OBJECT_PT_custom_panel)
    bpy.types.Scene.my_tool = bpy.props.PointerProperty(type=MyProperties)

def unregister():
    bpy.utils.unregister_class(MyProperties)
    bpy.utils.unregister_class(OBJECT_OT_apply_color_changes)
    bpy.utils.unregister_class(OBJECT_PT_custom_panel)
    del bpy.types.Scene.my_tool

if __name__ == "__main__":
    register()
