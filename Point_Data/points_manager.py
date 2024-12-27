import bpy
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import tempfile
import os
import numpy as np

def get_unique_properties(collection):
    unique_props = set()
    for obj in collection.all_objects:
        if obj.type == 'MESH':
            for key in obj.keys():
                if key not in {'_RNA_UI', 'cycles'}:
                    unique_props.add(key)
    return list(unique_props)

def update_properties_list(self, context):
    props = context.scene.my_mesh_tool
    collection = bpy.data.collections.get(props.collection_name)
    if collection:
        props.available_properties.clear()
        sorted_properties = sorted(get_unique_properties(collection))
        for prop in sorted_properties:
            item = props.available_properties.add()
            item.name = prop
        update_property_type_and_color_ramp(props, context)
        # Dynamically update size based on viewport clip_end
        clip_end = get_viewport_clip_end()
        props.size = clip_end * 0.0012

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

def get_viewport_clip_end():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    return space.clip_end
    return 10000.0  # Default fallback if not found


class OBJECT_OT_apply_color_changes_mesh(bpy.types.Operator):
    bl_idname = "object.apply_color_changes_mesh"
    bl_label = "Apply Color Changes to Mesh"
    
    original_positions = {}

    def execute(self, context):
        props = context.scene.my_mesh_tool
        collection = bpy.data.collections.get(props.collection_name)
        if not collection:
            print("Collection not found")
            self.report({'ERROR'}, "Collection not found")
            return {'CANCELLED'}

        

        property_type, property_data = self.get_property_type_and_data(collection, props.selected_property)
        log_scale_property_type, log_scale_property_data = self.get_property_type_and_data(collection, props.log_scale_property)

        color_map = {}
        normalization = None
        for obj in collection.all_objects:
            if obj.type == 'MESH' and props.selected_property in obj:
                value = obj.get(props.selected_property, "")
                
                if isinstance(value, str):
                    value = value.strip()
                if value:
                    try:
                        float_value = float(value) if property_type == 'NUMERICAL' else value
                        color, cmap, norm = self.map_color(float_value, props.color_ramp_options, property_type, property_data, props)
                        color_map[value] = color  # Store color for legend creation
                        self.apply_color(obj, color)
                        if norm:  # Store the normalization used only if it's defined
                            normalization = norm

                        if props.use_size_scaling:  # if size scaling option is enabled
                            self.store_original_positions(obj)
                            self.reset_to_original_positions(obj)

                            if props.log_scale and props.log_scale_property in obj:
                                size_value_str = obj[props.log_scale_property]
                                try:
                                    size_value = float(size_value_str)
                                    max_value = max(log_scale_property_data['values'])
                                    min_value = min(log_scale_property_data['values'])
                                    min_size = 0.5 * props.size_multiplier
                                    max_size = 3.5 * props.size_multiplier

                                    if props.use_full_data_range:
                                        size_value = min_size + ((size_value - min_value) / (max_value - min_value)) * (max_size - min_size)
                                    else:
                                        size_value = min_size + (np.log1p(size_value) / np.log1p(max_value)) * (max_size - min_size)
                                    
                                    for v in obj.data.vertices:
                                        v.co.normalize()
                                        v.co *= size_value
                                except ValueError:
                                    # If cannot be converted to float, use default size
                                    for v in obj.data.vertices:
                                        v.co.normalize()
                                        v.co *= props.size
                            else:
                                for v in obj.data.vertices:
                                    v.co.normalize()
                                    v.co *= props.size
                        else:
                            # If size scaling is not enabled, keep vertices as is
                            pass

                        obj.name = str(value)  # Ensure obj.name is always a string
                    except ValueError:
                        continue
                else:
                    self.apply_default_settings(obj)
                    obj.name = "Mesh Object"
            

        
        bpy.context.view_layer.update()

        if props.legend:
            self.create_legend_image(props.color_ramp_options, property_data['values'], property_type, color_map, props.selected_property, normalization)
            self.show_legend_in_image_editor()

        return {'FINISHED'}

    def store_original_positions(self, obj):
        if obj.name not in self.original_positions:
            self.original_positions[obj.name] = [(v.co.copy()) for v in obj.data.vertices]

    def reset_to_original_positions(self, obj):
        if obj.name in self.original_positions:
            for v, original_pos in zip(obj.data.vertices, self.original_positions[obj.name]):
                v.co = original_pos

    def apply_default_settings(self, obj):
        obj.data.materials.clear()

    def get_property_type_and_data(self, collection, prop_name):
        raw_values = [obj[prop_name] for obj in collection.all_objects if prop_name in obj and obj[prop_name] not in [None, '', 'N/A']]
        converted_values = []
        for value in raw_values:
            try:
                converted_values.append(float(value))
            except ValueError:
                continue

        if converted_values:
            min_val = np.min(converted_values)
            max_val = np.max(converted_values)
            return ('NUMERICAL', {'min': min_val, 'max': max_val, 'values': converted_values})
        else:
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

    def apply_color(self, obj, color):
        color_key = tuple(color[:3])  
        material_name = f"Material_{color_key}"
        
        # Check if the material already exists in Blender
        material = bpy.data.materials.get(material_name)
        
        if not material:
            # If the material doesn't exist, create a new one
            material = bpy.data.materials.new(name=material_name)
            material.use_nodes = True
            emission = material.node_tree.nodes.new(type='ShaderNodeEmission')
            material.node_tree.links.new(emission.outputs['Emission'], material.node_tree.nodes.get('Material Output').inputs['Surface'])
            emission.inputs['Color'].default_value = (color[0], color[1], color[2], 1)
            
        # Apply the materal to the object
        if not obj.data.materials:
            obj.data.materials.append(material)
        else:
            obj.data.materials[0] = material

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
            patches = [plt.plot([], [], marker="o", ms=10, ls="", mec=None, color=colors[i],
                                label="{:s}".format(unique_values[i]))[0] for i in range(len(unique_values))]
            ax.legend(handles=patches)

        ax.set_title(property_name)  # Set the title of the legend
        ax.axis('off')
        plt.tight_layout()
        
        # Create a temporary file to store the legend
        temp_dir = tempfile.gettempdir()  
        self.legend_path = os.path.join(temp_dir, "legend.png")  
        
        plt.savefig(self.legend_path, bbox_inches='tight', pad_inches=0.35, dpi=210)  # Increase resolution with dpi=300
        plt.close(fig)

    def show_legend_in_image_editor(self):
        bpy.ops.image.open(filepath=self.legend_path)
        image = bpy.data.images.load(self.legend_path)

        # show legend in 'IMAGE_EDITOR'
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
                        with bpy.context.temp_override(**override):
                            bpy.ops.image.view_all()
                        return


class OBJECT_PT_custom_panel_mesh(bpy.types.Panel): # UI Panel
    bl_label = "Manage Point Data"
    bl_idname = "IMPORT_PT_panel_manage_mesh"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GeoModeller'
    bl_parent_id = "GEOMOD_PT_points_category"
    bl_options = {'DEFAULT_CLOSED'}
    

    def draw(self, context):
        layout = self.layout
        mytool = context.scene.my_mesh_tool

        layout.prop_search(mytool, "collection_name", bpy.data, "collections", text="Choose Mesh Collection")
        if mytool.available_properties:
            layout.prop(mytool, "selected_property", text="Attribute")
            if mytool.selected_property:
                layout.prop(mytool, "color_ramp_options", text="Color Ramp")
                layout.prop(mytool, "use_size_scaling", text="Adjust Size")
                if mytool.use_size_scaling:
                    layout.prop(mytool, "size", text="Size")
                    
                layout.prop(mytool, "adjust_for_outliers", text="Colormap Normalization")
                if mytool.adjust_for_outliers:
                    layout.prop(mytool, "scaling_factor", text="IQR Scaling Factor")
                    
                
                if mytool.use_size_scaling:
                    layout.prop(mytool, "log_scale", text="Log Scale Sizing")
                    if mytool.log_scale:
                        layout.prop(mytool, "log_scale_property", text="Log Scale Attribute")
                        layout.prop(mytool, "use_full_data_range", text="Switch to Linear Scale")
                        layout.prop(mytool, "size_multiplier", text="Size Multiplier")
                layout.prop(mytool, "legend", text="Legend")
                layout.operator("object.apply_color_changes_mesh", text="Render", icon='PLAY')

class MyMeshProperties(bpy.types.PropertyGroup):
    collection_name: bpy.props.StringProperty(name="Collection Name", update=update_properties_list)
    available_properties: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    selected_property: bpy.props.EnumProperty(
        name="Selected Property",
        description="Select a property for coloring",
        items=lambda self, context: [(prop.name, prop.name, "") for prop in context.scene.my_mesh_tool.available_properties],
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
    use_size_scaling: bpy.props.BoolProperty(
        name="Use Size Scaling",
        description="Enable or disable size scaling",
        default=False
    )
    size: bpy.props.FloatProperty(
        name="Size",
        description="Default size for mesh objects",
        default=1.0,
        min=0.1,
        max=500
    )
    size_multiplier: bpy.props.FloatProperty(
        name="Size Multiplier",
        description="Multiplier for min and max sizes",
        default=1.0,
        min=0.1,
        max=100.0
    )
    log_scale: bpy.props.BoolProperty(
        name="Log Scale",
        description="Enable logarithmic scaling for object size",
        default=False
    )
    log_scale_property: bpy.props.EnumProperty(
        name="Log Scale Property",
        description="Select a property for logarithmic scaling",
        items=lambda self, context: [(prop.name, prop.name, "") for prop in context.scene.my_mesh_tool.available_properties]
    )
    use_full_data_range: bpy.props.BoolProperty(
        name="Use Full Data Range",
        description="Use the full range of the data for size scaling",
        default=False
    )
    legend: bpy.props.BoolProperty(
        name="Legend",
        description="Display legend in the scene",
        default=False
    )

def register():
    bpy.utils.register_class(MyMeshProperties)
    bpy.utils.register_class(OBJECT_OT_apply_color_changes_mesh)
    bpy.utils.register_class(OBJECT_PT_custom_panel_mesh)
    bpy.types.Scene.my_mesh_tool = bpy.props.PointerProperty(type=MyMeshProperties)

def unregister():
    bpy.utils.unregister_class(MyMeshProperties)
    bpy.utils.unregister_class(OBJECT_OT_apply_color_changes_mesh)
    bpy.utils.unregister_class(OBJECT_PT_custom_panel_mesh)
    del bpy.types.Scene.my_mesh_tool

if __name__ == "__main__":
    register()
